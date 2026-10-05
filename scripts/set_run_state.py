"""Start or pause an environment: its EventBridge schedule and its alarm actions (2026-10-02).

Terraform creates the schedule DISABLED and the alarms with their actions on, and ignores both
settings afterwards (`infra/environments`), so this is what changes them. An apply never undoes
a start or a pause.

- **start** enables the schedule, then the alarm actions. The schedule has no StartDate, so
  EventBridge fires it at once, then every interval.
- **pause** disables the alarm actions, then the schedule, so a paused environment's alarms can't
  email about the idleness they cause.

Pausing keeps the alarms and their state. `missed-runs` and `quiet` treat missing data as
breaching, so a paused environment's two sit in ALARM without emailing. A new environment is the
reverse: its alarms are on while its schedule is off, so those two email until you start it.
Starting re-enables their actions, and the first runs then bring them back to OK with an OK email.

Reads `terraform output -json` for the schedule name, alarm names and region, and changes nothing
unless --apply is given. Idempotent: whatever already matches is left alone. The schedule is
updated with its current definition, because `update-schedule` replaces the whole schedule.

    TF_DATA_DIR=.terraform-staging terraform -chdir=infra output -json | \\
        uv run python scripts/set_run_state.py start --apply -

`make start ENV=<env>` and `make pause ENV=<env>` run exactly that. Credentials come from the
weather-deploy profile Terraform uses (MFA), which prompts for a code in a real terminal.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from botocore.exceptions import BotoCoreError, ClientError

if TYPE_CHECKING:
    import boto3
    from types_boto3_cloudwatch import CloudWatchClient
    from types_boto3_scheduler import EventBridgeSchedulerClient

type ScheduleState = Literal["ENABLED", "DISABLED"]

DEFAULT_PROFILE = "weather-deploy"
# What get_schedule returns that update_schedule accepts back. An allowlist, so a new read-only
# field in the response (ResponseMetadata, Arn, CreationDate) never reaches the update.
SCHEDULE_PARAMETERS = (
    "Name",
    "GroupName",
    "Description",
    "ScheduleExpression",
    "ScheduleExpressionTimezone",
    "FlexibleTimeWindow",
    "Target",
    "StartDate",
    "EndDate",
    "KmsKeyArn",
    "ActionAfterCompletion",
)


class RunStateError(Exception):
    """The environment can't be toggled. The message says what, if anything, already changed."""


@dataclass(frozen=True)
class Plan:
    schedule_name: str
    schedule_changes: bool
    alarms_to_change: list[str]


def set_run_state(
    scheduler: EventBridgeSchedulerClient,
    cloudwatch: CloudWatchClient,
    outputs: Mapping[str, Any],
    *,
    running: bool,
    apply: bool,
) -> Plan:
    """Bring the schedule and the alarm actions to `running`, or only plan it when not `apply`."""
    schedule_name = _output(outputs, "schedule_name")
    alarm_names = _output(outputs, "alarm_names")
    _output(outputs, "region")

    schedule = scheduler.get_schedule(Name=schedule_name)
    wanted_state: ScheduleState = "ENABLED" if running else "DISABLED"
    alarms = _alarm_actions(cloudwatch, alarm_names)
    plan = Plan(
        schedule_name=schedule_name,
        schedule_changes=schedule["State"] != wanted_state,
        alarms_to_change=[name for name in alarm_names if alarms[name] != running],
    )
    if not apply:
        return plan

    def toggle_schedule() -> str | None:
        if plan.schedule_changes:
            _set_schedule(scheduler, schedule, wanted_state)
            return f"schedule {schedule_name} {wanted_state}"
        return None

    def toggle_alarms() -> str | None:
        if plan.alarms_to_change:
            _set_alarms(cloudwatch, plan.alarms_to_change, running)
            state = "on" if running else "off"
            return f"alarm actions {state} for {', '.join(plan.alarms_to_change)}"
        return None

    # Start: the schedule first, so the alarms are never live ahead of the runs they watch.
    # Pause: the alarms first, so the idleness the pause causes can't email.
    changed: list[str] = []
    for step in (toggle_schedule, toggle_alarms) if running else (toggle_alarms, toggle_schedule):
        try:
            done = step()
        except (BotoCoreError, ClientError) as error:
            already = "; ".join(changed) or "nothing"
            raise RunStateError(
                f"{error}. Already changed: {already}. It's idempotent, so rerun it to finish"
            ) from error
        if done:
            changed.append(done)
    return plan


def _output(outputs: Mapping[str, Any], name: str) -> Any:
    try:
        return outputs[name]["value"]
    except (KeyError, TypeError):
        raise RunStateError(
            f"Terraform output {name!r} is missing; deploy this environment first so it exists"
        ) from None


def _alarm_actions(cloudwatch: CloudWatchClient, alarm_names: list[str]) -> dict[str, bool]:
    """ActionsEnabled per alarm; every named alarm must exist."""
    found: dict[str, bool] = {}
    pages = cloudwatch.get_paginator("describe_alarms")
    for start in range(0, len(alarm_names), 100):
        # Paged: a request may name 100 alarms, but a response can hold fewer and a NextToken.
        for page in pages.paginate(
            AlarmNames=alarm_names[start : start + 100], AlarmTypes=["MetricAlarm"]
        ):
            found.update({a["AlarmName"]: a["ActionsEnabled"] for a in page["MetricAlarms"]})
    if missing := [name for name in alarm_names if name not in found]:
        raise RunStateError(f"CloudWatch has no alarm named {', '.join(missing)}")
    return found


def _set_schedule(
    scheduler: EventBridgeSchedulerClient, schedule: Mapping[str, Any], state: ScheduleState
) -> None:
    definition = {key: schedule[key] for key in SCHEDULE_PARAMETERS if key in schedule}
    scheduler.update_schedule(**definition, State=state)


def _set_alarms(cloudwatch: CloudWatchClient, alarm_names: list[str], enabled: bool) -> None:
    for start in range(0, len(alarm_names), 100):
        batch = alarm_names[start : start + 100]
        if enabled:
            cloudwatch.enable_alarm_actions(AlarmNames=batch)
        else:
            cloudwatch.disable_alarm_actions(AlarmNames=batch)


def session(profile: str, region: str) -> boto3.Session:
    import boto3  # Dev-only dependency.

    return boto3.Session(profile_name=profile, region_name=region)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Start or pause an environment's schedule.")
    parser.add_argument("command", choices=["start", "pause"])
    parser.add_argument("outputs", help="`terraform output -json` file, or - for stdin")
    parser.add_argument("--apply", action="store_true", help="make the change (default: dry run)")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    args = parser.parse_args(argv)

    running = args.command == "start"
    try:
        outputs = json.loads(
            sys.stdin.read() if args.outputs == "-" else Path(args.outputs).read_text()
        )
        region = _output(outputs, "region")
        boto = session(args.profile, region)
        plan = set_run_state(
            boto.client("scheduler"),
            boto.client("cloudwatch"),
            outputs,
            running=running,
            apply=args.apply,
        )
    except RunStateError as error:
        sys.exit(f"{error}")

    verb = "Started" if running else "Paused"
    if not args.apply:
        verb = f"Would {args.command}"
    schedule = "its schedule" if plan.schedule_changes else "no schedule change"
    alarms = ", ".join(plan.alarms_to_change) or "no alarm change"
    print(f"{verb} {plan.schedule_name}: {schedule}; alarm actions: {alarms}")
    if not args.apply:
        print("Dry run. Pass --apply to make the change.")


if __name__ == "__main__":
    main()
