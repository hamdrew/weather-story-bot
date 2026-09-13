from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from weather_story_bot import __main__ as cli
from weather_story_bot import handler

TOKEN = "123:secret-token"
CHAT_ID = "-100999"
STORIES_URL = "https://api.weather.gov/offices/MKX/weatherstories"
PHOTO_URL = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read a developer's real .env; start each test with no Telegram credentials."""
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)


@pytest.fixture
def telegram_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT_ID)


@pytest.fixture
def api(mkx_payload: dict[str, Any]) -> Any:
    with respx.mock(assert_all_called=False) as router:
        router.get(STORIES_URL).respond(json=mkx_payload)
        for story in mkx_payload["stories"]:
            router.get(story["download"]).respond(content=b"PNG-" + story["order"].to_bytes())
        message_ids = iter(range(100, 200))
        router.post(PHOTO_URL, name="photo").mock(
            side_effect=lambda _: httpx.Response(
                200, json={"ok": True, "result": {"message_id": next(message_ids)}}
            )
        )
        yield router


def test_dry_run_prints_captions_without_posting(api: Any, capsys: Any) -> None:
    assert cli.main(["--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "<b>Active Start To The Week - Timing</b>" in out
    assert "sent:" not in out
    assert not api["photo"].called


@respx.mock
def test_nws_failure_exits_nonzero(capsys: Any) -> None:
    respx.get(STORIES_URL).respond(404)

    assert cli.main(["--dry-run"]) == 1

    assert f"GET {STORIES_URL} returned HTTP 404" in capsys.readouterr().err


@respx.mock
def test_no_active_stories(capsys: Any) -> None:
    respx.get(STORIES_URL).respond(json={"stories": []})

    assert cli.main(["--dry-run", "--office", "mkx"]) == 0

    assert capsys.readouterr().out == "No active weather stories for MKX.\n"


def test_send_telegram_posts_each_story_via_handler(
    api: Any, telegram_env: None, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str, bool]] = []

    def spy(telegram: Any, chat_id: str, office_id: str, story: Any, image: bytes, **kw: Any):
        calls.append((chat_id, office_id, kw["updated"]))
        return handler.post_story(telegram, chat_id, office_id, story, image, **kw)

    monkeypatch.setattr(cli, "post_story", spy)

    assert cli.main(["--dry-run", "--send-telegram"]) == 0

    assert calls == [(CHAT_ID, "MKX", False), (CHAT_ID, "MKX", False)]
    bodies = [call.request.content for call in api["photo"].calls]
    assert len(bodies) == 2
    assert all(f'name="chat_id"\r\n\r\n{CHAT_ID}'.encode() in body for body in bodies)
    assert b"PNG-\x01" in bodies[0]
    out = capsys.readouterr().out
    assert "sent: message_id=100" in out
    assert "sent: message_id=101" in out


def test_send_telegram_requires_credentials(capsys: Any) -> None:
    with respx.mock() as router:
        assert cli.main(["--dry-run", "--send-telegram"]) == 2
        assert not router.calls
    assert "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required" in capsys.readouterr().err


def test_telegram_failure_continues_and_exits_nonzero(
    api: Any, telegram_env: None, capsys: Any
) -> None:
    api["photo"].side_effect = [
        httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"}),
        httpx.Response(200, json={"ok": True, "result": {"message_id": 7}}),
    ]

    assert cli.main(["--dry-run", "--send-telegram"]) == 1

    captured = capsys.readouterr()
    assert "chat not found" in captured.err
    assert TOKEN not in captured.err
    assert "sent: message_id=7" in captured.out
