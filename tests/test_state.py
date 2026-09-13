from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tests.conftest import TABLE_NAME, make_story
from weather_story_bot.state import PostedStore, Status, classify


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

    store.record_posted(story, 42, "stories/MKX/prefix", posted_at=posted_at)

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
    store.record_posted(make_story(), 1, "p1")
    updated = make_story(updateTime="2026-09-12T22:00:00+00:00")
    store.record_posted(updated, 2, "p2")

    assert store.get_update_time("MKX", updated.image_id) == "2026-09-12T22:00:00+00:00"
