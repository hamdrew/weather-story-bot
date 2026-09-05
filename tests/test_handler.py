import io
import json
import logging
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_runtime import Context, alarm_event, operations_config

from weather_story_bot import handler
from weather_story_bot.config import load_environment_config
from weather_story_bot.history import AttemptState
from weather_story_bot.operations import (
    AlertDeliveryOutcome,
    OfficeInformationService,
    OfficeRefreshResult,
)
from weather_story_bot.runtime import OperationsRuntime


def operation_runtime() -> OperationsRuntime:
    service = Mock(spec=OfficeInformationService)
    service.refresh.return_value = OfficeRefreshResult(
        office_id="MKX", outcome="refreshed", version=1
    )
    notifier = Mock()
    notifier.deliver_private_alert.return_value = AlertDeliveryOutcome.ACKNOWLEDGED
    return OperationsRuntime(
        operations_config(),
        load_environment_config(Path(__file__).parent.parent / "config/environments/dev.json"),
        service,
        notifier,
        lambda context: True,
        "mock",
        lambda office_id: None,
    )


def office_event(**updates: object) -> dict[str, object]:
    return {
        "environment": "dev",
        "office_id": "MKX",
        "operator_id": "operator",
        "correlation_id": "corr",
        **updates,
    }


def test_office_handler_uses_trusted_authorizer_and_returns_only_safe_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = operation_runtime()
    monkeypatch.setattr(handler, "_operations_runtime_factory", lambda: runtime)
    context = Context(runtime.config.office_function_arn)
    assert handler.office_information_handler(office_event(), context) == {"outcome": "refreshed"}
    denied = replace(runtime, office_authorizer=lambda context: False)
    monkeypatch.setattr(handler, "_operations_runtime_factory", lambda: denied)
    assert handler.office_information_handler(
        office_event(operator_id="administrator"), context
    ) == {"outcome": "rejected"}


@pytest.mark.parametrize(
    "event",
    [
        office_event(environment="prod"),
        office_event(office_id="GRB"),
        {"office_id": "MKX"},
        office_event(publish_story=True),
    ],
)
def test_office_handler_rejects_scope_before_service_calls(
    monkeypatch: pytest.MonkeyPatch, event: dict[str, object]
) -> None:
    runtime = operation_runtime()
    monkeypatch.setattr(handler, "_operations_runtime_factory", lambda: runtime)
    assert handler.office_information_handler(
        event, Context(runtime.config.office_function_arn)
    ) == {"outcome": "rejected"}
    assert isinstance(runtime.office_service, Mock)
    runtime.office_service.refresh.assert_not_called()


def test_operation_handlers_fail_closed_without_composition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(handler, "_operations_runtime_factory", None)
    assert handler.office_information_handler(office_event(), Context("function")) == {
        "outcome": "failed"
    }
    assert handler.alert_notification_handler(alarm_event(), Context("function")) == {
        "outcome": "failed"
    }


def test_alert_handler_redacts_primary_exceptions_and_never_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = io.StringIO()
    log_handler = logging.StreamHandler(output)
    monkeypatch.setattr(handler._operations_logger, "handlers", [log_handler])
    runtime = operation_runtime()
    assert isinstance(runtime.notifier, Mock)
    runtime.notifier.deliver_private_alert.side_effect = RuntimeError("UNTRUSTED upstream body")
    monkeypatch.setattr(handler, "_operations_runtime_factory", lambda: runtime)
    result = handler.alert_notification_handler(
        alarm_event(), Context(runtime.config.alert_function_arn)
    )
    assert result == {"outcome": "ambiguous", "fallback_outcome": "not_attempted"}
    runtime.notifier.deliver_fallback.assert_not_called()
    record = json.loads(output.getvalue())
    assert record["classification"] == "ambiguous"
    assert record["fallback_outcome"] == "not_attempted"
    assert record["request_id"] == "abc-def"
    assert "timestamp" in record
    assert "UNTRUSTED" not in output.getvalue()


def test_alert_handler_records_definitive_fallback_failure_without_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = operation_runtime()
    assert isinstance(runtime.notifier, Mock)
    runtime.notifier.deliver_private_alert.return_value = AlertDeliveryOutcome.DEFINITIVE_FAILURE
    runtime.notifier.deliver_fallback.side_effect = RuntimeError("mock unavailable")
    monkeypatch.setattr(handler, "_operations_runtime_factory", lambda: runtime)
    result = handler.alert_notification_handler(
        alarm_event(), Context(runtime.config.alert_function_arn)
    )
    assert result == {"outcome": "failed", "fallback_outcome": "failed"}
    runtime.notifier.deliver_private_alert.assert_called_once()
    runtime.notifier.deliver_fallback.assert_called_once()


def test_office_handler_reads_version_and_hides_boundary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = replace(operation_runtime(), office_version=lambda office_id: 3)
    assert isinstance(runtime.office_service, Mock)
    runtime.office_service.refresh.side_effect = RuntimeError("UNTRUSTED failure body")
    monkeypatch.setattr(handler, "_operations_runtime_factory", lambda: runtime)
    assert handler.office_information_handler(
        office_event(), Context(runtime.config.office_function_arn)
    ) == {"outcome": "failed"}
    assert runtime.office_service.refresh.call_args.kwargs["expected_version"] == 3


