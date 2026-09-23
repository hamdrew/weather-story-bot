from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
import respx

from weather_story_bot import __main__ as cli

STORIES_URL = "https://api.weather.gov/offices/MKX/weatherstories"
REISSUED_DOWNLOAD = "https://api.weather.gov/offices/MKX/weatherstories/download/reissued-uuid"
# Both fixture stories are active: they end at 19:24 and 19:34 on 2026-09-13.
NOW = datetime(2026, 9, 13, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never read a developer's real .env."""
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)


@pytest.fixture
def api(mkx_payload: dict[str, Any]) -> Any:
    with respx.mock(assert_all_called=False) as router:
        router.get(STORIES_URL).respond(json=mkx_payload)
        for story in mkx_payload["stories"]:
            router.get(story["download"]).respond(content=b"PNG-" + story["order"].to_bytes())
        yield router


def main(argv: list[str], now: datetime = NOW) -> int:
    return cli.main(argv, now=now)


def test_dry_run_prints_a_decision_beside_every_caption(api: Any, capsys: Any) -> None:
    assert main(["--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "<b>Active Start To The Week - Timing</b>" in out
    assert out.count("[new-or-updated (state not read)]") == 2


def test_dry_run_never_calls_telegram(api: Any) -> None:
    with respx.mock() as telegram:
        assert main(["--dry-run"]) == 0
        assert not telegram.calls


def test_expired_story_is_printed_but_never_downloaded(
    api: Any, mkx_payload: dict[str, Any], capsys: Any
) -> None:
    at_first_end = datetime(2026, 9, 13, 19, 24, tzinfo=UTC)

    assert main(["--dry-run"], now=at_first_end) == 0

    out = capsys.readouterr().out
    assert "[expired]" in out
    assert "[new-or-updated (state not read)]" in out
    first_download = mkx_payload["stories"][0]["download"]
    assert first_download not in [str(call.request.url) for call in api.calls]


def test_ambiguous_stories_are_rejected_and_printed(
    api: Any, mkx_payload: dict[str, Any], capsys: Any
) -> None:
    sibling = dict(mkx_payload["stories"][1], order=3, download=REISSUED_DOWNLOAD)
    mkx_payload["stories"].append(sibling)
    api.get(STORIES_URL).respond(json=mkx_payload)
    api.get(REISSUED_DOWNLOAD).respond(content=b"PNG-sibling")

    assert main(["--dry-run"]) == 0

    out = capsys.readouterr().out
    assert out.count("[rejected (duplicate_title_and_start)]") == 2


@respx.mock
def test_nws_list_failure_exits_nonzero(capsys: Any) -> None:
    respx.get(STORIES_URL).respond(404)

    assert main(["--dry-run"]) == 1

    assert f"GET {STORIES_URL} returned HTTP 404" in capsys.readouterr().err


def test_download_failure_continues_and_exits_nonzero(
    api: Any, mkx_payload: dict[str, Any], capsys: Any
) -> None:
    api.get(mkx_payload["stories"][0]["download"]).respond(404)

    assert main(["--dry-run"]) == 1

    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "[new-or-updated (state not read)]" in captured.out


@respx.mock
def test_no_active_stories(capsys: Any) -> None:
    respx.get(STORIES_URL).respond(json={"stories": []})

    assert main(["--dry-run", "--office", "mkx"]) == 0

    assert capsys.readouterr().out == "No active weather stories for MKX.\n"


def test_dry_run_is_required(capsys: Any) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2


@pytest.mark.parametrize("office", ["../x", "mk", "MKX1", "mk-x"])
def test_invalid_office_id_exits_with_a_usage_error(office: str, capsys: Any) -> None:
    with respx.mock() as router:
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["--dry-run", "--office", office])
        assert not router.calls

    assert exc_info.value.code == 2
    assert "invalid office id" in capsys.readouterr().err
