"""No handled Telegram failure puts a secret into a log record.

The Lambda runtime's JSON formatter is not available offline, and it only serialises what a
record holds. So these tests read the records: a record that holds no secret cannot produce a
line with one. Every failure is driven through `handler.run`, because on most paths
`telegram.py` raises without logging, and the records that carry a Telegram exception are the
handler's "Failed to process story" (with a stack trace) and "Telegram delete failed" (whose
`error` is `repr(exc)`).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from tests.conftest import BUCKET_NAME, TABLE_NAME
from weather_story_bot import handler
from weather_story_bot.archive import StoryArchive
from weather_story_bot.config import OfficeConfig
from weather_story_bot.history import StoryHistory
from weather_story_bot.models import Story
from weather_story_bot.nws import NwsClient
from weather_story_bot.state import OfficeLease, PostedStore
from weather_story_bot.telegram import TelegramClient, build_caption

TOKEN = "123456:LEAK-CANARY"
API_HOST = "api.telegram.org"
MKX = OfficeConfig("MKX", "-100111", "Milwaukee/Sullivan")
MKX_URL = "https://api.weather.gov/offices/MKX/weatherstories"
PHOTO_URL = f"https://{API_HOST}/bot{TOKEN}/sendPhoto"
DOCUMENT_URL = f"https://{API_HOST}/bot{TOKEN}/sendDocument"
DELETE_URL = f"https://{API_HOST}/bot{TOKEN}/deleteMessage"
# Both fixture stories are active: they end at 19:24 and 19:34 on 2026-09-13.
NOW = datetime(2026, 9, 13, 0, 0, tzinfo=UTC)
REJECTED_PHOTO = httpx.Response(
    400, json={"ok": False, "description": "Bad Request: PHOTO_INVALID_DIMENSIONS"}
)
FAILED_SEND = httpx.Response(
    403, json={"ok": False, "description": "Forbidden: bot is not a member of the channel chat"}
)


def image_of(story: dict[str, Any], revision: str = "first") -> bytes:
    """Long, distinctive bytes, so a stray fragment of an image can't hide in a short match."""
    return f"PNG-LEAK-CANARY-IMAGE-{story['order']}-{revision}-".encode() + b"0123456789" * 8


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
def api(mkx_payload: dict[str, Any]) -> Iterator[Any]:
    """Mock NWS and Telegram, with the canary token in every Telegram URL."""
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
        router.post(DOCUMENT_URL, name="document").respond(
            json={"ok": True, "result": {"message_id": 300}}
        )
        router.post(DELETE_URL, name="delete").respond(json={"ok": True, "result": True})
        yield router


@pytest.fixture
def production_logging() -> Iterator[None]:
    """Set the levels production sets, and put the three loggers' levels back afterwards."""
    loggers = [logging.getLogger(), logging.getLogger("httpx"), logging.getLogger("httpcore")]
    saved = [log.level for log in loggers]
    handler.configure_logging()
    try:
        yield
    finally:
        for log, level in zip(loggers, saved, strict=True):
            log.setLevel(level)


def sent_captions(mkx_payload: dict[str, Any]) -> list[str]:
    """Every caption the bot could send for the fixture stories, as a post and as an update."""
    return [
        build_caption(Story.from_api(story), MKX.office_id, updated=updated)
        for story in mkx_payload["stories"]
        for updated in (False, True)
    ]


def all_images(mkx_payload: dict[str, Any]) -> list[bytes]:
    return [
        image_of(story, revision)
        for story in mkx_payload["stories"]
        for revision in ("first", "revised")
    ]


