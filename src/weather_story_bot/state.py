"""DynamoDB record of which stories (and which revisions of them) have been posted."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from weather_story_bot.models import Story, parse_time


class Status(StrEnum):
    NEW = "new"
    UPDATED = "updated"
    SEEN = "seen"
    DUPLICATE = "duplicate"


def classify(story: Story, seen_update_time: str | None) -> Status:
    """Decide whether a story needs posting, given the `updateTime` recorded when last posted."""
    if seen_update_time is None:
        return Status.NEW
    if parse_time(seen_update_time) != story.update_time:
        return Status.UPDATED
    return Status.SEEN


def content_fingerprint(story: Story, image: bytes) -> str:
    """Identify a story revision by its image bytes and metadata, ignoring the image UUID.

    NWS can re-issue an unchanged story under a new UUID, so the UUID alone can't dedupe.
    `updateTime` is included so a revert to earlier content still counts as new.
    """
    content = {
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "title": story.title,
        "description": story.description,
        "start_time": story.start_time.astimezone(UTC).isoformat(),
        "end_time": story.end_time.astimezone(UTC).isoformat(),
        "update_time": story.update_time.astimezone(UTC).isoformat(),
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class PostedRecord:
    """The post that first carried a given content fingerprint."""

    image_id: str
    telegram_message_id: int
    archive_prefix: str


_FINGERPRINT_PREFIX = "content#"


class PostedStore:
    """Items keyed by `office_id` (partition) and `image_id` (sort).

    Each posted story also has a `content#<fingerprint>` item pointing at its post.
    """

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

    def find_by_fingerprint(self, office_id: str, fingerprint: str) -> PostedRecord | None:
        response = self._client.get_item(
            TableName=self._table,
            Key={
                "office_id": {"S": office_id},
                "image_id": {"S": _FINGERPRINT_PREFIX + fingerprint},
            },
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return None
        return PostedRecord(
            image_id=item["posted_image_id"]["S"],
            telegram_message_id=int(item["telegram_message_id"]["N"]),
            archive_prefix=item["archive_prefix"]["S"],
        )

    def record_posted(
        self,
        story: Story,
        message_id: int,
        archive_prefix: str,
        fingerprint: str,
        *,
        posted_at: datetime | None = None,
    ) -> None:
        posted_at = posted_at or datetime.now(UTC)
        common = {
            "office_id": {"S": story.office_id},
            "update_time": {"S": story.update_time.isoformat()},
            "title": {"S": story.title},
            "posted_at": {"S": posted_at.isoformat()},
            "telegram_message_id": {"N": str(message_id)},
            "archive_prefix": {"S": archive_prefix},
        }
        # Story item first: if the fingerprint write then fails, the story is still SEEN.
        self._client.put_item(
            TableName=self._table,
            Item={**common, "image_id": {"S": story.image_id}, "fingerprint": {"S": fingerprint}},
        )
        self._client.put_item(
            TableName=self._table,
            Item={
                **common,
                "image_id": {"S": _FINGERPRINT_PREFIX + fingerprint},
                "posted_image_id": {"S": story.image_id},
            },
        )

    def record_duplicate(
        self, story: Story, original: PostedRecord, *, seen_at: datetime | None = None
    ) -> None:
        """Mark a re-issued story as seen without posting it again."""
        seen_at = seen_at or datetime.now(UTC)
        self._client.put_item(
            TableName=self._table,
            Item={
                "office_id": {"S": story.office_id},
                "image_id": {"S": story.image_id},
                "update_time": {"S": story.update_time.isoformat()},
                "title": {"S": story.title},
                "duplicate_of": {"S": original.image_id},
                "duplicate_seen_at": {"S": seen_at.isoformat()},
                "telegram_message_id": {"N": str(original.telegram_message_id)},
                "archive_prefix": {"S": original.archive_prefix},
            },
        )
