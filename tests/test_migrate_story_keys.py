from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from scripts.migrate_story_keys import MigrationError, Revision, migrate, plan_copies
from tests.conftest import BUCKET_NAME, MVP_TABLE_NAME, make_story
from weather_story_bot.archive import archive_prefix
from weather_story_bot.models import Story
from weather_story_bot.state import content_fingerprint, story_key

if TYPE_CHECKING:
    from types_boto3_dynamodb import DynamoDBClient
    from types_boto3_s3 import S3Client

DOWNLOAD = "https://api.weather.gov/offices/MKX/weatherstories/download/"
EPOCH = "1970-01-01T00:00:00+00:00"

FIRST = make_story()
REISSUE = make_story(download=DOWNLOAD + "bbbb-2222", updateTime=EPOCH, altText="")
REVISED = make_story(
    download=DOWNLOAD + "cccc-3333",
    updateTime="2026-09-12T23:00:00+00:00",
    description="Storms arrive earlier.",
)
OTHER = make_story(title="Heat Index", download=DOWNLOAD + "dddd-4444")


def old_prefix(story: Story) -> str:
    """The archive layout before the migration."""
    start = story.start_time.astimezone(UTC)
    updated = story.update_time.astimezone(UTC)
    return f"stories/MKX/{start:%Y/%m/%d}/{story.image_id}/{updated:%Y%m%dT%H%M%SZ}"


def seed_post(
    s3: S3Client,
    dynamodb: DynamoDBClient,
    story: Story,
    image: bytes,
    message_id: int,
    posted_at: str,
) -> None:
    """An old archive pair plus the per-image and `content#` items the old Lambda wrote."""
    prefix = old_prefix(story)
    s3.put_object(Bucket=BUCKET_NAME, Key=f"{prefix}.png", Body=image)
    s3.put_object(Bucket=BUCKET_NAME, Key=f"{prefix}.json", Body=json.dumps(story.raw).encode())
    common = {
        "office_id": {"S": "MKX"},
        "update_time": {"S": story.update_time.isoformat()},
        "title": {"S": story.title},
        "posted_at": {"S": posted_at},
        "telegram_message_id": {"N": str(message_id)},
        "archive_prefix": {"S": prefix},
    }
    dynamodb.put_item(
        TableName=MVP_TABLE_NAME,
        Item={**common, "image_id": {"S": story.image_id}, "fingerprint": {"S": "old"}},
    )
    dynamodb.put_item(
        TableName=MVP_TABLE_NAME,
        Item={
            **common,
            "image_id": {"S": f"content#old-{message_id}"},
            "posted_image_id": {"S": story.image_id},
        },
    )


@pytest.fixture(autouse=True)
def _mvp_table(mvp_table: DynamoDBClient) -> None:
    """This script predates the state table and reads and writes only the MVP table."""


@pytest.fixture
def seeded(s3: S3Client, dynamodb: DynamoDBClient) -> None:
    """Two stories: one posted, re-issued unchanged, then revised; and one posted once."""
    seed_post(s3, dynamodb, FIRST, b"v1", 5, "2026-09-12T19:32:00+00:00")
    seed_post(s3, dynamodb, REISSUE, b"v1", 7, "2026-09-12T22:02:00+00:00")
    seed_post(s3, dynamodb, OTHER, b"v3", 11, "2026-09-12T22:30:00+00:00")
    seed_post(s3, dynamodb, REVISED, b"v2", 9, "2026-09-12T23:02:00+00:00")
    dynamodb.put_item(
        TableName=MVP_TABLE_NAME,
        Item={
            "office_id": {"S": "MKX"},
            "image_id": {"S": "eeee-5555"},
            "duplicate_of": {"S": OTHER.image_id},
            "telegram_message_id": {"N": "11"},
            "archive_prefix": {"S": old_prefix(OTHER)},
        },
    )


def run(s3: S3Client, dynamodb: DynamoDBClient, **flags: bool) -> tuple[list[str], object]:
    lines: list[str] = []
    plan = migrate(
        s3,
        dynamodb,
        BUCKET_NAME,
        MVP_TABLE_NAME,
        apply=flags.get("apply", False),
        delete_old=flags.get("delete_old", False),
        out=lines.append,
    )
    return lines, plan


def story_record(dynamodb: DynamoDBClient, story: Story) -> dict[str, Any]:
    return dynamodb.get_item(
        TableName=MVP_TABLE_NAME,
        Key={"office_id": {"S": "MKX"}, "image_id": {"S": f"story#{story_key(story)}"}},
    )["Item"]


def keys(s3: S3Client) -> set[str]:
    return {obj["Key"] for obj in s3.list_objects_v2(Bucket=BUCKET_NAME).get("Contents", [])}


def sort_keys(dynamodb: DynamoDBClient) -> set[str]:
    return {item["image_id"]["S"] for item in dynamodb.scan(TableName=MVP_TABLE_NAME)["Items"]}


def new_keys(story: Story, image: bytes) -> set[str]:
    prefix = archive_prefix(story, content_fingerprint(story, image))
    return {f"{prefix}.png", f"{prefix}.json"}


@pytest.mark.usefixtures("seeded")
def test_dry_run_plans_everything_and_changes_nothing(
    s3: S3Client, dynamodb: DynamoDBClient
) -> None:
    before = (keys(s3), sort_keys(dynamodb))

    lines, _ = run(s3, dynamodb)

    assert (keys(s3), sort_keys(dynamodb)) == before
    output = "\n".join(lines)
    assert "Archive: 3 copies, 1 identical re-issues" in output
    assert "DynamoDB: 2 story# records to write" in output
    assert "message 9 (earlier posts, left in the channel: 5, 7)" in output


