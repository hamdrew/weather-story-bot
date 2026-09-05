import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from weather_story_bot.config import OfficeRegistry, OperationsConfig
from weather_story_bot.runtime import (
    InvocationBudget,
    load_operations_config,
    load_publisher_runtime_settings,
    parse_alarm_notification,
)


def operations_config() -> OperationsConfig:
    prefix = "arn:aws:"
    scope = "us-east-2:123456789012:"
    return OperationsConfig(
        environment="dev",
        account_id="123456789012",
        office_function_arn=prefix + "lambda:" + scope + "function:weather-story-dev-office",
        alert_function_arn=prefix + "lambda:" + scope + "function:weather-story-dev-alert",
        trigger_topic_arn=prefix + "sns:" + scope + "weather-story-dev-trigger",
        fallback_topic_arn=prefix + "sns:" + scope + "weather-story-dev-fallback",
        alarm_names=("weather-story-dev-office-failed",),
    )


def alarm_event(**overrides: object) -> dict[str, object]:
    config = operations_config()
    alarm = {
        "AlarmName": config.alarm_names[0],
        "AlarmArn": (
            f"arn:aws:cloudwatch:us-east-2:{config.account_id}:alarm:{config.alarm_names[0]}"
        ),
        "AWSAccountId": config.account_id,
        "NewStateValue": "ALARM",
        "OldStateValue": "OK",
        "StateChangeTime": "2026-09-04T00:00:00Z",
        "NewStateReason": "UNTRUSTED upstream diagnostic text",
        **overrides,
    }
    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "EventSubscriptionArn": config.trigger_topic_arn + ":subscription",
                "Sns": {
                    "Type": "Notification",
                    "TopicArn": config.trigger_topic_arn,
                    "Message": json.dumps(alarm),
                    "Timestamp": "2026-09-04T00:00:01Z",
                },
            }
        ]
    }


@dataclass
class Context:
    invoked_function_arn: str
    aws_request_id: str = "abc-def"
    remaining_ms: int = 30_000

    def get_remaining_time_in_millis(self) -> int:
        return self.remaining_ms


def test_operation_configuration_loads_through_pydantic() -> None:
    config = operations_config()
    assert load_operations_config({"OPERATIONS_CONFIG": config.model_dump_json()}) == config


@pytest.mark.parametrize(
    "updates",
    [
        {"fallback_topic_arn": operations_config().trigger_topic_arn},
        {"office_function_arn": operations_config().alert_function_arn},
        {"environment": "staging"},
        {"alarm_names": []},
        {"alarm_names": ["foreign-alarm"]},
        {"account_id": "000000000000"},
        {"region": "us-east-1"},
    ],
)
def test_operation_configuration_rejects_cross_scope_resources(updates: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        OperationsConfig.model_validate(operations_config().model_dump() | updates)


def test_alarm_envelope_projects_only_safe_context() -> None:
    alarm = parse_alarm_notification(alarm_event(), operations_config())
    assert alarm.summary == "CloudWatch alarm entered ALARM"
    assert "UNTRUSTED" not in alarm.model_dump_json()


def test_alarm_envelope_refuses_fallback_topic_as_a_source() -> None:
    event = alarm_event()
    records = event["Records"]
    assert isinstance(records, list)
    records[0]["Sns"]["TopicArn"] = operations_config().fallback_topic_arn
    with pytest.raises(ValueError, match="not authorized"):
        parse_alarm_notification(event, operations_config())


def test_production_runtime_rejects_debug() -> None:
    values = operations_config().model_dump_json().replace("dev", "prod")
    config = OperationsConfig.model_validate_json(values)
    with pytest.raises(ValueError, match="DEBUG"):
        OperationsConfig.model_validate(config.model_dump() | {"log_level": "DEBUG"})


@pytest.mark.parametrize(
    "updates",
    [
        {"NewStateValue": "OK"},
        {"OldStateValue": "ALARM"},
        {"AWSAccountId": "000000000000"},
        {"AlarmName": "unknown"},
        {"AlarmArn": "foreign"},
        {"StateChangeTime": "not-a-time"},
        {"StateChangeTime": "2026-09-04T00:00:00"},
    ],
)
def test_alarm_envelope_rejects_non_actionable_or_foreign_alarms(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        parse_alarm_notification(alarm_event(**updates), operations_config())


@pytest.mark.parametrize(
    "event",
    [{}, {"Records": []}, {"Records": [{}, {}]}, {"Records": [{}]}, {"extra": "a" * 16_385}],
)
def test_alarm_envelope_rejects_malformed_or_unbounded_payloads(event: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        parse_alarm_notification(event, operations_config())


@pytest.mark.parametrize("remaining", [0, 11_999, 12_000])
def test_invocation_budget_reserves_a_complete_attempt(remaining: int) -> None:
    budget = InvocationBudget(Context("function", remaining_ms=remaining))
    if remaining < 12_000:
        with pytest.raises(TimeoutError):
            budget.check()
    else:
        budget.check()


def _registry() -> OfficeRegistry:
    return OfficeRegistry.model_validate(
        {
            "schema_version": 1,
            "offices": [
                {
                    "office_id": "MKX",
                    "weather_stories_url": "https://api.weather.gov/offices/MKX/weatherstories",
                    "display_name": "Milwaukee/Sullivan, WI",
                    "address": {
                        "street_address": "N3533 Hardscrabble Road",
                        "locality": "Dousman",
                        "region": "WI",
                        "postal_code": "53118",
                    },
                    "coordinates": {"latitude": 43.04, "longitude": -88.46},
                    "timezone": "America/Chicago",
                    "telegram_channel_id": "mock:weather-story-mkx",
                    "active": True,
                }
            ],
        }
    )


def _environment(tmp_path: Path) -> dict[str, str]:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(_registry().model_dump_json(), encoding="utf-8")
    return {
        "OFFICE_REGISTRY_PATH": str(registry_path),
        "ENVIRONMENT_CONFIG_PATH": str(
            Path(__file__).parent.parent / "config/environments/dev.json"
        ),
        "HISTORY_TABLE_NAME": "weather-story-dev-history",
        "IMAGE_BUCKET_NAME": "weather-story-dev-images",
        "ALERT_TRIGGER_TOPIC_ARN": "arn:aws:sns:us-east-2:123456789012:weather-story-dev-alerts",
        "TELEGRAM_SECRET_ARN": "arn:aws:secretsmanager:us-east-2:123456789012:secret:dev",
    }


def test_load_publisher_runtime_settings_validates_packaged_configuration(tmp_path: Path) -> None:
    settings = load_publisher_runtime_settings(_environment(tmp_path))

    assert settings.environment.environment == "dev"
    assert tuple(office.office_id for office in settings.registry.offices if office.active) == (
        "MKX",
    )
    assert settings.history_table_name == "weather-story-dev-history"


def test_load_publisher_runtime_settings_rejects_missing_resource_reference(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    del environment["IMAGE_BUCKET_NAME"]

    with pytest.raises(RuntimeError, match="IMAGE_BUCKET_NAME"):
        load_publisher_runtime_settings(environment)


def test_load_publisher_runtime_settings_rejects_mismatched_active_registry(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    registry_path = Path(environment["OFFICE_REGISTRY_PATH"])
    registry = _registry().model_copy(
        update={"offices": (_registry().offices[0].model_copy(update={"active": False}),)}
    )
    registry_path.write_text(registry.model_dump_json(), encoding="utf-8")

    with pytest.raises(RuntimeError, match="active offices"):
        load_publisher_runtime_settings(environment)
