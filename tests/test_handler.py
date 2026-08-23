import pytest

from weather_story_bot import handler
from weather_story_bot.history import AttemptState


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
