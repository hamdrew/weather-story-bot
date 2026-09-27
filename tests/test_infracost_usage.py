from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from scripts.infracost_usage import (
    RUN_SECONDS_PER_OFFICE,
    RUNS,
    SCENARIOS,
    Scenario,
    cost_table,
    usage,
    write_usage_files,
)

if TYPE_CHECKING:
    from pathlib import Path

BY_NAME = {scenario.name: scenario for scenario in SCENARIOS}


def test_scenarios_are_one_six_and_all_us_offices() -> None:
    assert [scenario.offices for scenario in SCENARIOS] == [1, 6, 122]


def test_one_office_counts_every_dynamodb_request() -> None:
    state = usage(BY_NAME["1-office"])["aws_dynamodb_table.state"]

    assert state["monthly_write_request_units"] == (
        2 * 2880  # lease take + release per run
        + 2880  # RUN# record per run
        + 2 * 24 * 30  # last_seen_at, hourly per unchanged story
        + 125  # last_seen_at again on the run after each post (record_posted clears it)
        + 2 * 125  # story item + posted/updated event per post
        + 10  # deletion event per update
        + 3 * 96  # rejected events
    )
    assert state["monthly_read_request_units"] == 2 * 2880  # GetItem per active story per run


def test_dynamodb_requests_scale_linearly_with_offices() -> None:
    one = usage(BY_NAME["1-office"])["aws_dynamodb_table.state"]
    six = usage(BY_NAME["6-offices"])["aws_dynamodb_table.state"]

    assert six["monthly_write_request_units"] == 6 * one["monthly_write_request_units"]
    assert six["monthly_read_request_units"] == 6 * one["monthly_read_request_units"]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_every_office_gets_its_own_invocation(scenario: Scenario) -> None:
    lam = usage(scenario)["aws_lambda_function.bot"]

    assert lam["monthly_requests"] == scenario.offices * RUNS
    assert lam["request_duration_ms"] == pytest.approx(RUN_SECONDS_PER_OFFICE * 1000)


def test_write_usage_files_writes_one_infracost_file_per_scenario(tmp_path: Path) -> None:
    write_usage_files(tmp_path)

    for scenario in SCENARIOS:
        written = json.loads((tmp_path / f"infracost-usage-{scenario.name}.yml").read_text())
        assert written == {"version": "0.1", "resource_usage": usage(scenario)}


def _resource(name: str, *costs: str) -> dict[str, object]:
    return {
        "name": name,
        "cost_components": [{"total_monthly_cost": cost} for cost in costs],
    }


def test_cost_table_shows_each_resource_per_scenario_with_totals() -> None:
    scan = {
        "projects": [
            {
                "project_name": "1-office",
                "resources": [
                    _resource("aws_lambda_function.bot", "0.05", "0.0006"),
                    # S3 nests its costs one level down, per storage class.
                    {
                        "name": "aws_s3_bucket.archive",
                        "subresources": [_resource("Standard", "0.1", "0.02")],
                    },
                    {"name": "aws_iam_role.lambda", "is_free": True},
                    {"name": "aws_scheduler_schedule.bot", "is_supported": False},
                ],
            },
            {
                "project_name": "all-us",
                "resources": [
                    _resource("aws_lambda_function.bot", "6.7", "0.15"),
                    {
                        "name": "aws_s3_bucket.archive",
                        "subresources": [_resource("Standard", "6.0")],
                    },
                ],
            },
        ]
    }

    assert cost_table(scan).splitlines() == [
        "Resource                     1-office      all-us",
        "aws_lambda_function.bot       $0.0506     $6.8500",
        "aws_s3_bucket.archive         $0.1200     $6.0000",
        "Total                         $0.1706    $12.8500",
    ]
