from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from tests.conftest import make_story
from weather_story_bot.models import Story
from weather_story_bot.nws import NwsClient, NwsError

STORIES_URL = "https://api.weather.gov/offices/MKX/weatherstories"
USER_AGENT = "weather-story-bot-tests (test@example.com)"


@pytest.fixture
def client() -> NwsClient:
    return NwsClient(httpx.Client(), USER_AGENT, sleep=lambda _: None)


def test_parses_fixture_fields(mkx_stories: list) -> None:
    story = mkx_stories[0]
    assert story.office_id == "MKX"
    assert story.title == "Active Start To The Week - Timing"
    assert story.start_time == datetime(2026, 9, 12, 19, 24, tzinfo=UTC)
    assert story.update_time.tzinfo is not None
    assert story.order == 1
    assert story.priority is False
    assert story.image_id == "596aaed9-3f9a-46cf-aaa1-a22d9ea8c0c2"


def test_naive_timestamps_are_treated_as_utc() -> None:
    story = make_story(updateTime="2026-09-12T19:30:25")
    assert story.update_time == datetime(2026, 9, 12, 19, 30, 25, tzinfo=UTC)


def test_image_id_ignores_trailing_slash() -> None:
    story = make_story(download="https://api.weather.gov/offices/MKX/weatherstories/download/abc/")
    assert story.image_id == "abc"


@pytest.mark.parametrize("bad", [{"updateTime": "not a time"}, {"order": "first"}])
def test_malformed_story_is_rejected(bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="Malformed"):
        make_story(**bad)


def test_missing_field_is_rejected(mkx_payload: dict[str, Any]) -> None:
    data = mkx_payload["stories"][0]
    del data["download"]
    with pytest.raises(ValueError, match="Malformed"):
        Story.from_api(data)


@respx.mock
def test_list_stories_sorts_by_order_and_sends_headers(
    client: NwsClient, mkx_payload: dict[str, Any]
) -> None:
    mkx_payload["stories"].reverse()
    route = respx.get(STORIES_URL).respond(json=mkx_payload)

    stories = client.list_stories("MKX")

    assert [s.order for s in stories] == [1, 2]
    request = route.calls.last.request
    assert request.headers["User-Agent"] == USER_AGENT
    assert request.headers["Accept"] == "application/ld+json"


@respx.mock
def test_list_stories_empty(client: NwsClient) -> None:
    respx.get(STORIES_URL).respond(json={"stories": []})
    assert client.list_stories("MKX") == []


@respx.mock
def test_retries_once_on_server_error(client: NwsClient, mkx_payload: dict[str, Any]) -> None:
    route = respx.get(STORIES_URL)
    route.side_effect = [httpx.Response(503), httpx.Response(200, json=mkx_payload)]

    assert len(client.list_stories("MKX")) == 2
    assert route.call_count == 2


@respx.mock
def test_retries_once_on_transport_error(client: NwsClient, mkx_payload: dict[str, Any]) -> None:
    route = respx.get(STORIES_URL)
    route.side_effect = [httpx.ConnectTimeout("slow"), httpx.Response(200, json=mkx_payload)]

    assert len(client.list_stories("MKX")) == 2


@respx.mock
def test_gives_up_after_second_server_error(client: NwsClient) -> None:
    route = respx.get(STORIES_URL).respond(502)
    with pytest.raises(NwsError, match="502"):
        client.list_stories("MKX")
    assert route.call_count == 2


@respx.mock
def test_gives_up_after_second_transport_error(client: NwsClient) -> None:
    respx.get(STORIES_URL).side_effect = httpx.ConnectError("down")
    with pytest.raises(NwsError):
        client.list_stories("MKX")


@respx.mock
def test_client_error_is_not_retried(client: NwsClient) -> None:
    route = respx.get(STORIES_URL).respond(404)
    with pytest.raises(NwsError, match="404"):
        client.list_stories("MKX")
    assert route.call_count == 1


@respx.mock
def test_malformed_body_raises_nws_error(client: NwsClient) -> None:
    respx.get(STORIES_URL).respond(json={"unexpected": True})
    with pytest.raises(NwsError, match="Unexpected"):
        client.list_stories("MKX")


@respx.mock
def test_download_image_returns_bytes(client: NwsClient) -> None:
    story = make_story()
    route = respx.get(story.download).respond(content=b"\x89PNG data")

    assert client.download_image(story) == b"\x89PNG data"
    assert route.calls.last.request.headers["Accept"] == "image/png"


@respx.mock
def test_download_empty_image_raises(client: NwsClient) -> None:
    story = make_story()
    respx.get(story.download).respond(content=b"")
    with pytest.raises(NwsError, match="Empty"):
        client.download_image(story)
