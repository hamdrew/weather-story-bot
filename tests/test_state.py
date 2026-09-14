from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from tests.conftest import TABLE_NAME, make_story
from weather_story_bot.state import (
    PostedRecord,
    PostedStore,
    Status,
    classify,
    content_fingerprint,
)


def test_classify_new_story() -> None:
    assert classify(make_story(), None) is Status.NEW


def test_classify_seen_story_compares_instants_not_strings() -> None:
    story = make_story(updateTime="2026-09-12T19:30:25+00:00")
    assert classify(story, "2026-09-12T14:30:25-05:00") is Status.SEEN


def test_classify_updated_story() -> None:
    story = make_story(updateTime="2026-09-12T21:00:00+00:00")
    assert classify(story, "2026-09-12T19:30:25+00:00") is Status.UPDATED


def test_get_update_time_missing(dynamodb: Any) -> None:
    assert PostedStore(dynamodb, TABLE_NAME).get_update_time("MKX", "nope") is None


def test_record_then_read_back(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    story = make_story()
    posted_at = datetime(2026, 9, 12, 20, 0, tzinfo=UTC)

    store.record_posted(story, 42, "stories/MKX/prefix", "fp", posted_at=posted_at)

    assert classify(story, store.get_update_time("MKX", story.image_id)) is Status.SEEN
    item = dynamodb.get_item(
        TableName=TABLE_NAME,
        Key={"office_id": {"S": "MKX"}, "image_id": {"S": story.image_id}},
    )["Item"]
    assert item["title"] == {"S": story.title}
    assert item["telegram_message_id"] == {"N": "42"}
    assert item["archive_prefix"] == {"S": "stories/MKX/prefix"}
    assert item["posted_at"] == {"S": "2026-09-12T20:00:00+00:00"}


def test_record_overwrites_previous_revision(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    store.record_posted(make_story(), 1, "p1", "fp1")
    updated = make_story(updateTime="2026-09-12T22:00:00+00:00")
    store.record_posted(updated, 2, "p2", "fp2")

    assert store.get_update_time("MKX", updated.image_id) == "2026-09-12T22:00:00+00:00"


def test_fingerprint_is_stable_and_ignores_download_and_order() -> None:
    story = make_story()
    reissued = make_story(
        download="https://api.weather.gov/offices/MKX/weatherstories/download/bbbb-2222",
        order=3,
    )
    assert content_fingerprint(story, b"PNG") == content_fingerprint(reissued, b"PNG")


def test_fingerprint_compares_instants_not_strings() -> None:
    story = make_story(updateTime="2026-09-12T19:30:25+00:00")
    same_instant = make_story(updateTime="2026-09-12T14:30:25-05:00")
    assert content_fingerprint(story, b"PNG") == content_fingerprint(same_instant, b"PNG")


@pytest.mark.parametrize(
    ("overrides", "image"),
    [
        ({}, b"PNG-other"),
        ({"title": "Different Title"}, b"PNG"),
        ({"description": "Different description."}, b"PNG"),
        ({"startTime": "2026-09-12T20:00:00+00:00"}, b"PNG"),
        ({"endTime": "2026-09-14T19:24:00+00:00"}, b"PNG"),
        ({"updateTime": "2026-09-12T22:00:00+00:00"}, b"PNG"),
    ],
)
def test_fingerprint_changes_with_content(overrides: dict[str, Any], image: bytes) -> None:
    assert content_fingerprint(make_story(), b"PNG") != content_fingerprint(
        make_story(**overrides), image
    )


def test_find_by_fingerprint_missing(dynamodb: Any) -> None:
    assert PostedStore(dynamodb, TABLE_NAME).find_by_fingerprint("MKX", "abc") is None


def test_record_posted_indexes_fingerprint(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    story = make_story()

    store.record_posted(story, 42, "stories/MKX/prefix", "fp1")

    assert store.find_by_fingerprint("MKX", "fp1") == PostedRecord(
        image_id=story.image_id, telegram_message_id=42, archive_prefix="stories/MKX/prefix"
    )
    assert store.find_by_fingerprint("GRB", "fp1") is None


def test_record_duplicate_marks_new_image_seen(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    original = make_story()
    store.record_posted(original, 42, "stories/MKX/prefix", "fp1")
    reissued = make_story(
        download="https://api.weather.gov/offices/MKX/weatherstories/download/bbbb-2222"
    )

    store.record_duplicate(reissued, store.find_by_fingerprint("MKX", "fp1"))

    assert classify(reissued, store.get_update_time("MKX", "bbbb-2222")) is Status.SEEN
    item = dynamodb.get_item(
        TableName=TABLE_NAME,
        Key={"office_id": {"S": "MKX"}, "image_id": {"S": "bbbb-2222"}},
    )["Item"]
    assert item["duplicate_of"] == {"S": original.image_id}
    assert item["telegram_message_id"] == {"N": "42"}
    assert item["archive_prefix"] == {"S": "stories/MKX/prefix"}
