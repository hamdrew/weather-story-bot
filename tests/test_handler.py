from __future__ import annotations

import copy
import dataclasses
import json
import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs

import boto3
import httpx
import pytest
import respx
from botocore.exceptions import ClientError

from tests.conftest import BUCKET_NAME, TABLE_NAME
from weather_story_bot import handler
from weather_story_bot.archive import StoryArchive
from weather_story_bot.config import OfficeConfig
from weather_story_bot.history import StoryHistory
from weather_story_bot.models import Story
from weather_story_bot.nws import NwsClient
from weather_story_bot.state import OfficeLease, PostedStore
from weather_story_bot.telegram import TelegramClient

TOKEN = "123:secret-token"
MKX = OfficeConfig("MKX", "-100111", "Milwaukee/Sullivan")
GRB = OfficeConfig("GRB", "-100222", "Green Bay")
MKX_URL = "https://api.weather.gov/offices/MKX/weatherstories"
GRB_URL = "https://api.weather.gov/offices/GRB/weatherstories"
PHOTO_URL = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
DELETE_URL = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
REISSUED_DOWNLOAD = "https://api.weather.gov/offices/MKX/weatherstories/download/reissued-uuid"
EPOCH = "1970-01-01T00:00:00+00:00"
# Both fixture stories are active: they end at 19:24 and 19:34 on 2026-09-13.
NOW = datetime(2026, 9, 13, 0, 0, tzinfo=UTC)
# A real Lambda context always has aws_request_id; lambda_handler reads it for every log line.
LAMBDA_CONTEXT = SimpleNamespace(aws_request_id="test-request-id")


@pytest.fixture
def services(dynamodb: Any, s3: Any) -> handler.Services:
    http = httpx.Client()
    return handler.Services(
        nws=NwsClient(http, "tests", sleep=lambda _: None),
        store=PostedStore(dynamodb, TABLE_NAME),
        lease=OfficeLease(dynamodb, TABLE_NAME),
        history=StoryHistory(dynamodb, TABLE_NAME),
        archive=StoryArchive(s3, BUCKET_NAME),
        telegram=TelegramClient(http, TOKEN, sleep=lambda _: None),
    )


@pytest.fixture
def api(mkx_payload: dict[str, Any]) -> Any:
    """Mock NWS (stories + images) and Telegram; message ids count up from 100."""
    with respx.mock(assert_all_called=False) as router:
        router.get(MKX_URL).respond(json=mkx_payload)
        for story in mkx_payload["stories"]:
            router.get(story["download"]).respond(content=image_of(story))
        message_ids = iter(range(100, 200))
        router.post(PHOTO_URL, name="photo").mock(
            side_effect=lambda _: httpx.Response(
                200, json={"ok": True, "result": {"message_id": next(message_ids)}}
            )
        )
        router.post(DELETE_URL, name="delete").respond(json={"ok": True, "result": True})
        yield router


def run(services: handler.Services, *offices: OfficeConfig, now: datetime = NOW) -> Any:
    return handler.run(offices or (MKX,), services, now=now)


def image_of(story: dict[str, Any]) -> bytes:
    return b"PNG-" + story["order"].to_bytes()


def counts(**nonzero: int) -> dict[str, int]:
    return {"posted": 0, "updated": 0, "skipped": 0, "rejected": 0, "failed": 0, **nonzero}


def captions(api: Any) -> list[str]:
    return [form_field(call.request, "caption") for call in api.routes["photo"].calls]


def form_field(request: httpx.Request, name: str) -> str:
    marker = f'name="{name}"\r\n\r\n'.encode()
    return request.content.split(marker)[1].split(b"\r\n--")[0].decode()


def deleted_ids(api: Any) -> list[int]:
    return [
        int(parse_qs(call.request.content.decode())["message_id"][0])
        for call in api.routes["delete"].calls
    ]


def revise(
    api: Any,
    mkx_payload: dict[str, Any],
    image: bytes | None = None,
    index: int = 1,
    **changes: Any,
) -> dict[str, Any]:
    """Change one listed story and serve it (with `image`, if given) on the next run."""
    story = mkx_payload["stories"][index]
    story.update(changes)
    api.get(MKX_URL).respond(json=mkx_payload)
    if image is not None or "download" in changes:
        api.get(story["download"]).respond(content=image or image_of(story))
    return story