@pytest.mark.usefixtures("seeded")
def test_apply_copies_each_revision_to_its_story_folder(
    s3: S3Client, dynamodb: DynamoDBClient
) -> None:
    old = keys(s3)

    run(s3, dynamodb, apply=True)

    migrated = new_keys(FIRST, b"v1") | new_keys(REVISED, b"v2") | new_keys(OTHER, b"v3")
    assert new_keys(REISSUE, b"v1") == new_keys(FIRST, b"v1")
    assert keys(s3) == old | migrated
    collapsed_prefix = archive_prefix(FIRST, content_fingerprint(FIRST, b"v1"))
    body = s3.get_object(Bucket=BUCKET_NAME, Key=f"{collapsed_prefix}.json")["Body"].read()
    assert json.loads(body) == dict(FIRST.raw)
    png = s3.get_object(Bucket=BUCKET_NAME, Key=f"{collapsed_prefix}.png")["Body"].read()
    assert png == b"v1"


@pytest.mark.usefixtures("seeded")
def test_apply_records_each_story_from_its_latest_post(
    s3: S3Client, dynamodb: DynamoDBClient
) -> None:
    run(s3, dynamodb, apply=True)

    first = story_record(dynamodb, FIRST)
    assert first["telegram_message_id"] == {"N": "9"}
    assert first["posted_image_id"] == {"S": REVISED.image_id}
    # The handler compares this fingerprint, so the live revision isn't reposted after deploy.
    fingerprint = content_fingerprint(REVISED, b"v2")
    assert first["fingerprint"] == {"S": fingerprint}
    assert first["archive_prefix"] == {"S": archive_prefix(REVISED, fingerprint)}
    assert first["posted_at"] == {"S": "2026-09-12T23:02:00+00:00"}
    assert story_record(dynamodb, OTHER)["telegram_message_id"] == {"N": "11"}
    assert len([key for key in sort_keys(dynamodb) if key.startswith("story#")]) == 2


@pytest.mark.usefixtures("seeded")
def test_rerun_changes_nothing_and_existing_records_are_kept(
    s3: S3Client, dynamodb: DynamoDBClient
) -> None:
    dynamodb.put_item(
        TableName=MVP_TABLE_NAME,
        Item={
            "office_id": {"S": "MKX"},
            "image_id": {"S": f"story#{story_key(OTHER)}"},
            "telegram_message_id": {"N": "99"},
        },
    )

    run(s3, dynamodb, apply=True)
    after_first = (keys(s3), sort_keys(dynamodb))
    lines, _ = run(s3, dynamodb, apply=True)

    assert (keys(s3), sort_keys(dynamodb)) == after_first
    output = "\n".join(lines)
    assert "Archive: 0 copies, 0 identical re-issues" in output
    assert "DynamoDB: 0 story# records to write" in output
    assert story_record(dynamodb, OTHER)["telegram_message_id"] == {"N": "99"}


@pytest.mark.usefixtures("seeded")
def test_delete_old_leaves_only_the_new_layout_and_records(
    s3: S3Client, dynamodb: DynamoDBClient
) -> None:
    run(s3, dynamodb, apply=True)
    migrated = keys(s3) - {
        f"{old_prefix(s)}.{ext}"
        for s in (FIRST, REISSUE, REVISED, OTHER)
        for ext in ("png", "json")
    }

    run(s3, dynamodb, apply=True, delete_old=True)

    assert keys(s3) == migrated
    assert sort_keys(dynamodb) == {f"story#{story_key(FIRST)}", f"story#{story_key(OTHER)}"}


@pytest.mark.usefixtures("seeded")
def test_delete_old_without_apply_changes_nothing(s3: S3Client, dynamodb: DynamoDBClient) -> None:
    before = (keys(s3), sort_keys(dynamodb))

    run(s3, dynamodb, delete_old=True)

    assert (keys(s3), sort_keys(dynamodb)) == before


@pytest.mark.usefixtures("seeded")
def test_missing_png_fails_before_writing(s3: S3Client, dynamodb: DynamoDBClient) -> None:
    s3.delete_object(Bucket=BUCKET_NAME, Key=f"{old_prefix(OTHER)}.png")
    before = (keys(s3), sort_keys(dynamodb))

    with pytest.raises(MigrationError, match="no matching PNG"):
        run(s3, dynamodb, apply=True)

    assert (keys(s3), sort_keys(dynamodb)) == before


@pytest.mark.usefixtures("seeded")
def test_post_without_archive_pair_fails_before_writing(
    s3: S3Client, dynamodb: DynamoDBClient
) -> None:
    for extension in ("png", "json"):
        s3.delete_object(Bucket=BUCKET_NAME, Key=f"{old_prefix(OTHER)}.{extension}")
    before = (keys(s3), sort_keys(dynamodb))

    with pytest.raises(MigrationError, match="has no archive pair"):
        run(s3, dynamodb, apply=True)

    assert (keys(s3), sort_keys(dynamodb)) == before


def test_collapse_keeps_the_earliest_copy_whatever_its_key() -> None:
    def revision(old: str, minute: int) -> Revision:
        return Revision(
            old_prefix=old,
            new_prefix="stories/MKX/new",
            story=FIRST,
            fingerprint="fp",
            last_modified=datetime(2026, 9, 14, 4, minute, tzinfo=UTC),
        )

    later, earlier = revision("stories/MKX/a", 30), revision("stories/MKX/z", 3)

    copies, collapsed = plan_copies([later, earlier], set())

    assert copies == [earlier]
    assert collapsed == [later]
    # Already migrated (a rerun): nothing to copy, and nothing reported as collapsed.
    assert plan_copies([later, earlier], {"stories/MKX/new.json"}) == ([], [])
