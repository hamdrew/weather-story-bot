"""Write Infracost usage files for `make cost`: one office, a handful, and every US office.

Infracost can't read usage from Terraform, so each scenario gets a usage file built from the same
per-office monthly rates below, multiplied by its office count. Keeping the rates in one place
means the three estimates can't drift apart. Values are estimates, not measurements, except where
a comment says "measured".

    uv run python scripts/infracost_usage.py write build   # build/infracost-usage-<name>.yml
    uv run python scripts/infracost_usage.py report build/infracost.json

`make cost` writes the files, `infracost scan` prices each as its own project (infracost.yml), and
`report` prints the scenarios side by side. The usage files are JSON, which is valid YAML.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --- Base assumptions, per office per month. Update these first. ---

RUNS = 2880  # rate(15 minutes) = 4/hour * 24 * 30 days
STORIES_PER_RUN = 2  # active stories NWS lists per office; MKX usually has 1-3
# Measured on MKX 2026-09-13 to 2026-09-26: 58 archived posts in ~14 days, across 54 stories.
POSTS = 125  # new and updated reposts together
UPDATES = 10  # of POSTS, reposts that replace an earlier message
# Allowance: one ambiguous story stuck for 3 days, which writes a `rejected` event every run
# (96 a day). None were seen in the first two weeks, so this is headroom, not a measurement.
REJECTIONS = 3 * 96
# Measured: 3.8 s average Lambda duration for one office, 2026-09-19 to 2026-09-26. Every scenario
# is priced as one invocation per office per run, the design offices are moving to (Phase 2.2).
# That also keeps the scaled estimates realistic: at 3.8 s an office, one invocation for all 122
# would run far past the 300 s Lambda timeout.
RUN_SECONDS_PER_OFFICE = 3.8
ARCHIVE_MONTHS = 12  # S3 and DynamoDB grow forever, so storage is priced after a year

PNG_MB = 1.64  # measured average archived image
JSON_KB = 0.9  # measured average archived story JSON
# DynamoDB item sizes, all under 1 KB, so every write is 1 WRU and every GetItem 1 RRU. Storage
# counts a story item per post, though an update overwrites one: close enough at 0.7 KB.
RUN_ITEM_KB = 0.4
STORY_ITEM_KB = 0.7
EVENT_ITEM_KB = 0.5
# CloudWatch Logs: START/END/REPORT plus `Run complete` per invocation, and the `Telegram message
# sent` and `Story posted` lines per post. Checked against ~97 KB of log messages a day for MKX.
INVOCATION_LOG_BYTES = 1000
POST_LOG_BYTES = 1000

# Monthly DynamoDB writes for one office:
WRITES_PER_OFFICE = (
    RUNS * 2  # office lease: conditional PutItem to take it, DeleteItem to release it
    + RUNS  # RUN# record
    + STORIES_PER_RUN * 24 * 30  # last_seen_at UpdateItem, at most hourly per unchanged story
    + POSTS  # last_seen_at again on the run after a post, since record_posted clears it
    + POSTS * 2  # current-story PutItem + posted/updated ledger event
    + UPDATES  # deleted/delete_failed event for the replaced message
    + REJECTIONS  # rejected ledger event
)
READS_PER_OFFICE = RUNS * STORIES_PER_RUN  # strongly consistent GetItem per active story
EVENTS_PER_OFFICE = POSTS + UPDATES + REJECTIONS

KB_PER_GB = 1024 * 1024


@dataclass(frozen=True)
class Scenario:
    name: str
    offices: int


SCENARIOS = (
    Scenario("1-office", 1),  # MKX today
    Scenario("6-offices", 6),  # MKX, GRB, ARX, DLH, MPX, LOT: Wisconsin and neighbours
    Scenario("all-us", 122),  # every NWS Weather Forecast Office
)


def usage(scenario: Scenario) -> dict[str, dict[str, Any]]:
    """Monthly Infracost usage for every usage-priced resource in infra/, keyed by address."""
    n = scenario.offices
    invocations = n * RUNS

    table_kb = ARCHIVE_MONTHS * (
        RUNS * RUN_ITEM_KB + POSTS * STORY_ITEM_KB + EVENTS_PER_OFFICE * EVENT_ITEM_KB
    )
    table_gb = round(n * table_kb / KB_PER_GB, 4)
    archive_gb = round(n * ARCHIVE_MONTHS * POSTS * (PNG_MB / 1024 + JSON_KB / KB_PER_GB), 3)
    log_bytes = invocations * INVOCATION_LOG_BYTES + n * POSTS * POST_LOG_BYTES
    log_gb = round(log_bytes / 1024**3, 4)

    return {
        "aws_lambda_function.bot": {
            "monthly_requests": invocations,
            "request_duration_ms": round(RUN_SECONDS_PER_OFFICE * 1000),
        },
        "aws_dynamodb_table.state": {
            "monthly_read_request_units": n * READS_PER_OFFICE,
            "monthly_write_request_units": n * WRITES_PER_OFFICE,
            # Infracost prices anything under 1 GB as $0 (the real cost is a fraction of a cent).
            "storage_gb": table_gb,
            "pitr_backup_storage_gb": table_gb,  # PITR is billed on table size
        },
        # The MVP table: no traffic since the flip, kept (a few KB) until it's removed.
        "aws_dynamodb_table.posted": {
            "monthly_read_request_units": 0,
            "monthly_write_request_units": 0,
            "storage_gb": 0.001,
            "pitr_backup_storage_gb": 0.001,
        },
        "aws_s3_bucket.archive": {
            "standard": {
                "storage_gb": archive_gb,
                "monthly_tier_1_requests": n * POSTS * 2,  # PutObject for .png and .json
            },
        },
        "aws_cloudwatch_log_group.lambda": {
            "monthly_data_ingested_gb": log_gb,
            "storage_gb": log_gb,  # 30-day retention keeps about one month
        },
    }


def write_usage_files(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for scenario in SCENARIOS:
        path = out_dir / f"infracost-usage-{scenario.name}.yml"
        body = {"version": "0.1", "resource_usage": usage(scenario)}
        path.write_text(json.dumps(body, indent=2) + "\n")


def cost_table(scan: Mapping[str, Any]) -> str:
    """Full-precision monthly cost of each costed resource, one column per scenario, with totals.

    Infracost's own tables round to whole dollars, which shows `$0` for nearly everything here.
    """
    names = [project["project_name"] for project in scan["projects"]]
    costs: dict[str, dict[str, float]] = {}
    for project in scan["projects"]:
        for resource in project["resources"]:
            # Unsupported means unpriced, not free (the scheduler: see the spec's cost record).
            if resource.get("is_free") or resource.get("is_supported") is False:
                continue
            costs.setdefault(resource["name"], {})[project["project_name"]] = _cost(resource)
    totals = {name: sum(row.get(name, 0.0) for row in costs.values()) for name in names}

    width = max(len(address) for address in [*costs, "Resource"]) + 2
    lines = ["Resource".ljust(width) + "".join(f"{name:>12}" for name in names)]
    for address, row in [*sorted(costs.items()), ("Total", totals)]:
        dollars = [f"${row.get(name, 0.0):.4f}" for name in names]
        lines.append(address.ljust(width) + "".join(f"{cell:>12}" for cell in dollars))
    return "\n".join(lines)


def _cost(resource: Mapping[str, Any]) -> float:
    """A resource's monthly cost, including subresources (S3 prices each storage class as one)."""
    own = sum(float(c["total_monthly_cost"]) for c in resource.get("cost_components", []))
    return own + sum(_cost(sub) for sub in resource.get("subresources", []))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write", help="write one usage file per scenario")
    write.add_argument("out_dir", type=Path, help="directory for the usage files, e.g. build")
    report = commands.add_parser("report", help="print the cost table from a scan")
    report.add_argument("scan", type=Path, help="`infracost scan --json` output")
    args = parser.parse_args()
    if args.command == "write":
        write_usage_files(args.out_dir)
    else:
        print(cost_table(json.loads(args.scan.read_text())))


if __name__ == "__main__":
    main()
