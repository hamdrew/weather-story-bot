from __future__ import annotations

import json
import logging
from typing import Any

import boto3
import httpx
import pytest
import respx

from tests.conftest import BUCKET_NAME, TABLE_NAME
from weather_story_bot import handler
from weather_story_bot.archive import StoryArchive
from weather_story_bot.config import OfficeConfig
from weather_story_bot.nws import NwsClient
from weather_story_bot.state import PostedStore
from weather_story_bot.telegram import TelegramClient

TOKEN = "123:secret-token"
MKX = OfficeConfig("MKX", "-100111", "Milwaukee/Sullivan")
GRB = OfficeConfig("GRB", "-100222", "Green Bay")
MKX_URL = "https://api.weather.gov/offices/MKX/weatherstories"
GRB_URL = "https://api.weather.gov/offices/GRB/weatherstories"
PHOTO_URL = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"


@pytest.fixture
def services(dynamodb: Any, s3: Any) -> handler.Services:
    http = httpx.Client()
    return handler.Services(
        nws=NwsClient(http, "tests", sleep=lambda _: None),
        store=PostedStore(dynamodb, TABLE_NAME),
        archive=StoryArchive(s3, BUCKET_NAME),
        telegram=TelegramClient(http, TOKEN, sleep=lambda _: None),
    )


@pytest.fixture
def api(mkx_payload: dict[str, Any]) -> Any:
    """Mock NWS (stories + images) and Telegram; message ids count up from 100."""
    with respx.mock(assert_all_called=False) as router:
        router.get(MKX_URL).respond(json=mkx_payload)
        for story in mkx_payload["stories"]:
            router.get(story["download"]).respond(content=b"PNG-" + story["order"].to_bytes())
        message_ids = iter(range(100, 200))
        router.post(PHOTO_URL, name="photo").mock(
            side_effect=lambda _: httpx.Response(
                200, json={"ok": True, "result": {"message_id": next(message_ids)}}
            )
        )
        yield router


def captions(api: Any) -> list[str]:
    return [
        call.request.content.split(b'name="caption"\r\n\r\n')[1].split(b"\r\n--")[0].decode()
        for call in api.routes["photo"].calls
    ]


def test_new_stories_are_archived_posted_and_recorded(
    services: handler.Services, api: Any, dynamodb: Any, s3: Any
) -> None:
    summary = handler.run((MKX,), services)

    assert summary == {"MKX": {"posted": 2, "updated": 0, "skipped": 0, "failed": 0}}
    assert [c.startswith("<b>Active Start") for c in captions(api)] == [True, False]
    all_items = dynamodb.scan(TableName=TABLE_NAME)["Items"]
    items = [i for i in all_items if not i["image_id"]["S"].startswith("content#")]
    fingerprints = [i for i in all_items if i["image_id"]["S"].startswith("content#")]
    assert sorted(int(i["telegram_message_id"]["N"]) for i in items) == [100, 101]
    assert sorted(i["posted_image_id"]["S"] for i in fingerprints) == sorted(
        i["image_id"]["S"] for i in items
    )
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET_NAME)["Contents"]]
    assert len(keys) == 4
    assert all(item["archive_prefix"]["S"] + ".png" in keys for item in items)


def test_seen_stories_are_skipped(services: handler.Services, api: Any) -> None:
    handler.run((MKX,), services)
    summary = handler.run((MKX,), services)

    assert summary["MKX"] == {"posted": 0, "updated": 0, "skipped": 2, "failed": 0}
    assert api.routes["photo"].call_count == 2


def test_changed_update_time_reposts_with_prefix(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any], dynamodb: Any
) -> None:
    handler.run((MKX,), services)
    mkx_payload["stories"][1]["updateTime"] = "2026-09-12T23:00:00+00:00"
    api.get(MKX_URL).respond(json=mkx_payload)

    summary = handler.run((MKX,), services)

    assert summary["MKX"] == {"posted": 0, "updated": 1, "skipped": 1, "failed": 0}
    assert captions(api)[-1].startswith("🔄 Updated: <b>Monday Night")
    image_id = mkx_payload["stories"][1]["download"].rpartition("/")[2]
    assert services.store.get_update_time("MKX", image_id) == "2026-09-12T23:00:00+00:00"


REISSUED_DOWNLOAD = "https://api.weather.gov/offices/MKX/weatherstories/download/reissued-uuid"


def reissue(api: Any, mkx_payload: dict[str, Any], image: bytes, **changes: Any) -> dict[str, Any]:
    """Re-serve story order 2 under a new image UUID, as NWS did on 2026-09-14."""
    story = mkx_payload["stories"][1]
    original = dict(story)
    story.update(download=REISSUED_DOWNLOAD, **changes)
    api.get(MKX_URL).respond(json=mkx_payload)
    api.get(REISSUED_DOWNLOAD, name="reissued").respond(content=image)
    return original


