"""DynamoDB record of which stories have been posted, and the message showing each one."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from weather_story_bot.models import Story

if TYPE_CHECKING:
    from types_boto3_dynamodb import DynamoDBClient


class Status(StrEnum):
    NEW = "new"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


def _sha256_json(content: dict[str, str]) -> str:
    # Frozen. This encoding is baked into every stored story_key and content_fingerprint;
    # changing it (even to json.dumps' own defaults) changes every digest, making stored
    # records unreachable and reposting every active story. See backend/story-identity.md.
    encoded = json.dumps(
        content, sort_keys=True, separators=(", ", ": "), ensure_ascii=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def image_sha256(image: bytes) -> str:
    return hashlib.sha256(image).hexdigest()


def content_fingerprint(story: Story, image: bytes) -> str:
    """Identify what a story's Telegram message shows: the image bytes and description.

    Ignores the image UUID and `updateTime`, which NWS changes (even to the Unix epoch) on
    re-issues whose content is identical, and `endTime`, which the message doesn't show.
    Title and start time are the story's identity, compared through `story_key`.
    """
    return _sha256_json({"image_sha256": image_sha256(image), "description": story.description})


def story_key(story: Story) -> str:
    """Identify one story across revisions and image UUIDs: title plus start time."""
    return _sha256_json(
        {"title": story.title, "start_time": story.start_time.astimezone(UTC).isoformat()}
    )


@dataclass(frozen=True, slots=True)
class PostedRecord:
    """The latest posted revision of a story and the Telegram message showing it."""

    image_id: str
    telegram_message_id: int
    archive_prefix: str
    fingerprint: str


_STORY_PREFIX = "story#"


class PostedStore:
    """One `story#<story_key>` item per posted story, keyed by `office_id` (partition).

    The sort key attribute is still named `image_id`. Items from before 2026-09-15 (keyed by
    image UUID or `content#<fingerprint>`) are no longer read.
    """

    def __init__(self, dynamodb_client: DynamoDBClient, table_name: str) -> None:
        self._client = dynamodb_client
        self._table = table_name

    def find_story(self, office_id: str, key: str) -> PostedRecord | None:
        response = self._client.get_item(
            TableName=self._table,
            Key={"office_id": {"S": office_id}, "image_id": {"S": _STORY_PREFIX + key}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return None
        return PostedRecord(
            image_id=item["posted_image_id"]["S"],
            telegram_message_id=int(item["telegram_message_id"]["N"]),
            archive_prefix=item["archive_prefix"]["S"],
            fingerprint=item["fingerprint"]["S"],
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
        self._client.put_item(
            TableName=self._table,
            Item={
                "office_id": {"S": story.office_id},
                "image_id": {"S": _STORY_PREFIX + story_key(story)},
                "posted_image_id": {"S": story.image_id},
                "title": {"S": story.title},
                "start_time": {"S": story.start_time.isoformat()},
                "end_time": {"S": story.end_time.isoformat()},
                "update_time": {"S": story.update_time.isoformat()},
                "posted_at": {"S": posted_at.isoformat()},
                "telegram_message_id": {"N": str(message_id)},
                "archive_prefix": {"S": archive_prefix},
                "fingerprint": {"S": fingerprint},
            },
        )
