from __future__ import annotations

import httpx
import pytest
import respx

from tests.conftest import make_story
from weather_story_bot.telegram import (
    CAPTION_LIMIT,
    TelegramClient,
    TelegramError,
    _telegram_len,
    build_caption,
)

TOKEN = "123:secret-token"
PHOTO_URL = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
DOCUMENT_URL = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
LINK = '<a href="https://www.weather.gov/mkx/weatherstory">View on weather.gov</a>'


def ok(message_id: int) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "result": {"message_id": message_id}})


def error(status: int, description: str, **extra: object) -> httpx.Response:
    body = {"ok": False, "error_code": status, "description": description, **extra}
    return httpx.Response(status, json=body)


# --- captions ---------------------------------------------------------------


def test_caption_layout() -> None:
    story = make_story(title="Storms", description="  Heavy rain.  ")
    assert build_caption(story, "MKX", updated=False) == f"<b>Storms</b>\n\nHeavy rain.\n\n{LINK}"


def test_caption_updated_prefix() -> None:
    caption = build_caption(make_story(title="Storms"), "MKX", updated=True)
    assert caption.startswith("🔄 Updated: <b>Storms</b>")


def test_caption_escapes_html() -> None:
    story = make_story(title='Rain <1"> & wind', description="Gusts > 40 & <b>hail</b>")
    caption = build_caption(story, "MKX", updated=False)
    assert "<b>Rain &lt;1&quot;&gt; &amp; wind</b>" in caption
    assert "Gusts &gt; 40 &amp; &lt;b&gt;hail&lt;/b&gt;" in caption


def test_caption_without_description() -> None:
    assert build_caption(make_story(description=""), "MKX", updated=False).count("\n\n") == 1


@pytest.mark.parametrize("updated", [False, True])
@pytest.mark.parametrize("char", ["a", "&", "🌧"])
def test_long_description_is_truncated_to_limit(char: str, updated: bool) -> None:
    story = make_story(description=char * 3000)
    caption = build_caption(story, "MKX", updated=updated)

    assert _telegram_len(caption) <= CAPTION_LIMIT
    assert _telegram_len(caption) > CAPTION_LIMIT - 10
    assert caption.endswith(f"…\n\n{LINK}")
    assert "&am…" not in caption  # never cut inside an HTML entity


def test_short_description_is_not_truncated() -> None:
    caption = build_caption(make_story(description="x" * 500), "MKX", updated=False)
    assert "…" not in caption


# --- client -----------------------------------------------------------------


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def client(sleeps: list[float]) -> TelegramClient:
    return TelegramClient(httpx.Client(), TOKEN, sleep=sleeps.append)


@respx.mock
def test_send_photo_uploads_multipart(client: TelegramClient) -> None:
    route = respx.post(PHOTO_URL).mock(return_value=ok(7))

    assert client.send_photo("-1001", b"PNGDATA", "<b>hi</b>", "abc.png") == 7
    body = route.calls.last.request.content
    assert b'name="chat_id"\r\n\r\n-1001' in body
    assert b'name="parse_mode"\r\n\r\nHTML' in body
    assert b'name="photo"; filename="abc.png"' in body
    assert b"PNGDATA" in body


@respx.mock
def test_rate_limit_is_retried_once(client: TelegramClient, sleeps: list[float]) -> None:
    route = respx.post(PHOTO_URL)
    route.side_effect = [error(429, "Too Many Requests", parameters={"retry_after": 3}), ok(8)]

    assert client.send_photo("-1001", b"x", "c", "a.png") == 8
    assert sleeps == [3]


@respx.mock
def test_second_rate_limit_raises(client: TelegramClient) -> None:
    respx.post(PHOTO_URL).mock(
        return_value=error(429, "Too Many Requests", parameters={"retry_after": 1})
    )
    with pytest.raises(TelegramError, match="429"):
        client.send_photo("-1001", b"x", "c", "a.png")


@respx.mock
def test_long_retry_after_is_not_waited(client: TelegramClient, sleeps: list[float]) -> None:
    respx.post(PHOTO_URL).mock(
        return_value=error(429, "Too Many Requests", parameters={"retry_after": 600})
    )
    with pytest.raises(TelegramError):
        client.send_photo("-1001", b"x", "c", "a.png")
    assert sleeps == []


@pytest.mark.parametrize(
    "rejection",
    [error(400, "Bad Request: PHOTO_INVALID_DIMENSIONS"), httpx.Response(413)],
)
@respx.mock
def test_rejected_photo_falls_back_to_document(
    client: TelegramClient, rejection: httpx.Response
) -> None:
    respx.post(PHOTO_URL).mock(return_value=rejection)
    document = respx.post(DOCUMENT_URL).mock(return_value=ok(9))

    assert client.send_photo("-1001", b"x", "cap", "a.png") == 9
    assert b'name="document"; filename="a.png"' in document.calls.last.request.content


@respx.mock
def test_other_errors_raise_without_fallback(client: TelegramClient) -> None:
    respx.post(PHOTO_URL).mock(return_value=error(403, "Forbidden: bot is not a member"))
    document = respx.post(DOCUMENT_URL)

    with pytest.raises(TelegramError, match="not a member"):
        client.send_photo("-1001", b"x", "cap", "a.png")
    assert not document.called


@respx.mock
def test_transport_error_is_not_retried_and_hides_token(client: TelegramClient) -> None:
    route = respx.post(PHOTO_URL).mock(side_effect=httpx.ReadTimeout(f"timeout on {PHOTO_URL}"))

    with pytest.raises(TelegramError) as exc_info:
        client.send_photo("-1001", b"x", "cap", "a.png")
    assert route.call_count == 1
    assert TOKEN not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