def posted_record(services: handler.Services, story: dict[str, Any]) -> Any:
    return services.store.find_story(Story.from_api(story))


def history_items(dynamodb: Any, prefix: str) -> list[dict[str, Any]]:
    """Items whose sort key starts with `prefix`, in key order (events by story, then time)."""
    found = [
        item
        for item in dynamodb.scan(TableName=TABLE_NAME)["Items"]
        if item["SK"]["S"].startswith(prefix)
    ]
    return sorted(found, key=lambda item: item["SK"]["S"])


def events(dynamodb: Any) -> list[tuple[str, int | None]]:
    """Each ledger event's kind and message id, in event-time order."""
    found = sorted(history_items(dynamodb, "EVENT#"), key=lambda i: i["event_at"]["S"])
    return [(item["event"]["S"], _message_id(item)) for item in found]


def _message_id(item: dict[str, Any]) -> int | None:
    return int(item["telegram_message_id"]["N"]) if "telegram_message_id" in item else None


def test_new_stories_are_archived_posted_and_recorded(
    services: handler.Services, api: Any, dynamodb: Any, s3: Any
) -> None:
    summary = run(services)

    assert summary == {"MKX": counts(posted=2)}
    assert [c.startswith("<b>Active Start") for c in captions(api)] == [True, False]
    items = history_items(dynamodb, "STORY#")
    assert sorted(int(i["telegram_message_id"]["N"]) for i in items) == [100, 101]
    assert api.routes["delete"].call_count == 0
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET_NAME)["Contents"]]
    assert len(keys) == 4
    assert all(item["archive_prefix"]["S"] + ".png" in keys for item in items)


def test_unchanged_stories_are_skipped(services: handler.Services, api: Any, s3: Any) -> None:
    run(services)
    summary = run(services)

    assert summary["MKX"] == counts(skipped=2)
    assert api.routes["photo"].call_count == 2
    assert api.routes["delete"].call_count == 0
    assert len(s3.list_objects_v2(Bucket=BUCKET_NAME)["Contents"]) == 4


@pytest.mark.parametrize(
    "changes",
    [
        {"updateTime": "2026-09-12T23:00:00+00:00"},
        {"endTime": "2026-09-13T20:00:00+00:00"},
        {"altText": ""},
        # NWS re-issued "High Swim Risk" on 2026-09-15 under a new UUID, updateTime at the epoch.
        {"download": REISSUED_DOWNLOAD, "updateTime": EPOCH, "altText": ""},
    ],
)
def test_changes_that_dont_alter_the_message_are_skipped(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any], changes: dict[str, Any]
) -> None:
    run(services)
    image = image_of(mkx_payload["stories"][1])
    revise(api, mkx_payload, image, **changes)

    summary = run(services)

    assert summary["MKX"] == counts(skipped=2)
    assert api.routes["photo"].call_count == 2
    assert api.routes["delete"].call_count == 0


@pytest.mark.parametrize(
    ("image", "changes"),
    [
        (b"PNG-revised", {}),
        # "Thunderstorms early this Morning" on 2026-09-15: new UUID, new image, later end.
        (
            b"PNG-revised",
            {
                "download": REISSUED_DOWNLOAD,
                "updateTime": EPOCH,
                "endTime": "2026-09-13T20:00:00+00:00",
            },
        ),
        (None, {"description": "Storm timing has shifted."}),
    ],
)
def test_changed_story_is_reposted_and_old_message_deleted(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    image: bytes | None,
    changes: dict[str, Any],
) -> None:
    run(services)
    story = revise(api, mkx_payload, image, **changes)

    summary = run(services)

    assert summary["MKX"] == counts(updated=1, skipped=1)
    assert api.routes["photo"].call_count == 3
    assert captions(api)[-1].startswith("🔄 Updated: <b>Monday Night")
    assert deleted_ids(api) == [101]
    assert posted_record(services, story).telegram_message_id == 102

    assert run(services)["MKX"] == counts(skipped=2)
    assert api.routes["photo"].call_count == 3
    assert api.routes["delete"].call_count == 1


