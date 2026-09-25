"""DynamoDB record of which stories have been posted, and the message showing each one."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from weather_story_bot.models import Story

if TYPE_CHECKING:
    from types_boto3_dynamodb import DynamoDBClient
    from types_boto3_dynamodb.type_defs import AttributeValueTypeDef


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


def description_sha256(story: Story) -> str:
    """Hash the description alone, so an update can say which part of the content changed."""
    return hashlib.sha256(story.description.encode()).hexdigest()


def content_fingerprint(story: Story, image: bytes) -> str:
    """Identify what a story's Telegram message shows: the image bytes and description.

    Ignores the image UUID and `updateTime`, which NWS changes (even to the Unix epoch) on
    re-issues whose content is identical, and `endTime`, which the message doesn't show.
    Title and start time are the story's identity, compared through `story_key`.
    """
    return _sha256_json({"image_sha256": image_sha256(image), "description": story.description})


def story_key(story: Story) -> str:
    """Identify one story across revisions and image UUIDs: title plus start time."""
    return story_key_for(story.title, story.start_time)


def story_key_for(title: str, start_time: datetime) -> str:
    """`story_key` from a stored title and start time, for code that has no `Story`."""
    return _sha256_json({"title": title, "start_time": start_time.astimezone(UTC).isoformat()})


# Keys of the state table (backend/dynamodb-schema). Shared with scripts/migrate_table_keys.py,
# which must write exactly what this module reads.
SCHEMA_VERSION = 1


def office_pk(office_id: str) -> str:
    return f"OFFICE#{office_id}"


def story_sk(start_time: datetime, key: str) -> str:
    return f"STORY#{start_time.astimezone(UTC).isoformat()}#{key}"


@dataclass(frozen=True, slots=True)
class PostedRecord:
    """The latest posted revision of a story and the Telegram message showing it.

    `image_sha256` and `description_sha256` are the fingerprint's two inputs, kept so an update
    can say which one changed. Records written before 2026-09-24 don't have them.
    """

    image_id: str
    telegram_message_id: int
    archive_prefix: str
    fingerprint: str
    image_sha256: str | None = None
    description_sha256: str | None = None


class PostedStore:
    """One current-story item per posted story in the state table (backend/dynamodb-schema).

    Keyed `PK = OFFICE#<office_id>`, `SK = STORY#<start_utc_iso>#<story_key>`, and built from the
    `Story` alone, so a lookup and the write it follows can't disagree about the key.
    """

    def __init__(self, dynamodb_client: DynamoDBClient, table_name: str) -> None:
        self._client = dynamodb_client
        self._table = table_name

    def find_story(self, story: Story) -> PostedRecord | None:
        response = self._client.get_item(
            TableName=self._table,
            Key=_story_item_key(story),
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
            image_sha256=item["image_sha256"]["S"] if "image_sha256" in item else None,
            description_sha256=(
                item["description_sha256"]["S"] if "description_sha256" in item else None
            ),
        )

    def record_posted(
        self,
        story: Story,
        message_id: int,
        archive_prefix: str,
        fingerprint: str,
        *,
        image_sha256: str,
        posted_at: datetime | None = None,
    ) -> None:
        """Replace the story's record with the revision just posted."""
        posted_at = posted_at or datetime.now(UTC)
        item: dict[str, AttributeValueTypeDef] = {
            **_story_item_key(story),
            "schema_version": {"N": str(SCHEMA_VERSION)},
            "office_id": {"S": story.office_id},
            "story_key": {"S": story_key(story)},
            "posted_image_id": {"S": story.image_id},
            "title": {"S": story.title},
            "start_time": {"S": story.start_time.isoformat()},
            "end_time": {"S": story.end_time.isoformat()},
            "update_time": {"S": story.update_time.isoformat()},
            "posted_at": {"S": posted_at.isoformat()},
            "telegram_message_id": {"N": str(message_id)},
            "archive_prefix": {"S": archive_prefix},
            "fingerprint": {"S": fingerprint},
            "image_sha256": {"S": image_sha256},
            "description_sha256": {"S": description_sha256(story)},
        }
        self._client.put_item(TableName=self._table, Item=item)


def _story_item_key(story: Story) -> dict[str, AttributeValueTypeDef]:
    return {
        "PK": {"S": office_pk(story.office_id)},
        "SK": {"S": story_sk(story.start_time, story_key(story))},
    }
