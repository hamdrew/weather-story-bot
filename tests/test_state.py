from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.conftest import TABLE_NAME, make_story
from weather_story_bot.state import (
    LEASE_DURATION,
    OfficeLease,
    PostedRecord,
    PostedStore,
    content_fingerprint,
    description_sha256,
    image_sha256,
    story_key,
)

REISSUED_DOWNLOAD = "https://api.weather.gov/offices/MKX/weatherstories/download/bbbb-2222"
EPOCH = "1970-01-01T00:00:00+00:00"


def test_image_sha256_is_hex_digest() -> None:
    assert image_sha256(b"PNG") == hashlib.sha256(b"PNG").hexdigest()


def test_description_sha256_is_hex_digest_of_utf8() -> None:
    story = make_story(description="Snow ❄ tonight.")
    assert description_sha256(story) == hashlib.sha256("Snow ❄ tonight.".encode()).hexdigest()


def test_story_key_matches_pinned_digest() -> None:
    # Pins the frozen encoding in _sha256_json. If this fails, the encoding changed and every
    # stored story_key is now unreachable — do not "fix" the test, fix the encoding.
    assert (
        story_key(make_story())
        == "b43e93b75361ecc66062f0811c248a01598644855ba8e3e4f62eed6a44d99ea3"
    )


def test_content_fingerprint_matches_pinned_digest() -> None:
    # Pins the frozen encoding in _sha256_json. If this fails, the encoding changed and every
    # stored content_fingerprint is now unreachable — do not "fix" the test, fix the encoding.
    assert (
        content_fingerprint(make_story(), b"PNG")
        == "4a120108135cd16c0d6248e9c9f221b9e2fb42bc87f9d376269475c11043764a"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"download": REISSUED_DOWNLOAD, "order": 3},
        # NWS has re-issued byte-identical stories with updateTime set to the Unix epoch.
        {"updateTime": EPOCH, "altText": ""},
        # endTime doesn't change what the Telegram message shows.
        {"endTime": "2026-09-14T19:24:00+00:00"},
        # Title and start are the story's identity, compared through story_key instead.
        {"title": "Different Title", "startTime": "2026-09-12T20:00:00+00:00"},
    ],
)
def test_fingerprint_ignores_fields_that_dont_change_the_message(
    overrides: dict[str, Any],
) -> None:
    assert content_fingerprint(make_story(), b"PNG") == content_fingerprint(
        make_story(**overrides), b"PNG"
    )


@pytest.mark.parametrize(
    ("overrides", "image"),
    [({}, b"PNG-other"), ({"description": "Different description."}, b"PNG")],
)
def test_fingerprint_changes_with_image_or_description(
    overrides: dict[str, Any], image: bytes
) -> None:
    assert content_fingerprint(make_story(), b"PNG") != content_fingerprint(
        make_story(**overrides), image
    )


def test_story_key_survives_revisions() -> None:
    revised = make_story(
        download=REISSUED_DOWNLOAD,
        updateTime=EPOCH,
        endTime="2026-09-13T20:00:00+00:00",
        description="Storm timing has shifted.",
    )
    assert story_key(make_story()) == story_key(revised)


def test_story_key_compares_instants_not_strings() -> None:
    same_instant = make_story(startTime="2026-09-12T14:24:00-05:00")
    assert story_key(make_story()) == story_key(same_instant)


@pytest.mark.parametrize(
    "overrides", [{"title": "Different Title"}, {"startTime": "2026-09-13T19:24:00+00:00"}]
)
def test_story_key_distinguishes_occurrences(overrides: dict[str, Any]) -> None:
    assert story_key(make_story()) != story_key(make_story(**overrides))


def test_find_story_missing(dynamodb: Any) -> None:
    assert PostedStore(dynamodb, TABLE_NAME).find_story(make_story()) is None


