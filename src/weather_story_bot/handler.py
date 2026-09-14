"""Lambda entry point: find new or updated Weather Stories, archive them, and post them."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from weather_story_bot.archive import StoryArchive
from weather_story_bot.config import OfficeConfig, Settings
from weather_story_bot.models import Story
from weather_story_bot.nws import NwsClient
from weather_story_bot.state import PostedStore, Status, classify, content_fingerprint
from weather_story_bot.telegram import TelegramClient, build_caption

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


def run(offices: tuple[OfficeConfig, ...], services: Services) -> dict[str, dict[str, int]]:
    """Process every office, isolating failures per office and per story."""
    summary: dict[str, dict[str, int]] = {}
    for office in offices:
        counts = {"posted": 0, "updated": 0, "skipped": 0, "failed": 0}
        summary[office.office_id] = counts
        try:
            stories = services.nws.list_stories(office.office_id)
        except Exception:
            logger.exception("Failed to list stories", extra={"office": office.office_id})
            counts["failed"] += 1
            continue

        for story in stories:
            try:
                status = _process_story(office, story, services)
            except Exception:
                logger.exception(
                    "Failed to process story",
                    extra={"office": office.office_id, "title": story.title},
                )
                counts["failed"] += 1
                continue
            counts[{Status.NEW: "posted", Status.UPDATED: "updated"}.get(status, "skipped")] += 1
    return summary


def _process_story(office: OfficeConfig, story: Story, services: Services) -> Status:
    image_id = story.image_id
    status = classify(story, services.store.get_update_time(office.office_id, image_id))
    if status is Status.SEEN:
        return status

    image = services.nws.download_image(story)
    fingerprint = content_fingerprint(story, image)
    original = services.store.find_by_fingerprint(office.office_id, fingerprint)
    if original is not None:
        # NWS re-issued an already-posted revision under a new image UUID.
        services.store.record_duplicate(story, original)
        logger.info(
            "Duplicate story skipped",
            extra={
                "office": office.office_id,
                "image_id": image_id,
                "duplicate_of": original.image_id,
                "telegram_message_id": original.telegram_message_id,
            },
        )
        return Status.DUPLICATE

    prefix = services.archive.save(story, image)
    message_id = post_story(
        services.telegram,
        office.chat_id,
        office.office_id,
        story,
        image,
        updated=status is Status.UPDATED,
    )
    # Recorded only after a successful post: a failure here may cause a repost, never a miss.
    services.store.record_posted(story, message_id, prefix, fingerprint)
    logger.info(
        "Story posted",
        extra={
            "office": office.office_id,
            "image_id": image_id,
            "status": str(status),
            "telegram_message_id": message_id,
            "archive_prefix": prefix,
        },
    )
    return status


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