def strings_in(value: Any) -> Iterator[str]:
    """Every str inside `value`, raw, walking dicts, lists, tuples and sets.

    `repr` and `str` of a container escape a caption's newlines, so a raw caption nested in a
    field would not match them.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings_in(key)
            yield from strings_in(item)
    elif isinstance(value, list | tuple | set | frozenset):
        for item in value:
            yield from strings_in(item)


def assert_no_secret(
    records: list[logging.LogRecord], *, captions: list[str], images: list[bytes]
) -> None:
    """Search each record's message, every attribute, and its stack trace.

    An attribute is searched as its raw strings (`strings_in`), as `str` and as `repr`: `repr`
    escapes a caption's newlines, so it alone would miss a caption held in a field.
    """
    assert records, "no records were captured, so nothing was checked"
    # An image's ASCII text is also a substring of its bytes' repr.
    forbidden = [TOKEN, API_HOST, *captions, *(image.decode("ascii") for image in images)]
    formatter = logging.Formatter()
    for record in records:
        texts = [record.getMessage()]
        for value in vars(record).values():
            texts += [*strings_in(value), str(value), repr(value)]
        if record.exc_info:
            texts.append(formatter.formatException(record.exc_info))
        for text in texts:
            for secret in forbidden:
                assert secret not in text, f"{secret[:30]!r} leaked into a {record.name} record"


def records_of(caplog: pytest.LogCaptureFixture, message: str) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage() == message]


def assert_stack_traces(records: list[logging.LogRecord]) -> None:
    """At least one record, each with a stack trace, so the trace check is never vacuous."""
    assert records
    assert all(r.exc_info is not None for r in records)


def test_transport_error_on_send_photo_leaks_nothing(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    production_logging: None,
) -> None:
    # A real transport error's text can hold the URL, which holds the token.
    route = api.post(PHOTO_URL).mock(side_effect=httpx.ConnectError(f"cannot reach {PHOTO_URL}"))

    handler.run((MKX,), services, now=NOW)

    assert route.called
    assert_stack_traces(records_of(caplog, "Failed to process story"))
    assert_no_secret(
        caplog.records, captions=sent_captions(mkx_payload), images=all_images(mkx_payload)
    )


def test_rate_limit_then_success_leaks_nothing(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    production_logging: None,
) -> None:
    message_ids = iter(range(100, 200))
    limited = [True]

    def rate_limited_once(_: httpx.Request) -> httpx.Response:
        if limited:
            limited.pop()
            return httpx.Response(
                429,
                json={
                    "ok": False,
                    "description": "Too Many Requests: retry after 1",
                    "parameters": {"retry_after": 1},
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": next(message_ids)}})

    route = api.post(PHOTO_URL).mock(side_effect=rate_limited_once)

    handler.run((MKX,), services, now=NOW)

    assert route.called
    [limited_record] = records_of(caplog, "Telegram rate limited, retrying")
    assert vars(limited_record)["event"] == "telegram.rate_limited"
    assert_no_secret(
        caplog.records, captions=sent_captions(mkx_payload), images=all_images(mkx_payload)
    )


def test_photo_rejected_then_sent_as_a_document_leaks_nothing(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    production_logging: None,
) -> None:
    photo = api.post(PHOTO_URL).mock(return_value=REJECTED_PHOTO)

    handler.run((MKX,), services, now=NOW)

    assert photo.called
    assert api.routes["document"].called
    rejected = records_of(caplog, "Photo rejected, sending as document")
    assert [vars(r)["event"] for r in rejected] == ["telegram.photo_rejected"] * 2
    assert_no_secret(
        caplog.records, captions=sent_captions(mkx_payload), images=all_images(mkx_payload)
    )


def test_unexpected_result_without_a_message_id_leaks_nothing(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    production_logging: None,
) -> None:
    route = api.post(PHOTO_URL).respond(json={"ok": True, "result": {}})

    handler.run((MKX,), services, now=NOW)

    assert route.called
    assert_stack_traces(records_of(caplog, "Failed to process story"))
    assert_no_secret(
        caplog.records, captions=sent_captions(mkx_payload), images=all_images(mkx_payload)
    )


def test_http_error_status_on_send_photo_leaks_nothing(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    production_logging: None,
) -> None:
    route = api.post(PHOTO_URL).mock(return_value=FAILED_SEND)

    handler.run((MKX,), services, now=NOW)

    assert route.called
    assert_stack_traces(records_of(caplog, "Failed to process story"))
    assert_no_secret(
        caplog.records, captions=sent_captions(mkx_payload), images=all_images(mkx_payload)
    )


def test_http_error_status_on_send_document_leaks_nothing(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    production_logging: None,
) -> None:
    photo = api.post(PHOTO_URL).mock(return_value=REJECTED_PHOTO)
    document = api.post(DOCUMENT_URL).mock(return_value=FAILED_SEND)

    handler.run((MKX,), services, now=NOW)

    assert photo.called
    assert document.called
    assert records_of(caplog, "Photo rejected, sending as document")
    assert_stack_traces(records_of(caplog, "Failed to process story"))
    assert_no_secret(
        caplog.records, captions=sent_captions(mkx_payload), images=all_images(mkx_payload)
    )


def test_http_error_status_on_delete_message_leaks_nothing(
    services: handler.Services,
    api: Any,
    mkx_payload: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    production_logging: None,
) -> None:
    handler.run((MKX,), services, now=NOW)
    # Revising a posted story makes the next run repost it, then delete the old message.
    story = mkx_payload["stories"][1]
    api.get(story["download"]).respond(content=image_of(story, "revised"))
    delete = api.post(DELETE_URL).mock(
        return_value=httpx.Response(
            400, json={"ok": False, "description": "Bad Request: message can't be deleted"}
        )
    )

    summary = handler.run((MKX,), services, now=NOW)

    assert summary["MKX"]["updated"] == 1
    assert delete.called
    [refused] = records_of(caplog, "Telegram delete failed, old message kept")
    assert vars(refused)["event"] == "telegram.delete_failed"
    # The error is the exception's repr: its text is kept, and holds no secret.
    assert "deleteMessage failed with HTTP 400" in vars(refused)["error"]
    assert_no_secret(
        caplog.records, captions=sent_captions(mkx_payload), images=all_images(mkx_payload)
    )


def test_http_client_loggers_are_capped_at_warning(production_logging: None) -> None:
    # httpx logs request URLs at INFO, and Telegram URLs hold the token (FR-011).
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def test_the_check_fails_on_a_record_that_holds_a_secret() -> None:
    """The search is not vacuous: it fails for a leak in a message, a field and a trace."""
    caption = "<b>Title</b>\n\nA multi-line caption"
    leaked_message = logging.makeLogRecord({"msg": f"POST {PHOTO_URL}"})
    leaked_attribute = logging.makeLogRecord({"msg": "ok", "error": f"HTTPError({API_HOST!r})"})
    leaked_caption = logging.makeLogRecord({"msg": "ok", "caption": caption})
    leaked_caption_in_list = logging.makeLogRecord({"msg": "ok", "captions": [caption]})
    try:
        raise RuntimeError(TOKEN)
    except RuntimeError:
        leaked_trace = logging.makeLogRecord({"msg": "ok", "exc_info": sys.exc_info()})

    for record in (
        leaked_message,
        leaked_attribute,
        leaked_caption,
        leaked_caption_in_list,
        leaked_trace,
    ):
        with pytest.raises(AssertionError, match="leaked"):
            assert_no_secret([record], captions=[caption], images=[])
    with pytest.raises(AssertionError, match="no records"):
        assert_no_secret([], captions=[], images=[])
