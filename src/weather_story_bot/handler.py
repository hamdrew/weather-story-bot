"""Lambda entry points for the Weather Story service.

Business behavior is added in subsequent implementation tasks.  Keeping the
entry point importable establishes the package shape used by SAM packaging.
"""

import os
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

import boto3

from weather_story_bot.history import AttemptState, DynamoTable, HistoryStore


class PublisherRuntime(Protocol):
    """The fully composed, single-office scheduled publishing workflow."""

    def process_office(self, office_id: str) -> None: ...


PublisherRuntimeFactory = Callable[[], PublisherRuntime]
_publisher_runtime_factory: PublisherRuntimeFactory | None = None


def publisher_handler(event: Mapping[str, Any], context: object) -> None:
    """Process exactly the active office selected by one Scheduler invocation."""
    del context
    if set(event) != {"office_id"}:
        raise ValueError("publisher event must contain exactly one office_id")
    office_id = _required_event_text(event, "office_id")
    if _publisher_runtime_factory is None:
        raise RuntimeError("publisher runtime is not configured")
    _publisher_runtime_factory().process_office(office_id)


def reconciliation_handler(event: Mapping[str, Any], context: object) -> dict[str, object]:
    """Reconcile an ambiguous publication from an IAM-protected console or CLI invocation.

    The deployment grants invocation permission only to authorized operators. The
    supplied identity and reason form the durable reconciliation audit record.
    """
    del context
    attempt_id = _required_event_text(event, "attempt_id")
    actor = _required_event_text(event, "operator_id")
    reason = _required_event_text(event, "reason")
    outcome_text = _required_event_text(event, "outcome")
    try:
        outcome = AttemptState(outcome_text)
    except ValueError as error:
        raise ValueError("outcome must be confirmed_received or confirmed_not_received") from error
    if outcome not in {
        AttemptState.CONFIRMED_RECEIVED,
        AttemptState.CONFIRMED_NOT_RECEIVED,
    }:
        raise ValueError("outcome must be confirmed_received or confirmed_not_received")
    message_ref = event.get("message_ref")
    if message_ref is not None and not isinstance(message_ref, str):
        raise ValueError("message_ref must be a string when supplied")

    table_name = os.environ.get("HISTORY_TABLE_NAME")
    if not table_name:
        raise RuntimeError("HISTORY_TABLE_NAME is required")
    table = boto3.resource("dynamodb").Table(table_name)
    reconciled = HistoryStore(cast(DynamoTable, table)).reconcile_ambiguous_attempt(
        attempt_id,
        outcome,
        actor=actor,
        reason=reason,
        message_ref=message_ref,
    )
    return {"attempt_id": attempt_id, "outcome": outcome.value, "reconciled": reconciled}


def _required_event_text(event: Mapping[str, Any], field: str) -> str:
    value = event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value
