from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import TABLE_NAME, make_story
from weather_story_bot.history import EventKind, StoryHistory
from weather_story_bot.state import PostedStore, story_key

NOW = datetime(2026, 9, 25, 14, 37, 12, 345678, tzinfo=UTC)
MISSING_TABLE = "no-such-table"


def items(dynamodb: Any, prefix: str) -> list[dict[str, Any]]:
    return [
        item
        for item in dynamodb.scan(TableName=TABLE_NAME)["Items"]
        if item["SK"]["S"].startswith(prefix)
    ]


def failures(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [vars(r) for r in caplog.records if r.getMessage() == "History write failed"]


# record_event


def test_record_event_writes_one_immutable_ledger_item(dynamodb: Any) -> None:
    story = make_story()

    StoryHistory(dynamodb, TABLE_NAME).record_event(
        story, EventKind.UPDATED, at=NOW, fingerprint="fp2", telegram_message_id=43
    )

    [item] = items(dynamodb, "EVENT#")
    assert item == {
        "PK": {"S": "OFFICE#MKX"},
        # Pinned: backend/dynamodb-schema's EVENT# key, with a fixed-width UTC event time.
        "SK": {
            "S": f"EVENT#2026-09-12T19:24:00+00:00#{story_key(story)}"
            "#2026-09-25T14:37:12.345678+00:00"
        },
        "schema_version": {"N": "1"},
        "office_id": {"S": "MKX"},
        "story_key": {"S": story_key(story)},
        "event": {"S": "updated"},
        "event_at": {"S": "2026-09-25T14:37:12.345678+00:00"},
        "image_id": {"S": "aaaa-1111"},
        "title": {"S": "Storms Monday Night"},
        "start_time": {"S": "2026-09-12T19:24:00+00:00"},
        "end_time": {"S": "2026-09-13T19:24:00+00:00"},
        "update_time": {"S": "2026-09-12T19:30:25+00:00"},
        "fingerprint": {"S": "fp2"},
        "telegram_message_id": {"N": "43"},
    }


def test_record_event_keeps_rejection_reasons_and_omits_absent_fields(dynamodb: Any) -> None:
    StoryHistory(dynamodb, TABLE_NAME).record_event(
        make_story(),
        EventKind.REJECTED,
        at=NOW,
        reasons=["duplicate_image_id", "duplicate_image"],
    )

    [item] = items(dynamodb, "EVENT#")
    assert item["event"] == {"S": "rejected"}
    assert item["reasons"] == {"L": [{"S": "duplicate_image_id"}, {"S": "duplicate_image"}]}
    assert "fingerprint" not in item
    assert "telegram_message_id" not in item


def test_record_event_stores_no_update_diff(dynamodb: Any) -> None:
    # Decided 2026-09-24: what an update changed is derived from consecutive events, not stored.
    StoryHistory(dynamodb, TABLE_NAME).record_event(
        make_story(), EventKind.UPDATED, at=NOW, fingerprint="fp2", telegram_message_id=43
    )

    [item] = items(dynamodb, "EVENT#")
    assert not {key for key in item if key.startswith("previous_") or key == "changes"}


def test_events_sort_by_time_within_a_story(dynamodb: Any) -> None:
    history = StoryHistory(dynamodb, TABLE_NAME)
    story = make_story()
    history.record_event(story, EventKind.DELETED, at=NOW + timedelta(seconds=1))
    history.record_event(story, EventKind.POSTED, at=NOW)

    response = dynamodb.query(
        TableName=TABLE_NAME,
        KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
        ExpressionAttributeValues={
            ":pk": {"S": "OFFICE#MKX"},
            ":prefix": {"S": f"EVENT#2026-09-12T19:24:00+00:00#{story_key(story)}#"},
        },
    )
    assert [item["event"]["S"] for item in response["Items"]] == ["posted", "deleted"]


def test_record_event_never_overwrites_an_event(
    dynamodb: Any, caplog: pytest.LogCaptureFixture
) -> None:
    history = StoryHistory(dynamodb, TABLE_NAME)
    history.record_event(make_story(), EventKind.POSTED, at=NOW, telegram_message_id=42)

    history.record_event(make_story(), EventKind.DELETED, at=NOW, telegram_message_id=41)

    [item] = items(dynamodb, "EVENT#")
    assert item["event"] == {"S": "posted"}
    [record] = failures(caplog)
    assert record["levelno"] == logging.WARNING
    assert record["history_write"] == "event"


def test_record_event_failure_logs_warning_and_returns(
    dynamodb: Any, caplog: pytest.LogCaptureFixture
) -> None:
    StoryHistory(dynamodb, MISSING_TABLE).record_event(make_story(), EventKind.POSTED, at=NOW)

    [record] = failures(caplog)
    assert record["levelno"] == logging.WARNING
    assert (record["history_write"], record["office"], record["image_id"]) == (
        "event",
        "MKX",
        "aaaa-1111",
    )
    assert "ResourceNotFoundException" in record["error"]


# touch_last_seen


def test_touch_last_seen_sets_it_on_the_current_story(dynamodb: Any) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    story = make_story()
    store.record_posted(story, 42, "p1", "fp1", image_sha256="img1")

    StoryHistory(dynamodb, TABLE_NAME).touch_last_seen(story, None, now=NOW)

    record = store.find_story(story)
    assert record is not None
    assert record.last_seen_at == NOW
    [item] = items(dynamodb, "STORY#")
    assert item["last_seen_at"] == {"S": "2026-09-25T14:37:12.345678+00:00"}


@pytest.mark.parametrize(
    ("age", "touched"),
    [
        (timedelta(minutes=59, seconds=59), False),
        (timedelta(hours=1), True),
        (timedelta(hours=3), True),
    ],
)
def test_touch_last_seen_only_when_an_hour_stale(
    dynamodb: Any, age: timedelta, touched: bool
) -> None:
    store = PostedStore(dynamodb, TABLE_NAME)
    history = StoryHistory(dynamodb, TABLE_NAME)
    story = make_story()
    store.record_posted(story, 42, "p1", "fp1", image_sha256="img1")
    history.touch_last_seen(story, None, now=NOW - age)

    history.touch_last_seen(story, NOW - age, now=NOW)

    record = store.find_story(story)
    assert record is not None
    assert record.last_seen_at == (NOW if touched else NOW - age)


def test_touch_last_seen_when_fresh_makes_no_request(
    dynamodb: Any, caplog: pytest.LogCaptureFixture
) -> None:
    # A missing table would fail any request, so silence proves none was made.
    StoryHistory(dynamodb, MISSING_TABLE).touch_last_seen(
        make_story(), NOW - timedelta(minutes=15), now=NOW
    )

    assert not failures(caplog)


def test_touch_last_seen_never_creates_a_story_item(
    dynamodb: Any, caplog: pytest.LogCaptureFixture
) -> None:
    StoryHistory(dynamodb, TABLE_NAME).touch_last_seen(make_story(), None, now=NOW)

    assert dynamodb.scan(TableName=TABLE_NAME)["Items"] == []
    assert not failures(caplog)


def test_touch_last_seen_failure_logs_warning_and_returns(
    dynamodb: Any, caplog: pytest.LogCaptureFixture
) -> None:
    StoryHistory(dynamodb, MISSING_TABLE).touch_last_seen(make_story(), None, now=NOW)

    [record] = failures(caplog)
    assert record["levelno"] == logging.WARNING
    assert record["history_write"] == "last_seen"


def test_record_posted_clears_last_seen(dynamodb: Any) -> None:
    # record_posted replaces the whole item, so a repost starts unseen and the next run touches it.
    store = PostedStore(dynamodb, TABLE_NAME)
    story = make_story()
    store.record_posted(story, 42, "p1", "fp1", image_sha256="img1")
    StoryHistory(dynamodb, TABLE_NAME).touch_last_seen(story, None, now=NOW)

    store.record_posted(story, 43, "p2", "fp2", image_sha256="img2")

    record = store.find_story(story)
    assert record is not None
    assert record.last_seen_at is None


# record_run

COUNTS = {"posted": 1, "updated": 0, "skipped": 2, "rejected": 0, "failed": 0}


def test_record_run_writes_one_immutable_run_item(dynamodb: Any) -> None:
    StoryHistory(dynamodb, TABLE_NAME).record_run(
        "MKX",
        at=NOW,
        nws_failed=False,
        stories_seen=3,
        counts=COUNTS,
        aws_request_id="e16ab440-4453-4ddb-b52a-f9af386f1184",
    )

    [item] = items(dynamodb, "RUN#")
    assert item == {
        "PK": {"S": "OFFICE#MKX"},
        # Pinned: backend/dynamodb-schema's RUN# key, with a fixed-width UTC run time.
        "SK": {"S": "RUN#2026-09-25T14:37:12.345678+00:00"},
        "schema_version": {"N": "1"},
        "office_id": {"S": "MKX"},
        "run_at": {"S": "2026-09-25T14:37:12.345678+00:00"},
        "nws_failed": {"BOOL": False},
        "stories_seen": {"N": "3"},
        "posted": {"N": "1"},
        "updated": {"N": "0"},
        "skipped": {"N": "2"},
        "rejected": {"N": "0"},
        "failed": {"N": "0"},
        "aws_request_id": {"S": "e16ab440-4453-4ddb-b52a-f9af386f1184"},
    }


def test_record_run_without_request_id_omits_it(dynamodb: Any) -> None:
    StoryHistory(dynamodb, TABLE_NAME).record_run(
        "MKX", at=NOW, nws_failed=True, stories_seen=0, counts=COUNTS
    )

    [item] = items(dynamodb, "RUN#")
    assert item["nws_failed"] == {"BOOL": True}
    assert "aws_request_id" not in item


def test_every_run_is_its_own_record(dynamodb: Any) -> None:
    # A Scheduler duplicate or a manual invoke seconds apart is a second run, recorded as one.
    history = StoryHistory(dynamodb, TABLE_NAME)

    history.record_run("MKX", at=NOW, nws_failed=False, stories_seen=3, counts=COUNTS)
    history.record_run(
        "MKX", at=NOW + timedelta(seconds=30), nws_failed=False, stories_seen=3, counts=COUNTS
    )
    history.record_run("GRB", at=NOW, nws_failed=False, stories_seen=1, counts=COUNTS)

    keys = sorted((i["PK"]["S"], i["SK"]["S"]) for i in items(dynamodb, "RUN#"))
    assert keys == [
        ("OFFICE#GRB", "RUN#2026-09-25T14:37:12.345678+00:00"),
        ("OFFICE#MKX", "RUN#2026-09-25T14:37:12.345678+00:00"),
        ("OFFICE#MKX", "RUN#2026-09-25T14:37:42.345678+00:00"),
    ]


def test_run_key_is_utc_whatever_the_caller_zone(dynamodb: Any) -> None:
    # 19:00 CDT is 00:00 UTC the next day.
    StoryHistory(dynamodb, TABLE_NAME).record_run(
        "MKX",
        at=datetime(2026, 9, 25, 19, 0, tzinfo=ZoneInfo("America/Chicago")),
        nws_failed=False,
        stories_seen=3,
        counts=COUNTS,
    )

    [item] = items(dynamodb, "RUN#")
    assert item["SK"] == {"S": "RUN#2026-09-26T00:00:00.000000+00:00"}


def test_record_run_never_overwrites_a_run(dynamodb: Any, caplog: pytest.LogCaptureFixture) -> None:
    history = StoryHistory(dynamodb, TABLE_NAME)
    history.record_run("MKX", at=NOW, nws_failed=False, stories_seen=3, counts=COUNTS)

    history.record_run("MKX", at=NOW, nws_failed=True, stories_seen=0, counts=COUNTS)

    [item] = items(dynamodb, "RUN#")
    assert item["nws_failed"] == {"BOOL": False}
    [record] = failures(caplog)
    assert record["history_write"] == "run"


def test_record_run_failure_logs_warning_and_returns(
    dynamodb: Any, caplog: pytest.LogCaptureFixture
) -> None:
    StoryHistory(dynamodb, MISSING_TABLE).record_run(
        "MKX", at=NOW, nws_failed=False, stories_seen=3, counts=COUNTS
    )

    [record] = failures(caplog)
    assert record["levelno"] == logging.WARNING
    assert (record["history_write"], record["office"]) == ("run", "MKX")