def test_identical_story_reissued_under_new_uuid_is_skipped(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    dynamodb: Any,
    s3: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    handler.run((MKX,), services)
    original = reissue(api, mkx_payload, b"PNG-" + mkx_payload["stories"][1]["order"].to_bytes())
    original_id = original["download"].rpartition("/")[2]
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    summary = handler.run((MKX,), services)

    assert summary["MKX"] == {"posted": 0, "updated": 0, "skipped": 2, "failed": 0}
    assert api.routes["photo"].call_count == 2
    assert len(s3.list_objects_v2(Bucket=BUCKET_NAME)["Contents"]) == 4
    item = dynamodb.get_item(
        TableName=TABLE_NAME,
        Key={"office_id": {"S": "MKX"}, "image_id": {"S": "reissued-uuid"}},
    )["Item"]
    assert item["duplicate_of"] == {"S": original_id}
    assert item["telegram_message_id"] == {"N": "101"}
    [skipped] = [r for r in caplog.records if r.getMessage() == "Duplicate story skipped"]
    assert skipped.image_id == "reissued-uuid"
    assert skipped.duplicate_of == original_id

    handler.run((MKX,), services)
    assert api.routes["reissued"].call_count == 1


@pytest.mark.parametrize(
    ("image", "changes"),
    [
        (b"PNG-different", {}),
        (None, {"updateTime": "2026-09-12T23:00:00+00:00"}),
        (None, {"description": "Storm timing has shifted."}),
    ],
)
def test_reissue_with_changed_content_is_posted(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    image: bytes | None,
    changes: dict[str, Any],
) -> None:
    handler.run((MKX,), services)
    same_image = b"PNG-" + mkx_payload["stories"][1]["order"].to_bytes()
    reissue(api, mkx_payload, image or same_image, **changes)

    summary = handler.run((MKX,), services)

    assert summary["MKX"] == {"posted": 1, "updated": 0, "skipped": 1, "failed": 0}
    assert api.routes["photo"].call_count == 3


def test_one_story_posted_log_per_new_or_updated_story(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    # "Story posted" marks a recorded post; the repost-loop runbook compares it with
    # "Telegram message sent", which is what the StoriesPosted metric filter counts.
    def posted_records() -> list[logging.LogRecord]:
        return [r for r in caplog.records if r.getMessage() == "Story posted"]

    caplog.set_level(logging.INFO, logger="weather_story_bot")
    handler.run((MKX,), services)
    assert [r.status for r in posted_records()] == ["new", "new"]

    caplog.clear()
    mkx_payload["stories"][1]["updateTime"] = "2026-09-12T23:00:00+00:00"
    api.get(MKX_URL).respond(json=mkx_payload)
    handler.run((MKX,), services)
    assert [r.status for r in posted_records()] == ["updated"]

    caplog.clear()
    handler.run((MKX,), services)
    assert posted_records() == []


def test_post_is_counted_even_when_recording_fails(
    services: handler.Services,
    api: Any,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The StoriesPosted CloudWatch metric filter matches "Telegram message sent", so the
    # repost-loop alarm must still see posts whose DynamoDB write fails.
    def fail(*_: object) -> None:
        raise RuntimeError("PutItem throttled")

    monkeypatch.setattr(services.store, "record_posted", fail)
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    summary = handler.run((MKX,), services)

    assert summary["MKX"]["failed"] == 2
    messages = [r.getMessage() for r in caplog.records]
    assert messages.count("Telegram message sent") == 2
    assert "Story posted" not in messages


def test_telegram_failure_leaves_story_unrecorded(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any]
) -> None:
    api.post(PHOTO_URL).mock(
        side_effect=[
            httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"}),
            httpx.Response(200, json={"ok": True, "result": {"message_id": 5}}),
        ]
    )

    summary = handler.run((MKX,), services)

    assert summary["MKX"] == {"posted": 1, "updated": 0, "skipped": 0, "failed": 1}
    first_id = mkx_payload["stories"][0]["download"].rpartition("/")[2]
    assert services.store.get_update_time("MKX", first_id) is None


def test_failing_office_does_not_block_others(services: handler.Services, api: Any) -> None:
    api.get(GRB_URL).respond(404)

    summary = handler.run((GRB, MKX), services)

    assert summary["GRB"]["failed"] == 1
    assert summary["MKX"]["posted"] == 2


def test_lambda_handler_end_to_end(
    services: handler.Services, api: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    boto3.client("ssm").put_parameter(
        Name="/weather-story-bot/telegram-token", Value=TOKEN, Type="SecureString"
    )
    monkeypatch.setattr(handler, "_services", None)
    for name, value in {
        "OFFICES_JSON": json.dumps({"MKX": {"chat_id": MKX.chat_id, "name": MKX.name}}),
        "STATE_TABLE": TABLE_NAME,
        "ARCHIVE_BUCKET": BUCKET_NAME,
        "TELEGRAM_TOKEN_PARAM": "/weather-story-bot/telegram-token",
        "NWS_USER_AGENT": "tests",
    }.items():
        monkeypatch.setenv(name, value)

    assert handler.lambda_handler({}, None)["MKX"]["posted"] == 2
    assert handler.lambda_handler({}, None)["MKX"]["skipped"] == 2

    api.get(MKX_URL).respond(503)
    with pytest.raises(handler.ProcessingError):
        handler.lambda_handler({}, None)


def test_json_formatter_includes_extra_fields() -> None:
    record = logging.makeLogRecord(
        {"name": "x", "levelname": "INFO", "msg": "Story posted", "office": "MKX"}
    )
    entry = json.loads(handler.JsonFormatter().format(record))
    assert entry["message"] == "Story posted"
    assert entry["office"] == "MKX"
