"""DynamoDB record of which stories (and which revisions of them) have been posted."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from weather_story_bot.models import Story, parse_time


class Status(StrEnum):
    NEW = "new"
    UPDATED = "updated"
    SEEN = "seen"


def classify(story: Story, seen_update_time: str | None) -> Status:
    """Decide whether a story needs posting, given the `updateTime` recorded when last posted."""
    if seen_update_time is None:
        return Status.NEW
    if parse_time(seen_update_time) != story.update_time:
        return Status.UPDATED
    return Status.SEEN


class PostedStore:
    """Items keyed by `office_id` (partition) and `image_id` (sort)."""

    def __init__(self, dynamodb_client: Any, table_name: str) -> None:
        self._client = dynamodb_client
        self._table = table_name

    def get_update_time(self, office_id: str, image_id: str) -> str | None:
        response = self._client.get_item(
            TableName=self._table,
            Key={"office_id": {"S": office_id}, "image_id": {"S": image_id}},
            ProjectionExpression="update_time",
            ConsistentRead=True,
        )
        item = response.get("Item")
        return item["update_time"]["S"] if item else None

    def record_posted(
        self,
        story: Story,
        message_id: int,
        archive_prefix: str,
        *,
        posted_at: datetime | None = None,
    ) -> None:
        posted_at = posted_at or datetime.now(UTC)
        self._client.put_item(
            TableName=self._table,
            Item={
                "office_id": {"S": story.office_id},
                "image_id": {"S": story.image_id},
                "update_time": {"S": story.update_time.isoformat()},
                "title": {"S": story.title},
                "posted_at": {"S": posted_at.isoformat()},
                "telegram_message_id": {"N": str(message_id)},
                "archive_prefix": {"S": archive_prefix},
            },
        )
