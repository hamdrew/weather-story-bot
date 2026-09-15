"""Lambda entry point: validate active Weather Stories, then post new and changed ones."""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from weather_story_bot.archive import StoryArchive
from weather_story_bot.config import OfficeConfig, Settings
from weather_story_bot.models import Story
from weather_story_bot.nws import NwsClient
from weather_story_bot.state import (
    PostedRecord,
    PostedStore,
    Status,
    content_fingerprint,
    image_sha256,
    story_key,
)
from weather_story_bot.telegram import TelegramClient, TelegramError, build_caption

logger = logging.getLogger("weather_story_bot")

_STANDARD_LOG_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update({k: v for k, v in vars(record).items() if k not in _STANDARD_LOG_ATTRS})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        handler.setFormatter(JsonFormatter())
    root.setLevel(logging.INFO)
    # httpx logs full request URLs at INFO, and Telegram URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


class ProcessingError(Exception):
    """At least one office or story failed; raised so Lambda records an error."""


@dataclass(frozen=True, slots=True)
class Services:
    nws: NwsClient
    store: PostedStore
    archive: StoryArchive
    telegram: TelegramClient


def run(
    offices: tuple[OfficeConfig, ...], services: Services, *, now: datetime | None = None
) -> dict[str, dict[str, int]]:
    """Process every office, isolating failures per office and per story."""
    now = now or datetime.now(UTC)
    summary: dict[str, dict[str, int]] = {}
    for office in offices:
        counts = {"posted": 0, "updated": 0, "skipped": 0, "rejected": 0, "failed": 0}
        summary[office.office_id] = counts
        try:
            stories = services.nws.list_stories(office.office_id)
        except Exception:
            logger.exception("Failed to list stories", extra={"office": office.office_id})
            counts["failed"] += 1
            continue

        # Expired stories get no action at all: no download, no checks, no post or delete.
        active = [story for story in stories if story.end_time > now]
        counts["skipped"] += len(stories) - len(active)

        downloaded: list[tuple[Story, bytes]] = []
        for story in active:
            try:
                downloaded.append((story, services.nws.download_image(story)))
            except Exception:
                logger.exception(
                    "Failed to download story image",
                    extra={"office": office.office_id, "title": story.title},
                )
                counts["failed"] += 1

        accepted = _reject_ambiguous(office, downloaded)
        counts["rejected"] += len(downloaded) - len(accepted)

        for story, image in accepted:
            try:
                status = _process_story(office, story, image, services)
            except Exception:
                logger.exception(
                    "Failed to process story",
                    extra={"office": office.office_id, "title": story.title},
                )
                counts["failed"] += 1
                continue
            counts[{Status.NEW: "posted", Status.UPDATED: "updated"}.get(status, "skipped")] += 1
    return summary


_AMBIGUITY_CHECKS: tuple[tuple[str, Callable[[Story, bytes], str]], ...] = (
    ("duplicate_image_id", lambda story, _: story.image_id),
    ("duplicate_title_and_start", lambda story, _: story_key(story)),
    ("duplicate_image", lambda _, image: image_sha256(image)),
)


def _reject_ambiguous(
    office: OfficeConfig, downloaded: list[tuple[Story, bytes]]
) -> list[tuple[Story, bytes]]:
    """Drop every story sharing an image ID, title and start time, or image with another.

    NWS data is untrusted: when listed stories collide, there's no telling which is right.
    The `nws-ambiguous` alarm's metric filter matches the exact ERROR message.
    """
    reasons: dict[int, list[str]] = {}
    for reason, key in _AMBIGUITY_CHECKS:
        values = [key(story, image) for story, image in downloaded]
        occurrences = Counter(values)
        for index, value in enumerate(values):
            if occurrences[value] > 1:
                reasons.setdefault(index, []).append(reason)
    if reasons:
        logger.error(
            "Ambiguous stories from NWS",
            extra={
                "office": office.office_id,
                "stories": [
                    {
                        "image_id": downloaded[index][0].image_id,
                        "title": downloaded[index][0].title,
                        "reasons": story_reasons,
                    }
                    for index, story_reasons in reasons.items()
                ],
            },
        )
    return [item for index, item in enumerate(downloaded) if index not in reasons]


def _process_story(office: OfficeConfig, story: Story, image: bytes, services: Services) -> Status:
    """Post a new story, repost a changed one and delete its old message, or skip it."""
    fingerprint = content_fingerprint(story, image)
    current = services.store.find_story(office.office_id, story_key(story))
    if current is not None and current.fingerprint == fingerprint:
        return Status.UNCHANGED

    status = Status.NEW if current is None else Status.UPDATED
    prefix = services.archive.save(story, image, fingerprint)
    message_id = post_story(
        services.telegram,
        office.chat_id,
        office.office_id,
        story,
        image,
        updated=status is Status.UPDATED,
    )
    # Recorded only after Telegram accepts it: a failure here may cause a repost, never a miss.
    services.store.record_posted(story, message_id, prefix, fingerprint)
    logger.info(
        "Story posted",
        extra={
            "office": office.office_id,
            "image_id": story.image_id,
            "status": str(status),
            "telegram_message_id": message_id,
            "archive_prefix": prefix,
        },
    )
    if current is not None:
        _delete_replaced_message(services.telegram, office, story, current)
    return status


def _delete_replaced_message(
    telegram: TelegramClient, office: OfficeConfig, story: Story, replaced: PostedRecord
) -> None:
    """Delete the message a repost replaced; if Telegram refuses, both stay in the channel."""
    try:
        telegram.delete_message(office.chat_id, replaced.telegram_message_id)
    except TelegramError as exc:
        logger.warning(
            "Telegram delete failed, old message kept",
            extra={
                "office": office.office_id,
                "image_id": story.image_id,
                "telegram_message_id": replaced.telegram_message_id,
                "error": str(exc),
            },
        )


def post_story(
    telegram: TelegramClient,
    chat_id: str,
    office_id: str,
    story: Story,
    image: bytes,
    *,
    updated: bool,
) -> int:
    """Caption and post one story image; shared by the Lambda and the local dry run."""
    caption = build_caption(story, office_id, updated=updated)
    return telegram.send_photo(chat_id, image, caption, f"{story.image_id}.png")


# Created on cold start and reused by warm invocations.
_services: Services | None = None


def _build_services(settings: Settings) -> Services:
    import boto3  # Provided by the Lambda runtime; dev-only dependency locally.

    token = boto3.client("ssm").get_parameter(
        Name=settings.telegram_token_param, WithDecryption=True
    )["Parameter"]["Value"]
    http = httpx.Client()
    return Services(
        nws=NwsClient(http, settings.nws_user_agent),
        store=PostedStore(boto3.client("dynamodb"), settings.state_table),
        archive=StoryArchive(boto3.client("s3"), settings.archive_bucket),
        telegram=TelegramClient(http, token),
    )


def lambda_handler(event: Any, context: Any) -> dict[str, dict[str, int]]:
    global _services
    configure_logging()
    settings = Settings.from_env()
    if _services is None:
        _services = _build_services(settings)

    summary = run(settings.offices, _services)
    logger.info("Run complete", extra={"summary": summary})
    if any(counts["failed"] for counts in summary.values()):
        raise ProcessingError(f"Some stories failed: {json.dumps(summary)}")
    return summary
