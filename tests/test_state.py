from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest

from tests.conftest import TABLE_NAME, make_story
from weather_story_bot.state import (
    PostedRecord,
    PostedStore,
    content_fingerprint,
    image_sha256,
    story_key,
)

REISSUED_DOWNLOAD = "https://api.weather.gov/offices/MKX/weatherstories/download/bbbb-2222"
EPOCH = "1970-01-01T00:00:00+00:00"


def test_image_sha256_is_hex_digest() -> None:
    assert image_sha256(b"PNG") == hashlib.sha256(b"PNG").hexdigest()


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
    assert PostedStore(dynamodb, TABLE_NAME).find_story("MKX", story_key(make_story())) is None


def test_record_posted_then_find_story(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    story = make_story()
    posted_at = datetime(2026, 9, 12, 20, 0, tzinfo=UTC)

    store.record_posted(story, 42, "stories/MKX/prefix", "fp1", posted_at=posted_at)

    assert store.find_story("MKX", story_key(story)) == PostedRecord(
        image_id=story.image_id,
        telegram_message_id=42,
        archive_prefix="stories/MKX/prefix",
        fingerprint="fp1",
    )
    assert store.find_story("GRB", story_key(story)) is None
    [item] = dynamodb.scan(TableName=TABLE_NAME)["Items"]
    assert item["image_id"] == {"S": "story#" + story_key(story)}
    assert item["title"] == {"S": story.title}
    assert item["start_time"] == {"S": "2026-09-12T19:24:00+00:00"}
    assert item["end_time"] == {"S": "2026-09-13T19:24:00+00:00"}
    assert item["update_time"] == {"S": "2026-09-12T19:30:25+00:00"}
    assert item["posted_at"] == {"S": "2026-09-12T20:00:00+00:00"}


def test_record_posted_replaces_previous_revision(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    store.record_posted(make_story(), 42, "p1", "fp1")
    revised = make_story(download=REISSUED_DOWNLOAD, description="Storm timing has shifted.")

    store.record_posted(revised, 43, "p2", "fp2")

    assert store.find_story("MKX", story_key(revised)) == PostedRecord(
        image_id="bbbb-2222", telegram_message_id=43, archive_prefix="p2", fingerprint="fp2"
    )
    assert len(dynamodb.scan(TableName=TABLE_NAME)["Items"]) == 1