def test_each_revision_deletes_the_previous_repost(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any]
) -> None:
    run(services)
    original = image_of(mkx_payload["stories"][1])
    revise(api, mkx_payload, b"PNG-second")
    run(services)
    revise(api, mkx_payload, original)

    summary = run(services)

    # Reverting to the first image is still a change from what the channel shows now.
    assert summary["MKX"]["updated"] == 1
    assert deleted_ids(api) == [101, 102]
    assert posted_record(services, mkx_payload["stories"][1]).telegram_message_id == 103


def test_failed_delete_keeps_the_new_post(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    run(services)
    story = revise(api, mkx_payload, b"PNG-revised")
    # Telegram refuses to delete messages sent more than 48 hours ago.
    api.post(DELETE_URL, name="delete").respond(
        400, json={"ok": False, "description": "Bad Request: message can't be deleted"}
    )
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    summary = run(services)

    assert summary["MKX"] == counts(updated=1, skipped=1)
    assert posted_record(services, story).telegram_message_id == 102
    [warning] = [
        r for r in caplog.records if r.getMessage() == "Telegram delete failed, old message kept"
    ]
    assert warning.levelno == logging.WARNING
    assert vars(warning)["telegram_message_id"] == 101
    assert TOKEN not in caplog.text


def test_old_message_is_kept_when_recording_the_repost_fails(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run(services)
    revise(api, mkx_payload, b"PNG-revised")

    def fail(*_: object) -> None:
        raise RuntimeError("PutItem throttled")

    monkeypatch.setattr(services.store, "record_posted", fail)

    summary = run(services)

    assert summary["MKX"] == counts(skipped=1, failed=1)
    assert api.routes["photo"].call_count == 3
    assert api.routes["delete"].call_count == 0


@pytest.mark.parametrize(
    "changes", [{"title": "Rain Ending Tuesday"}, {"startTime": "2026-09-12T19:44:00+00:00"}]
)
def test_new_title_or_start_is_a_new_story(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any], changes: dict[str, Any]
) -> None:
    run(services)
    revise(api, mkx_payload, **changes)

    summary = run(services)

    assert summary["MKX"] == counts(posted=1, skipped=1)
    assert api.routes["photo"].call_count == 3
    assert api.routes["delete"].call_count == 0


def test_expired_stories_take_no_action(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any]
) -> None:
    first = mkx_payload["stories"][0]
    at_first_end = datetime(2026, 9, 13, 19, 24, tzinfo=UTC)

    summary = run(services, now=at_first_end)

    assert summary["MKX"] == counts(posted=1, skipped=1)
    assert api.routes["photo"].call_count == 1
    assert first["download"] not in [str(call.request.url) for call in api.calls]

    run(services)
    revise(api, mkx_payload, b"PNG-revised", index=0)
    summary = run(services, now=at_first_end)

    assert summary["MKX"] == counts(skipped=2)
    assert api.routes["photo"].call_count == 2
    assert api.routes["delete"].call_count == 0


def sibling(mkx_payload: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return dict(mkx_payload["stories"][1], order=3, **changes)


@pytest.mark.parametrize(
    ("extra", "image", "reason"),
    [
        (
            {"title": "Rain Ending Tuesday", "startTime": "2026-09-12T19:44:00+00:00"},
            b"PNG-sibling",
            "duplicate_image_id",
        ),
        ({"download": REISSUED_DOWNLOAD}, b"PNG-sibling", "duplicate_title_and_start"),
        (
            {
                "download": REISSUED_DOWNLOAD,
                "title": "Rain Ending Tuesday",
                "startTime": "2026-09-12T19:44:00+00:00",
            },
            None,
            "duplicate_image",
        ),
    ],
)
def test_ambiguous_stories_are_all_rejected_and_logged(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    extra: dict[str, Any],
    image: bytes | None,
    reason: str,
) -> None:
    listed = mkx_payload["stories"][1]
    mkx_payload["stories"].append(sibling(mkx_payload, **extra))
    api.get(MKX_URL).respond(json=mkx_payload)
    if "download" in extra:
        api.get(REISSUED_DOWNLOAD).respond(content=image or image_of(listed))
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    summary = run(services)

    assert summary["MKX"] == counts(posted=1, rejected=2)
    assert [c.startswith("<b>Active Start") for c in captions(api)] == [True]
    assert posted_record(services, listed) is None
    [logged] = [r for r in caplog.records if r.getMessage() == "Ambiguous stories from NWS"]
    assert logged.levelno == logging.ERROR
    assert vars(logged)["office"] == "MKX"
    stories = vars(logged)["stories"]
    assert len(stories) == 2
    assert all(reason in s["reasons"] for s in stories)
    titles = {listed["title"], extra.get("title", listed["title"])}
    assert {s["title"] for s in stories} == titles


def test_rejection_leaves_a_posted_story_alone_until_nws_fixes_it(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any]
) -> None:
    run(services)
    listed = dict(mkx_payload["stories"][1])
    mkx_payload["stories"].append(sibling(mkx_payload, download=REISSUED_DOWNLOAD))
    api.get(MKX_URL).respond(json=mkx_payload)
    api.get(REISSUED_DOWNLOAD).respond(content=b"PNG-sibling")

    assert run(services)["MKX"] == counts(skipped=1, rejected=2)
    assert api.routes["photo"].call_count == 2
    assert api.routes["delete"].call_count == 0

    mkx_payload["stories"].pop()
    api.get(MKX_URL).respond(json=mkx_payload)
    assert run(services)["MKX"] == counts(skipped=2)
    assert posted_record(services, listed).telegram_message_id == 101


