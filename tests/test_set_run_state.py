from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import boto3
import pytest
from moto import mock_aws

from scripts.set_run_state import RunStateError, main, set_run_state

if TYPE_CHECKING:
    from types_boto3_cloudwatch import CloudWatchClient
    from types_boto3_scheduler import EventBridgeSchedulerClient

SCHEDULE = "weather-story-bot-staging"
ALARMS = ["weather-story-bot-staging-errors", "weather-story-bot-staging-quiet"]
LAMBDA_ARN = "arn:aws:lambda:us-east-2:123456789012:function:weather-story-bot-staging"
ROLE_ARN = "arn:aws:iam::123456789012:role/weather-story-bot-staging-scheduler"
OUTPUTS: dict[str, Any] = {
    "schedule_name": {"value": SCHEDULE, "type": "string", "sensitive": False},
    "alarm_names": {"value": ALARMS, "type": ["list", "string"], "sensitive": False},
    "region": {"value": "us-east-2", "type": "string", "sensitive": False},
    "bucket_name": {"value": "ignored", "type": "string", "sensitive": False},
}


@pytest.fixture
def scheduler() -> Iterator[EventBridgeSchedulerClient]:
    with mock_aws():
        yield boto3.client("scheduler", region_name="us-east-2")


@pytest.fixture
def cloudwatch(scheduler: EventBridgeSchedulerClient) -> CloudWatchClient:
    return boto3.client("cloudwatch", region_name="us-east-2")


@pytest.fixture
def paused(scheduler: EventBridgeSchedulerClient, cloudwatch: CloudWatchClient) -> None:
    """A paused environment: a DISABLED schedule and alarms whose actions are off."""
    scheduler.create_schedule(
        Name=SCHEDULE,
        Description="Check for new NWS Weather Stories",
        ScheduleExpression="rate(15 minutes)",
        FlexibleTimeWindow={"Mode": "OFF"},
        State="DISABLED",
        Target={
            "Arn": LAMBDA_ARN,
            "RoleArn": ROLE_ARN,
            "RetryPolicy": {"MaximumRetryAttempts": 0},
        },
    )
    for name in ALARMS:
        cloudwatch.put_metric_alarm(
            AlarmName=name,
            Namespace="AWS/Lambda",
            MetricName="Invocations",
            Statistic="Sum",
            Period=3600,
            EvaluationPeriods=1,
            Threshold=1,
            ComparisonOperator="LessThanThreshold",
            ActionsEnabled=False,
            AlarmActions=["arn:aws:sns:us-east-2:123456789012:weather-story-bot-staging-alerts"],
        )


def schedule_state(scheduler: EventBridgeSchedulerClient) -> str:
    return scheduler.get_schedule(Name=SCHEDULE)["State"]


def actions_enabled(cloudwatch: CloudWatchClient) -> dict[str, bool]:
    alarms = cloudwatch.describe_alarms(AlarmNames=ALARMS)["MetricAlarms"]
    return {alarm["AlarmName"]: alarm["ActionsEnabled"] for alarm in alarms}


def test_start_enables_the_schedule_and_the_alarm_actions(
    paused: None, scheduler: EventBridgeSchedulerClient, cloudwatch: CloudWatchClient
) -> None:
    set_run_state(scheduler, cloudwatch, OUTPUTS, running=True, apply=True)

    assert schedule_state(scheduler) == "ENABLED"
    assert actions_enabled(cloudwatch) == {name: True for name in ALARMS}


def test_pause_disables_the_schedule_and_the_alarm_actions(
    paused: None, scheduler: EventBridgeSchedulerClient, cloudwatch: CloudWatchClient
) -> None:
    set_run_state(scheduler, cloudwatch, OUTPUTS, running=True, apply=True)

    set_run_state(scheduler, cloudwatch, OUTPUTS, running=False, apply=True)

    assert schedule_state(scheduler) == "DISABLED"
    assert actions_enabled(cloudwatch) == {name: False for name in ALARMS}


def test_a_toggle_keeps_the_rest_of_the_schedule_definition(
    paused: None, scheduler: EventBridgeSchedulerClient, cloudwatch: CloudWatchClient
) -> None:
    before = scheduler.get_schedule(Name=SCHEDULE)

    set_run_state(scheduler, cloudwatch, OUTPUTS, running=True, apply=True)

    after = scheduler.get_schedule(Name=SCHEDULE)
    for key in ("Description", "ScheduleExpression", "FlexibleTimeWindow", "Target", "GroupName"):
        assert after[key] == before[key], key


def test_dry_run_changes_nothing_and_reports_the_plan(
    paused: None, scheduler: EventBridgeSchedulerClient, cloudwatch: CloudWatchClient
) -> None:
    plan = set_run_state(scheduler, cloudwatch, OUTPUTS, running=True, apply=False)

    assert schedule_state(scheduler) == "DISABLED"
    assert actions_enabled(cloudwatch) == {name: False for name in ALARMS}
    assert plan.schedule_changes is True
    assert plan.alarms_to_change == ALARMS


def test_a_second_start_has_nothing_to_change(
    paused: None, scheduler: EventBridgeSchedulerClient, cloudwatch: CloudWatchClient
) -> None:
    set_run_state(scheduler, cloudwatch, OUTPUTS, running=True, apply=True)

    plan = set_run_state(scheduler, cloudwatch, OUTPUTS, running=True, apply=True)

    assert plan.schedule_changes is False
    assert plan.alarms_to_change == []


def test_only_the_alarms_that_differ_are_changed(
    paused: None, scheduler: EventBridgeSchedulerClient, cloudwatch: CloudWatchClient
) -> None:
    cloudwatch.enable_alarm_actions(AlarmNames=ALARMS[:1])

    plan = set_run_state(scheduler, cloudwatch, OUTPUTS, running=True, apply=False)

    assert plan.alarms_to_change == ALARMS[1:]


@pytest.mark.parametrize("missing", ["schedule_name", "alarm_names", "region"])
def test_a_missing_terraform_output_fails_before_touching_aws(
    paused: None,
    scheduler: EventBridgeSchedulerClient,
    cloudwatch: CloudWatchClient,
    missing: str,
) -> None:
    outputs = {key: value for key, value in OUTPUTS.items() if key != missing}

    with pytest.raises(RunStateError, match=missing):
        set_run_state(scheduler, cloudwatch, outputs, running=True, apply=True)

    assert schedule_state(scheduler) == "DISABLED"


def test_an_alarm_missing_from_cloudwatch_fails_before_changing_anything(
    scheduler: EventBridgeSchedulerClient, cloudwatch: CloudWatchClient, paused: None
) -> None:
    cloudwatch.delete_alarms(AlarmNames=ALARMS[1:])

    with pytest.raises(RunStateError, match=ALARMS[1]):
        set_run_state(scheduler, cloudwatch, OUTPUTS, running=True, apply=True)

    assert schedule_state(scheduler) == "DISABLED"
    assert actions_enabled(cloudwatch) == {ALARMS[0]: False}


def test_main_reads_terraform_outputs_from_a_file_and_toggles_when_applied(
    paused: None,
    scheduler: EventBridgeSchedulerClient,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs = tmp_path / "outputs.json"
    outputs.write_text(json.dumps(OUTPUTS))
    monkeypatch.setattr("scripts.set_run_state.session", lambda profile, region: boto3.Session())

    main(["start", str(outputs)])
    assert schedule_state(scheduler) == "DISABLED"

    main(["start", "--apply", str(outputs)])
    assert schedule_state(scheduler) == "ENABLED"
