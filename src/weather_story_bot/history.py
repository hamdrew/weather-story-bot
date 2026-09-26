"""Append-only history in the state table: what the bot did, and when it could see NWS.

Best-effort on purpose, and kept out of `state.py`, which is the safety chain. A failed history
write logs a WARNING and returns; it never raises for AWS errors and never blocks a post. See
`backend/dynamodb-schema` for the item keys.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from botocore.exceptions import BotoCoreError, ClientError

from weather_story_bot.models import Story
from weather_story_bot.state import (
    SCHEMA_VERSION,
    event_sk,
    office_pk,
    run_sk,
    story_item_key,
    story_key,
    utc_timestamp,
)

if TYPE_CHECKING:
    from types_boto3_dynamodb import DynamoDBClient
    from types_boto3_dynamodb.type_defs import AttributeValueTypeDef

logger = logging.getLogger(__name__)

# How stale `last_seen_at` may get before a run rewrites it: one write per story per hour instead
# of one per run. Pulled-early stories show up as `last_seen_at` well before `end_time`.
LAST_SEEN_INTERVAL = timedelta(hours=1)


class EventKind(StrEnum):
    POSTED = "posted"
    UPDATED = "updated"
    REJECTED = "rejected"
    DELETED = "deleted"
    DELETE_FAILED = "delete_failed"


class StoryHistory:
    """Ledger events, story sightings and run records (backend/dynamodb-schema)."""

    def __init__(self, dynamodb_client: DynamoDBClient, table_name: str) -> None:
        self._client = dynamodb_client
        self._table = table_name

    def record_event(
        self,
        story: Story,
        kind: EventKind,
        *,
        at: datetime,
        fingerprint: str | None = None,
        telegram_message_id: int | None = None,
        reasons: Sequence[str] = (),
    ) -> None:
        """Write one immutable ledger event about one revision of a story.

        `at` is when the action happened; read the clock per event, since it is part of the key.
        An event never overwrites another: a key collision is a failed write, not a replacement.
        Events hold only the revision they are about. What an update changed is derived from
        consecutive events at analysis time, never stored (`global/principles`).
        """
        key = story_key(story)
        item: dict[str, AttributeValueTypeDef] = {
            "PK": {"S": office_pk(story.office_id)},
            "SK": {"S": event_sk(story.start_time, key, at)},
            "schema_version": {"N": str(SCHEMA_VERSION)},
            "office_id": {"S": story.office_id},
            "story_key": {"S": key},
            "event": {"S": kind},
            "event_at": {"S": utc_timestamp(at)},
            "image_id": {"S": story.image_id},
            "title": {"S": story.title},
            "start_time": {"S": story.start_time.isoformat()},
            "end_time": {"S": story.end_time.isoformat()},
            "update_time": {"S": story.update_time.isoformat()},
        }
        if fingerprint is not None:
            item["fingerprint"] = {"S": fingerprint}
        if telegram_message_id is not None:
            item["telegram_message_id"] = {"N": str(telegram_message_id)}
        if reasons:
            item["reasons"] = {"L": [{"S": reason} for reason in reasons]}
        try:
            self._client.put_item(
                TableName=self._table,
                Item=item,
                ConditionExpression="attribute_not_exists(PK)",
            )
        except (BotoCoreError, ClientError) as exc:
            _log_failure("event", story.office_id, exc, image_id=story.image_id)

    def touch_last_seen(
        self, story: Story, last_seen_at: datetime | None, *, now: datetime
    ) -> None:
        """Set `last_seen_at` on the story's current item, if the stored value is an hour stale.

        `last_seen_at` is the value the caller already read with the record, so a fresh story
        costs no request at all. Never creates an item: a story with no record isn't touched.
        """
        if last_seen_at is not None and now - last_seen_at < LAST_SEEN_INTERVAL:
            return
        try:
            self._client.update_item(
                TableName=self._table,
                Key=story_item_key(story),
                UpdateExpression="SET last_seen_at = :now",
                ConditionExpression="attribute_exists(PK)",
                ExpressionAttributeValues={":now": {"S": utc_timestamp(now)}},
            )
        except (BotoCoreError, ClientError) as exc:
            if _is_condition_failure(exc):
                return  # No record to touch; the story was never posted.
            _log_failure("last_seen", story.office_id, exc, image_id=story.image_id)

    def record_run(
        self,
        office_id: str,
        *,
        at: datetime,
        nws_failed: bool,
        stories_seen: int,
        counts: Mapping[str, int],
        aws_request_id: str | None = None,
    ) -> None:
        """Write one immutable record of one office's run: when, whether NWS answered, and counts.

        Raw runs, not daily totals: outages, days and per-office baselines are derived from these
        at analysis time, so they don't depend on the schedule's cadence. A duplicate run is its
        own record.
        """
        item: dict[str, AttributeValueTypeDef] = {
            "PK": {"S": office_pk(office_id)},
            "SK": {"S": run_sk(at)},
            "schema_version": {"N": str(SCHEMA_VERSION)},
            "office_id": {"S": office_id},
            "run_at": {"S": utc_timestamp(at)},
            "nws_failed": {"BOOL": nws_failed},
            "stories_seen": {"N": str(stories_seen)},
            **{name: {"N": str(count)} for name, count in counts.items()},
        }
        if aws_request_id is not None:
            item["aws_request_id"] = {"S": aws_request_id}
        try:
            self._client.put_item(
                TableName=self._table,
                Item=item,
                ConditionExpression="attribute_not_exists(PK)",
            )
        except (BotoCoreError, ClientError) as exc:
            _log_failure("run", office_id, exc)


def _is_condition_failure(exc: Exception) -> bool:
    return (
        isinstance(exc, ClientError)
        and exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"
    )


def _log_failure(write: str, office_id: str, exc: Exception, **extra: str) -> None:
    # This module's logger isn't handler's, so its lines don't get `office` from the filter.
    logger.warning(
        "History write failed",
        extra={"history_write": write, "office": office_id, "error": str(exc), **extra},
    )