def test_failed_download_counts_as_failed_and_others_post(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any]
) -> None:
    api.get(mkx_payload["stories"][0]["download"]).respond(404)

    summary = run(services)

    assert summary["MKX"] == counts(posted=1, failed=1)
    assert captions(api)[0].startswith("<b>Monday Night")


def test_one_log_line_per_recorded_post(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    # "Story posted" marks a recorded post; the repost-loop runbook compares it with
    # "Telegram message sent", which is what the StoriesPosted metric filter counts.
    def statuses() -> list[str]:
        return [vars(r)["status"] for r in caplog.records if r.getMessage() == "Story posted"]

    caplog.set_level(logging.INFO, logger="weather_story_bot")
    run(services)
    assert statuses() == ["new", "new"]

    caplog.clear()
    revise(api, mkx_payload, description="Storm timing has shifted.")
    run(services)
    assert statuses() == ["updated"]

    caplog.clear()
    run(services)
    assert statuses() == []


def test_updated_story_logs_what_changed(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    run(services)
    before = posted_record(services, mkx_payload["stories"][1])
    old_image_id = before.image_id
    story = revise(
        api,
        mkx_payload,
        b"PNG-revised",
        download=REISSUED_DOWNLOAD,
        description="Storm timing has shifted.",
    )
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    run(services)

    [rec] = [r for r in caplog.records if r.getMessage() == "Story posted"]
    after = posted_record(services, story)
    fields = vars(rec)
    assert fields["status"] == "updated"
    assert fields["changes"] == ["image_id", "image", "description"]
    assert fields["image_id"] == Story.from_api(story).image_id != old_image_id
    assert fields["previous_image_id"] == old_image_id
    assert fields["fingerprint"] == after.fingerprint
    assert fields["previous_fingerprint"] == before.fingerprint
    assert fields["archive_prefix"] == after.archive_prefix
    assert fields["previous_archive_prefix"] == before.archive_prefix


def test_new_story_log_has_no_previous_fields(
    services: handler.Services, api: Any, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    run(services)

    posted = [vars(r) for r in caplog.records if r.getMessage() == "Story posted"]
    assert len(posted) == 2
    assert all("fingerprint" in fields for fields in posted)
    assert not any(k.startswith("previous_") or k == "changes" for f in posted for k in f)


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

    summary = run(services)

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

    summary = run(services)

    assert summary["MKX"] == counts(posted=1, failed=1)
    assert posted_record(services, mkx_payload["stories"][0]) is None


def test_failing_office_does_not_block_others(services: handler.Services, api: Any) -> None:
    api.get(GRB_URL).respond(404)

    summary = run(services, GRB, MKX)

    assert summary["GRB"]["failed"] == 1
    assert summary["MKX"]["posted"] == 2


def test_failed_record_lookup_fails_only_its_office(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    dynamodb: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    grb_payload = copy.deepcopy(mkx_payload)
    for story in grb_payload["stories"]:
        story["officeId"] = "GRB"
    api.get(GRB_URL).respond(json=grb_payload)
    get_item = dynamodb.get_item

    def throttled_for_grb(**kwargs: Any) -> Any:
        if kwargs["Key"]["PK"]["S"] == "OFFICE#GRB":
            raise ClientError(
                {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "x"}},
                "GetItem",
            )
        return get_item(**kwargs)

    # moto can't throttle; GetItem is only find_story's.
    monkeypatch.setattr(dynamodb, "get_item", throttled_for_grb)
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    summary = run(services, GRB, MKX)

    # Deciding without GRB's records would repost its stories, so GRB does nothing.
    assert summary == {"GRB": counts(failed=1), "MKX": counts(posted=2)}
    assert api.routes["photo"].call_count == 2
    [failed] = [r for r in caplog.records if r.getMessage() == "Failed to read posted stories"]
    assert vars(failed)["office"] == "GRB"
    # GRB still released its lease and recorded a run that saw NWS.
    assert services.lease.take("GRB", NOW) is not None
    [grb_run] = [r for r in history_items(dynamodb, "RUN#") if r["office_id"]["S"] == "GRB"]
    assert grb_run["nws_failed"] == {"BOOL": False}


def test_log_lines_carry_their_own_office_and_never_a_stale_one(
    services: handler.Services, api: Any, caplog: pytest.LogCaptureFixture
) -> None:
    api.get(GRB_URL).respond(404)
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    run(services, GRB, MKX)

    [failed] = [r for r in caplog.records if r.getMessage() == "Failed to list stories"]
    assert vars(failed)["office"] == "GRB"
    posted = [r for r in caplog.records if r.getMessage() == "Story posted"]
    assert {vars(r)["office"] for r in posted} == {"MKX"}


def test_lambda_handler_end_to_end(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
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
    # The Lambda uses the real clock, so keep the fixture stories active.
    for story in mkx_payload["stories"]:
        story["endTime"] = "2999-01-01T00:00:00+00:00"
    api.get(MKX_URL).respond(json=mkx_payload)
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    assert handler.lambda_handler({}, LAMBDA_CONTEXT)["MKX"]["posted"] == 2
    assert handler.lambda_handler({}, LAMBDA_CONTEXT)["MKX"]["skipped"] == 2
    run_records = history_items(boto3.client("dynamodb"), "RUN#")
    assert [r["aws_request_id"]["S"] for r in run_records] == ["test-request-id"] * 2

    # aws_request_id comes from the Lambda context, not a caller-supplied extra.
    complete = [r for r in caplog.records if r.getMessage() == "Run complete"]
    assert all(vars(r)["aws_request_id"] == "test-request-id" for r in complete)
    # Run complete spans every office, so it carries no single office's id.
    assert all("office" not in vars(r) for r in complete)

    # Ambiguous NWS data alarms through its own metric filter, not a failed invocation.
    mkx_payload["stories"].append(sibling(mkx_payload, download=REISSUED_DOWNLOAD))
    api.get(MKX_URL).respond(json=mkx_payload)
    api.get(REISSUED_DOWNLOAD).respond(content=b"PNG-sibling")
    assert handler.lambda_handler({}, LAMBDA_CONTEXT)["MKX"]["rejected"] == 2

    api.get(MKX_URL).respond(503)
    with pytest.raises(handler.ProcessingError):
        handler.lambda_handler({}, LAMBDA_CONTEXT)


def test_aws_request_id_does_not_leak_into_a_later_bare_run(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A ContextVar reset, not a leftover attribute: it must not survive past its invocation."""
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
    for story in mkx_payload["stories"]:
        story["endTime"] = "2999-01-01T00:00:00+00:00"
    api.get(MKX_URL).respond(json=mkx_payload)
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    handler.lambda_handler({}, LAMBDA_CONTEXT)
    caplog.clear()
    revise(api, mkx_payload, b"PNG-revised")
    run(services)

    [posted] = [r for r in caplog.records if r.getMessage() == "Story posted"]
    assert "aws_request_id" not in vars(posted)


def test_json_formatter_includes_extra_fields() -> None:
    record = logging.makeLogRecord(
        {"name": "x", "levelname": "INFO", "msg": "Story posted", "office": "MKX"}
    )
    entry = json.loads(handler.JsonFormatter().format(record))
    assert entry["message"] == "Story posted"
    assert entry["office"] == "MKX"


def test_overlapping_run_sends_nothing(services: handler.Services, api: Any) -> None:
    send = api.routes["photo"].side_effect
    overlapping: list[Any] = []

    def send_during_overlap(request: httpx.Request) -> httpx.Response:
        # Scheduler's at-least-once delivery: a second run starts while the first is sending.
        if not overlapping:
            overlapping.append(run(services))
        return send(request)

    api.routes["photo"].side_effect = send_during_overlap

    summary = run(services)

    assert overlapping == [{"MKX": counts(skipped=1)}]
    assert summary["MKX"] == counts(posted=2)
    assert api.routes["photo"].call_count == 2
    # The first run released its lease, so the next one runs and finds nothing new.
    assert run(services)["MKX"] == counts(skipped=2)
    assert api.routes["photo"].call_count == 2


def test_held_lease_skips_the_office(
    services: handler.Services, api: Any, caplog: pytest.LogCaptureFixture
) -> None:
    assert services.lease.take("MKX", NOW) is not None
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    assert run(services)["MKX"] == counts(skipped=1)
    assert not api.calls
    [record] = [r for r in caplog.records if r.getMessage() == "Office run already in progress"]
    assert record.levelno == logging.INFO
    assert vars(record)["office"] == "MKX"


def test_lease_error_counts_as_failed(
    services: handler.Services, api: Any, dynamodb: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def throttled(**_: Any) -> None:
        raise ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Throttled"}},
            "PutItem",
        )

    # moto can't throttle; this PutItem is the lease's, the first write of the run.
    monkeypatch.setattr(dynamodb, "put_item", throttled)

    assert run(services)["MKX"] == counts(failed=1)
    assert not api.calls


def test_failed_release_still_counts_the_run(
    services: handler.Services,
    api: Any,
    dynamodb: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def throttled(**_: Any) -> None:
        raise ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Throttled"}},
            "DeleteItem",
        )

    monkeypatch.setattr(dynamodb, "delete_item", throttled)
    caplog.set_level(logging.INFO, logger="weather_story_bot")

    assert run(services)["MKX"] == counts(posted=2)
    [record] = [r for r in caplog.records if r.getMessage() == "Office lease release failed"]
    assert record.levelno == logging.WARNING


# History (history.py): best-effort writes after the safety chain, never between its steps.


def test_posts_are_recorded_as_events_and_the_run_as_a_run_record(
    services: handler.Services, api: Any, dynamodb: Any
) -> None:
    run(services)

    assert events(dynamodb) == [("posted", 100), ("posted", 101)]
    fingerprints = {i["fingerprint"]["S"] for i in history_items(dynamodb, "STORY#")}
    assert {i["fingerprint"]["S"] for i in history_items(dynamodb, "EVENT#")} == fingerprints
    [record] = history_items(dynamodb, "RUN#")
    assert record["run_at"] == {"S": "2026-09-13T00:00:00.000000+00:00"}
    assert record["nws_failed"] == {"BOOL": False}
    assert record["stories_seen"] == {"N": "2"}
    assert {name: int(record[name]["N"]) for name in counts()} == counts(posted=2)
    # run() outside lambda_handler has no request id.
    assert "aws_request_id" not in record


def test_update_records_the_repost_then_the_deleted_message(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any], dynamodb: Any
) -> None:
    run(services)
    before = posted_record(services, mkx_payload["stories"][1])
    story = revise(api, mkx_payload, b"PNG-revised", download=REISSUED_DOWNLOAD)

    run(services)

    assert events(dynamodb)[2:] == [("updated", 102), ("deleted", 101)]
    updated, deleted = sorted(history_items(dynamodb, "EVENT#"), key=lambda i: i["event_at"]["S"])[
        2:
    ]
    assert updated["fingerprint"]["S"] == posted_record(services, story).fingerprint
    # The deleted event is about the replaced revision, under the same story.
    assert deleted["fingerprint"]["S"] == before.fingerprint
    assert deleted["image_id"]["S"] == before.image_id != updated["image_id"]["S"]
    assert deleted["story_key"] == updated["story_key"]
    # The replaced revision's end and update times aren't stored, so the event doesn't guess.
    assert "end_time" not in deleted and "update_time" not in deleted


def test_refused_delete_is_recorded_as_delete_failed(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any], dynamodb: Any
) -> None:
    run(services)
    revise(api, mkx_payload, b"PNG-revised")
    api.post(DELETE_URL, name="delete").respond(
        400, json={"ok": False, "description": "Bad Request: message can't be deleted"}
    )

    run(services)

    assert events(dynamodb)[2:] == [("updated", 102), ("delete_failed", 101)]


def test_rejections_are_recorded_with_their_reasons(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any], dynamodb: Any
) -> None:
    # Both rejected stories share a story_key, so their events differ only by event time.
    mkx_payload["stories"].append(sibling(mkx_payload, download=REISSUED_DOWNLOAD))
    api.get(MKX_URL).respond(json=mkx_payload)
    api.get(REISSUED_DOWNLOAD).respond(content=b"PNG-sibling")

    assert run(services)["MKX"] == counts(posted=1, rejected=2)

    rejected = [i for i in history_items(dynamodb, "EVENT#") if i["event"]["S"] == "rejected"]
    assert len(rejected) == 2
    assert all(
        {"S": "duplicate_title_and_start"} in i["reasons"]["L"] and "fingerprint" in i
        for i in rejected
    )
    assert "telegram_message_id" not in rejected[0]
    # Recorded before anything is sent, never between a send and its record.
    [posted] = [i for i in history_items(dynamodb, "EVENT#") if i["event"]["S"] == "posted"]
    assert max(i["event_at"]["S"] for i in rejected) < posted["event_at"]["S"]


def test_unchanged_stories_are_marked_seen_at_most_hourly(
    services: handler.Services, api: Any, mkx_payload: dict[str, Any]
) -> None:
    run(services)
    story = mkx_payload["stories"][1]
    # A fresh post hasn't been seen by a later run yet.
    assert posted_record(services, story).last_seen_at is None

    run(services)
    assert posted_record(services, story).last_seen_at == NOW

    run(services, now=NOW + timedelta(minutes=45))
    assert posted_record(services, story).last_seen_at == NOW

    later = NOW + timedelta(hours=1)
    run(services, now=later)
    assert posted_record(services, story).last_seen_at == later


def test_failed_listing_is_recorded_as_a_blind_run(
    services: handler.Services, api: Any, dynamodb: Any
) -> None:
    api.get(MKX_URL).respond(503)

    assert run(services)["MKX"] == counts(failed=1)

    [record] = history_items(dynamodb, "RUN#")
    assert record["nws_failed"] == {"BOOL": True}
    assert record["stories_seen"] == {"N": "0"}
    assert record["failed"] == {"N": "1"}


def test_run_without_the_lease_writes_no_history(
    services: handler.Services, api: Any, dynamodb: Any
) -> None:
    assert services.lease.take("MKX", NOW) is not None

    assert run(services)["MKX"] == counts(skipped=1)

    assert history_items(dynamodb, "RUN#") == []
    assert history_items(dynamodb, "EVENT#") == []


def test_failed_history_writes_never_block_a_post(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    dynamodb: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # A missing table fails every history write at the wire, like an outage would.
    services = dataclasses.replace(services, history=StoryHistory(dynamodb, "no-such-table"))
    caplog.set_level(logging.INFO)

    assert run(services)["MKX"] == counts(posted=2)
    run(services)
    revise(api, mkx_payload, b"PNG-revised")
    assert run(services)["MKX"] == counts(updated=1, skipped=1)
    mkx_payload["stories"].append(sibling(mkx_payload, download=REISSUED_DOWNLOAD))
    api.get(MKX_URL).respond(json=mkx_payload)
    api.get(REISSUED_DOWNLOAD).respond(content=b"PNG-sibling")
    assert run(services)["MKX"] == counts(skipped=1, rejected=2)

    assert deleted_ids(api) == [101]
    failed = [vars(r) for r in caplog.records if r.getMessage() == "History write failed"]
    assert all(r["levelno"] == logging.WARNING for r in failed)
    assert {r["history_write"] for r in failed} == {"event", "last_seen", "run"}
    # Every run still released its lease.
    assert services.lease.take("MKX", NOW) is not None