def test_record_posted_then_find_story(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    story = make_story()
    posted_at = datetime(2026, 9, 12, 20, 0, tzinfo=UTC)

    store.record_posted(
        story, 42, "stories/MKX/prefix", "fp1", image_sha256="img1", posted_at=posted_at
    )

    assert store.find_story(story) == PostedRecord(
        image_id=story.image_id,
        telegram_message_id=42,
        archive_prefix="stories/MKX/prefix",
        fingerprint="fp1",
        image_sha256="img1",
        description_sha256=description_sha256(story),
    )
    assert store.find_story(make_story(officeId="GRB")) is None
    [item] = dynamodb.scan(TableName=TABLE_NAME)["Items"]
    assert item["PK"] == {"S": "OFFICE#MKX"}
    # Pinned: scripts/migrate_table_keys.py wrote the live records under exactly this key.
    assert item["SK"] == {"S": f"STORY#2026-09-12T19:24:00+00:00#{story_key(story)}"}
    assert item["schema_version"] == {"N": "1"}
    assert item["office_id"] == {"S": "MKX"}
    assert item["story_key"] == {"S": story_key(story)}
    assert item["title"] == {"S": story.title}
    assert item["start_time"] == {"S": "2026-09-12T19:24:00+00:00"}
    assert item["end_time"] == {"S": "2026-09-13T19:24:00+00:00"}
    assert item["update_time"] == {"S": "2026-09-12T19:30:25+00:00"}
    assert item["posted_at"] == {"S": "2026-09-12T20:00:00+00:00"}


def test_sort_key_uses_the_utc_start(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    story = make_story(startTime="2026-09-12T14:24:00-05:00")

    store.record_posted(story, 42, "p1", "fp1", image_sha256="img1")

    [item] = dynamodb.scan(TableName=TABLE_NAME)["Items"]
    assert item["SK"]["S"].startswith("STORY#2026-09-12T19:24:00+00:00#")
    assert item["start_time"] == {"S": "2026-09-12T14:24:00-05:00"}
    assert store.find_story(story) is not None


def test_record_posted_replaces_previous_revision(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    store.record_posted(make_story(), 42, "p1", "fp1", image_sha256="img1")
    revised = make_story(download=REISSUED_DOWNLOAD, description="Storm timing has shifted.")

    store.record_posted(revised, 43, "p2", "fp2", image_sha256="img2")

    assert store.find_story(revised) == PostedRecord(
        image_id="bbbb-2222",
        telegram_message_id=43,
        archive_prefix="p2",
        fingerprint="fp2",
        image_sha256="img2",
        description_sha256=description_sha256(revised),
    )
    assert len(dynamodb.scan(TableName=TABLE_NAME)["Items"]) == 1


def test_find_story_reads_records_written_before_content_hashes(dynamodb: Any) -> None:
    # Items from before 2026-09-24 carry only the combined fingerprint.
    store = PostedStore(dynamodb, TABLE_NAME)
    story = make_story()
    store.record_posted(story, 42, "p1", "fp1", image_sha256="img1")
    [item] = dynamodb.scan(TableName=TABLE_NAME)["Items"]
    dynamodb.update_item(
        TableName=TABLE_NAME,
        Key={"PK": item["PK"], "SK": item["SK"]},
        UpdateExpression="REMOVE image_sha256, description_sha256",
    )

    record = store.find_story(story)

    assert record is not None
    assert (record.fingerprint, record.image_sha256, record.description_sha256) == (
        "fp1",
        None,
        None,
    )


@pytest.mark.parametrize("stored", [{"S": "not a time"}, {"N": "1758810000"}])
def test_find_story_ignores_a_malformed_last_seen_at(dynamodb: Any, stored: dict[str, str]) -> None:
    # last_seen_at is history.py's best-effort data; it must never break the dedupe lookup.
    store = PostedStore(dynamodb, TABLE_NAME)
    story = make_story()
    store.record_posted(story, 42, "p1", "fp1", image_sha256="img1")
    [item] = dynamodb.scan(TableName=TABLE_NAME)["Items"]
    dynamodb.update_item(
        TableName=TABLE_NAME,
        Key={"PK": item["PK"], "SK": item["SK"]},
        UpdateExpression="SET last_seen_at = :v",
        ExpressionAttributeValues={":v": stored},
    )

    record = store.find_story(story)

    assert record is not None
    assert (record.fingerprint, record.last_seen_at) == ("fp1", None)


LEASE_AT = datetime(2026, 9, 13, 0, 0, tzinfo=UTC)
LEASE_KEY = {"PK": {"S": "OFFICE#MKX"}, "SK": {"S": "LEASE"}}


def test_take_lease_writes_the_lease_item(dynamodb: Any) -> None:
    holder = OfficeLease(dynamodb, TABLE_NAME).take("MKX", LEASE_AT)

    item = dynamodb.get_item(TableName=TABLE_NAME, Key=LEASE_KEY)["Item"]
    assert item == {
        **LEASE_KEY,
        "schema_version": {"N": "1"},
        "office_id": {"S": "MKX"},
        "holder": {"S": holder},
        "taken_at": {"S": "2026-09-13T00:00:00.000000+00:00"},
        "expires_at": {"S": "2026-09-13T00:06:00.000000+00:00"},
    }


def test_held_lease_is_not_taken_until_it_expires(dynamodb: Any) -> None:
    lease = OfficeLease(dynamodb, TABLE_NAME)
    first = lease.take("MKX", LEASE_AT)

    assert first is not None
    assert lease.take("MKX", LEASE_AT) is None
    assert lease.take("MKX", LEASE_AT + LEASE_DURATION) is None
    # A crashed run never releases; its lease just runs out.
    second = lease.take("MKX", LEASE_AT + LEASE_DURATION + timedelta(microseconds=1))
    assert second not in (None, first)


def test_lease_is_per_office(dynamodb: Any) -> None:
    lease = OfficeLease(dynamodb, TABLE_NAME)

    assert lease.take("MKX", LEASE_AT) is not None
    assert lease.take("GRB", LEASE_AT) is not None


def test_release_frees_the_lease(dynamodb: Any) -> None:
    lease = OfficeLease(dynamodb, TABLE_NAME)
    holder = lease.take("MKX", LEASE_AT)
    assert holder is not None

    lease.release("MKX", holder)

    assert "Item" not in dynamodb.get_item(TableName=TABLE_NAME, Key=LEASE_KEY)
    assert lease.take("MKX", LEASE_AT) is not None


def test_release_leaves_a_later_runs_lease(dynamodb: Any) -> None:
    lease = OfficeLease(dynamodb, TABLE_NAME)
    stale = lease.take("MKX", LEASE_AT)
    assert stale is not None
    later = LEASE_AT + LEASE_DURATION + timedelta(microseconds=1)
    assert lease.take("MKX", later) is not None

    lease.release("MKX", stale)

    assert lease.take("MKX", later) is None
