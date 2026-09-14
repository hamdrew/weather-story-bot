"""Client for the api.weather.gov Weather Story endpoints."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

from weather_story_bot.models import Story

logger = logging.getLogger(__name__)

BASE_URL = "https://api.weather.gov"
TIMEOUT_SECONDS = 10.0
MAX_ATTEMPTS = 2


class NwsError(Exception):
    """The NWS API could not be reached or returned an unusable response."""


class NwsClient:
    def __init__(
        self,
        http: httpx.Client,
        user_agent: str,
        *,
        base_url: str = BASE_URL,
        retry_delay: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = http
        self._user_agent = user_agent
        self._base_url = base_url.rstrip("/")
        self._retry_delay = retry_delay
        self._sleep = sleep

    def list_stories(self, office_id: str) -> list[Story]:
        """Return the office's active stories, sorted by their display `order`."""
        url = f"{self._base_url}/offices/{office_id}/weatherstories"
        response = self._get(url, accept="application/ld+json")
        try:
            items = response.json()["stories"]
            stories = [Story.from_api(item) for item in items]
        except (ValueError, KeyError, TypeError) as exc:
            raise NwsError(f"Unexpected weatherstories response for {office_id}: {exc}") from exc
        return sorted(stories, key=lambda story: story.order)

    def download_image(self, story: Story) -> bytes:
        response = self._get(story.download, accept="image/png")
        if not response.content:
            raise NwsError(f"Empty image for story {story.image_id}")
        return response.content

    def _get(self, url: str, *, accept: str) -> httpx.Response:
        headers = {"User-Agent": self._user_agent, "Accept": accept}
        for attempt in range(1, MAX_ATTEMPTS + 1):
            retryable = attempt < MAX_ATTEMPTS
            try:
                response = self._http.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
            except httpx.TransportError as exc:
                if retryable:
                    logger.warning(
                        "NWS request failed, retrying", extra={"url": url, "error": repr(exc)}
                    )
                    self._sleep(self._retry_delay)
                    continue
                raise NwsError(f"GET {url} failed: {exc!r}") from exc

            if response.is_server_error and retryable:
                logger.warning(
                    "NWS server error, retrying", extra={"url": url, "status": response.status_code}
                )
                self._sleep(self._retry_delay)
                continue
            if not response.is_success:
                raise NwsError(f"GET {url} returned HTTP {response.status_code}")
            return response
        raise AssertionError("unreachable")