def test_alert_handler_wrong_function_and_deadline_do_not_deliver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = operation_runtime()
    monkeypatch.setattr(handler, "_operations_runtime_factory", lambda: runtime)
    assert handler.alert_notification_handler(alarm_event(), Context("other")) == {
        "outcome": "rejected"
    }
    assert handler.alert_notification_handler(
        alarm_event(), Context(runtime.config.alert_function_arn, remaining_ms=0)
    ) == {"outcome": "failed"}
    assert isinstance(runtime.notifier, Mock)
    runtime.notifier.deliver_private_alert.assert_not_called()


def test_runtime_refuses_live_ports_in_dev() -> None:
    with pytest.raises(ValueError, match="mode mismatch"):
        replace(operation_runtime(), telegram_mode="live")


def test_office_handler_authorizes_a_configured_non_default_office(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from weather_story_bot.config import EnvironmentConfig

    runtime = operation_runtime()
    environment = EnvironmentConfig.model_validate(
        runtime.environment.model_dump(exclude={"office_channels"})
        | {
            "active_office_ids": ["GRB"],
            "office_channels": {"GRB": "mock:grb"},
        }
    )
    runtime = replace(runtime, environment=environment)
    assert isinstance(runtime.office_service, Mock)
    runtime.office_service.refresh.return_value = OfficeRefreshResult(
        office_id="GRB", outcome="refreshed", version=1
    )
    monkeypatch.setattr(handler, "_operations_runtime_factory", lambda: runtime)
    assert handler.office_information_handler(
        office_event(office_id="GRB"), Context(runtime.config.office_function_arn)
    ) == {"outcome": "refreshed"}


def test_publisher_handler_passes_exactly_one_office_to_the_configured_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    class Runtime:
        def process_office(self, office_id: str) -> None:
            captured.append(office_id)

    monkeypatch.setattr(handler, "_publisher_runtime_factory", lambda: Runtime())

    handler.publisher_handler({"office_id": "MKX"}, object())
    assert captured == ["MKX"]


@pytest.mark.parametrize(
    "event",
    [{}, {"office_id": ""}, {"office_id": "MKX", "unexpected": True}],
)
def test_publisher_handler_rejects_anything_other_than_one_office_id(
    event: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="office"):
        handler.publisher_handler(event, object())


def test_reconciliation_handler_uses_a_configured_history_table_and_returns_safe_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeDynamoResource:
        def Table(self, name: str) -> object:
            captured["table_name"] = name
            return object()

    class FakeHistoryStore:
        def __init__(self, table: object) -> None:
            captured["table"] = table

        def reconcile_ambiguous_attempt(
            self,
            attempt_id: str,
            outcome: AttemptState,
            *,
            actor: str,
            reason: str,
            message_ref: str | None,
        ) -> bool:
            captured.update(
                attempt_id=attempt_id,
                outcome=outcome,
                actor=actor,
                reason=reason,
                message_ref=message_ref,
            )
            return True

    monkeypatch.setenv("HISTORY_TABLE_NAME", "weather-story-history")
    monkeypatch.setattr(
        "weather_story_bot.handler.boto3.resource", lambda service: FakeDynamoResource()
    )
    monkeypatch.setattr(handler, "HistoryStore", FakeHistoryStore)

    result = handler.reconciliation_handler(
        {
            "attempt_id": "attempt-1",
            "outcome": "confirmed_not_received",
            "operator_id": "operator@example.invalid",
            "reason": "No message was found.",
        },
        object(),
    )

    assert result == {
        "attempt_id": "attempt-1",
        "outcome": "confirmed_not_received",
        "reconciled": True,
    }
    assert captured == {
        "table_name": "weather-story-history",
        "table": captured["table"],
        "attempt_id": "attempt-1",
        "outcome": AttemptState.CONFIRMED_NOT_RECEIVED,
        "actor": "operator@example.invalid",
        "reason": "No message was found.",
        "message_ref": None,
    }


def test_reconciliation_handler_rejects_invalid_operator_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HISTORY_TABLE_NAME", "weather-story-history")

    with pytest.raises(ValueError, match="outcome"):
        handler.reconciliation_handler(
            {
                "attempt_id": "attempt-1",
                "outcome": "ambiguous",
                "operator_id": "operator@example.invalid",
                "reason": "No message was found.",
            },
            object(),
        )


def test_reconciliation_handler_rejects_an_unknown_outcome_before_accessing_dynamodb() -> None:
    with pytest.raises(ValueError, match="outcome"):
        handler.reconciliation_handler(
            {
                "attempt_id": "attempt-1",
                "outcome": "unexpected",
                "operator_id": "operator@example.invalid",
                "reason": "No message was found.",
            },
            object(),
        )


@pytest.mark.parametrize("message_ref", [1, object()])
def test_reconciliation_handler_rejects_non_string_message_references(message_ref: object) -> None:
    with pytest.raises(ValueError, match="message_ref"):
        handler.reconciliation_handler(
            {
                "attempt_id": "attempt-1",
                "outcome": "confirmed_received",
                "operator_id": "operator@example.invalid",
                "reason": "The message was found.",
                "message_ref": message_ref,
            },
            object(),
        )


def test_reconciliation_handler_requires_a_history_table_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HISTORY_TABLE_NAME", raising=False)

    with pytest.raises(RuntimeError, match="HISTORY_TABLE_NAME"):
        handler.reconciliation_handler(
            {
                "attempt_id": "attempt-1",
                "outcome": "confirmed_not_received",
                "operator_id": "operator@example.invalid",
                "reason": "No message was found.",
            },
            object(),
        )
    with pytest.raises(ValueError, match="operator_id"):
        handler.reconciliation_handler(
            {
                "attempt_id": "attempt-1",
                "outcome": "confirmed_not_received",
                "operator_id": "",
                "reason": "No message was found.",
            },
            object(),
        )
