"""Telegram Bot API client and caption formatting."""

from __future__ import annotations

import contextlib
import html
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from weather_story_bot.models import Story

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
CAPTION_LIMIT = 1024
UPLOAD_TIMEOUT_SECONDS = 30.0
MAX_RETRY_AFTER_SECONDS = 30
UPDATED_PREFIX = "🔄 Updated: "
ELLIPSIS = "…"

# Telegram rejects some images as photos but accepts them as documents.
_PHOTO_REJECTION_MARKERS = (
    "PHOTO_INVALID_DIMENSIONS",
    "PHOTO_SAVE_FILE_INVALID",
    "IMAGE_PROCESS_FAILED",
    "too big",
)


class TelegramError(Exception):
    """A Telegram API call failed."""


def _telegram_len(text: str) -> int:
    # Telegram measures text in UTF-16 code units.
    return len(text.encode("utf-16-le")) // 2


def _truncate_escaped(text: str, budget: int) -> str:
    """HTML-escape `text`, cutting it with an ellipsis so the result fits in `budget`."""
    escaped = html.escape(text)
    if _telegram_len(escaped) <= budget:
        return escaped
    budget -= _telegram_len(ELLIPSIS)
    pieces: list[str] = []
    used = 0
    for char in text:
        piece = html.escape(char)
        used += _telegram_len(piece)
        if used > budget:
            break
        pieces.append(piece)
    return "".join(pieces).rstrip() + ELLIPSIS


def build_caption(story: Story, office_id: str, *, updated: bool) -> str:
    """HTML caption: optional update prefix, bold title, description, weather.gov link."""
    link_url = f"https://www.weather.gov/{office_id.lower()}/weatherstory"
    head = (UPDATED_PREFIX if updated else "") + f"<b>{html.escape(story.title)}</b>"
    link = f'<a href="{html.escape(link_url)}">View on weather.gov</a>'
    description = story.description.strip()
    if not description:
        return f"{head}\n\n{link}"
    budget = CAPTION_LIMIT - _telegram_len(f"{head}\n\n\n\n{link}")
    return f"{head}\n\n{_truncate_escaped(description, budget)}\n\n{link}"


class TelegramClient:
    def __init__(
        self,
        http: httpx.Client,
        token: str,
        *,
        base_url: str = API_BASE,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = http
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._sleep = sleep

    def send_photo(self, chat_id: str, image_bytes: bytes, caption: str, filename: str) -> int:
        """Post the image with its caption and return the Telegram `message_id`."""
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        try:
            result = self._call("sendPhoto", data, {"photo": (filename, image_bytes, "image/png")})
        except _PhotoRejectedError as exc:
            logger.warning("Photo rejected, sending as document", extra={"reason": str(exc)})
            result = self._call(
                "sendDocument", data, {"document": (filename, image_bytes, "image/png")}
            )
        # Logged before anything else can fail: the StoriesPosted metric filter counts this exact
        # message, so the repost-loop alarm sees every delivered post, even ones never recorded.
        logger.info("Telegram message sent", extra={"chat_id": chat_id, "image_filename": filename})
        try:
            return int(result["message_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TelegramError(f"Unexpected Telegram result: {type(exc).__name__}") from None

    def delete_message(self, chat_id: str, message_id: int) -> None:
        """Delete a message; one that's already gone counts as deleted.

        Telegram refuses to delete messages sent more than 48 hours ago, which raises.
        """
        data = {"chat_id": chat_id, "message_id": str(message_id)}
        with contextlib.suppress(_MessageNotFoundError):
            self._call("deleteMessage", data, {})
        logger.info(
            "Telegram message deleted", extra={"chat_id": chat_id, "message_id": message_id}
        )

    def _call(self, method: str, data: dict[str, str], files: dict[str, Any]) -> Any:
        url = f"{self._base_url}/bot{self._token}/{method}"
        retried = False
        while True:
            try:
                response = self._http.post(
                    url, data=data, files=files, timeout=UPLOAD_TIMEOUT_SECONDS
                )
            except httpx.TransportError as exc:
                # Not retried: the message may have been delivered despite the error.
                # Never include the URL, which contains the bot token.
                raise TelegramError(f"{method} request failed: {type(exc).__name__}") from None

            body = _json_body(response)
            if response.is_success and body.get("ok"):
                # An object for sends, `true` for deleteMessage.
                if body.get("result") is None:
                    raise TelegramError(f"{method} returned no result")
                return body["result"]

            description = str(body.get("description") or response.reason_phrase)
            if response.status_code == 429 and not retried:
                retry_after = _retry_after(body)
                if retry_after is not None and retry_after <= MAX_RETRY_AFTER_SECONDS:
                    logger.warning(
                        "Telegram rate limited, retrying",
                        extra={"method": method, "retry_after": retry_after},
                    )
                    self._sleep(retry_after)
                    retried = True
                    continue
            if method == "sendPhoto" and (
                response.status_code == 413
                or (
                    response.status_code == 400
                    and any(marker in description for marker in _PHOTO_REJECTION_MARKERS)
                )
            ):
                raise _PhotoRejectedError(description)
            if method == "deleteMessage" and "message to delete not found" in description:
                raise _MessageNotFoundError(description)
            raise TelegramError(f"{method} failed with HTTP {response.status_code}: {description}")


class _PhotoRejectedError(TelegramError):
    pass


class _MessageNotFoundError(TelegramError):
    pass


def _json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _retry_after(body: dict[str, Any]) -> int | None:
    """Seconds from `parameters.retry_after` (default 1), or None if the value is unusable."""
    parameters = body.get("parameters")
    raw = parameters.get("retry_after", 1) if isinstance(parameters, dict) else 1
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
