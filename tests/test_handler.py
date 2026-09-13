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
        router.post(PHOTO_URL).mock(
            side_effect=lambda _: httpx.Response(
                200, json={"ok": True, "result": {"message_id": next(message_ids)}}
            )
        )
        yield router


def captions(api: Any) -> list[str]:
    return [
        call.request.content.split(b'name="caption"\r\n\r\n')[1].split(b"\r\n--")[0].decode()
        for call in api.routes[-1].calls
    ]


def test_new_stories_are_archived_posted_and_recorded(
    services: handler.Services, api: Any, dynamodb: Any, s3: Any
) -> None:
    summary = handler.run((MKX,), services)

    assert summary == {"MKX": {"posted": 2, "updated": 0, "skipped": 0, "failed": 0}}
    assert [c.startswith("<b>Active Start") for c in captions(api)] == [True, False]
    items = dynamodb.scan(TableName=TABLE_NAME)["Items"]
    assert sorted(int(i["telegram_message_id"]["N"]) for i in items) == [100, 101]
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET_NAME)["Contents"]]
    assert len(keys) == 4
    assert all(item["archive_prefix"]["S"] + ".png" in keys for item in items)


def test_seen_stories_are_skipped(services: handler.Services, api: Any) -> None:
    handler.run((MKX,), services)
    summary = handler.run((MKX,), services)

    assert summary["MKX"] == {"posted": 0, "updated": 0, "skipped": 2, "failed": 0}
    assert api.routes[-1].call_count == 2


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
