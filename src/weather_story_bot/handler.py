"""Lambda entry point: validate active Weather Stories, then post new and changed ones."""

from __future__ import annotations

import contextvars
import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from botocore.exceptions import BotoCoreError, ClientError

from weather_story_bot.archive import StoryArchive
from weather_story_bot.config import OfficeConfig, Settings
from weather_story_bot.models import Story
from weather_story_bot.nws import NwsClient
from weather_story_bot.planner import Decision, Outcome, decide, select_active
from weather_story_bot.state import (
    OfficeLease,
    PostedRecord,
    PostedStore,
    content_fingerprint,
    image_sha256,
    story_key,
)
from weather_story_bot.telegram import TelegramClient, TelegramError, build_caption

logger = logging.getLogger("weather_story_bot")

_STANDARD_LOG_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


_aws_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "aws_request_id", default=None
)
_office: contextvars.ContextVar[str | None] = contextvars.ContextVar("office", default=None)


class _RequestContextFilter(logging.Filter):
    """Adds `office` and `aws_request_id` to every line this logger emits.

    Set once per invocation (`aws_request_id`, via `_invocation_context`, from the Lambda
    context) and once per office within it (`office`, via `_office_context`), instead of every
    caller passing them through `extra`. `ContextVar.set`'s token makes each scope's cleanup
    exact, even on an exception, rather than relying on a plain attribute someone remembers to
    reset. Attached once, at import time, to the `weather_story_bot` logger itself, so it still
    applies when tests call `run()` directly without `configure_logging`.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        aws_request_id = _aws_request_id.get()
        if aws_request_id is not None:
            record.aws_request_id = aws_request_id
        office = _office.get()
        if office is not None:
            record.office = office
        return True


logger.addFilter(_RequestContextFilter())


@contextmanager
def _invocation_context(aws_request_id: str) -> Generator[None]:
    token = _aws_request_id.set(aws_request_id)
    try:
        yield
    finally:
        _aws_request_id.reset(token)


@contextmanager
def _office_context(office_id: str) -> Generator[None]:
    token = _office.set(office_id)
    try:
        yield
    finally:
        _office.reset(token)


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
    lease: OfficeLease
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
        with _office_context(office.office_id):
            try:
                holder = services.lease.take(office.office_id, now)
            except Exception:
                logger.exception("Failed to take office lease")
                counts["failed"] += 1
                continue
            if holder is None:
                logger.info("Office run already in progress")
                counts["skipped"] += 1
                continue
            try:
                _run_office(office, services, now, counts)
            finally:
                _release_lease(services.lease, office.office_id, holder)
    return summary


def _run_office(
    office: OfficeConfig, services: Services, now: datetime, counts: dict[str, int]
) -> None:
    """List, download, decide and act for one office, while holding its lease."""
    try:
        stories = services.nws.list_stories(office.office_id)
    except Exception:
        logger.exception("Failed to list stories")
        counts["failed"] += 1
        return

    active, expired = select_active(stories, now)
    counts["skipped"] += len(expired)

    downloaded: list[tuple[Story, bytes]] = []
    for story in active:
        try:
            downloaded.append((story, services.nws.download_image(story)))
        except Exception:
            logger.exception("Failed to download story image", extra={"title": story.title})
            counts["failed"] += 1

    records: dict[str, PostedRecord] = {}
    for story, _ in downloaded:
        record = services.store.find_story(story)
        if record is not None:
            records[story_key(story)] = record
    decisions = decide(office.office_id, downloaded, records, now)
    _apply_decisions(office, decisions, services, counts)


def _release_lease(lease: OfficeLease, office_id: str, holder: str) -> None:
    """Free the office for the next run; if this fails, the lease expires before that run."""
    try:
        lease.release(office_id, holder)
    except (BotoCoreError, ClientError) as exc:
        logger.warning("Office lease release failed", extra={"error": str(exc)})


def _apply_decisions(
    office: OfficeConfig, decisions: list[Decision], services: Services, counts: dict[str, int]
) -> None:
    """Log rejections once per office, then act on every remaining decision in order."""
    rejected = [d for d in decisions if d.outcome is Outcome.REJECTED]
    if rejected:
        # The `nws-ambiguous` alarm's metric filter matches this exact ERROR message.
        logger.error(
            "Ambiguous stories from NWS",
            extra={
                "stories": [
                    {
                        "image_id": decision.story.image_id,
                        "title": decision.story.title,
                        "reasons": list(decision.reasons),
                    }
                    for decision in rejected
                ],
            },
        )
    counts["rejected"] += len(rejected)

    for decision in decisions:
        if decision.outcome is Outcome.REJECTED:
            continue
        if decision.outcome is Outcome.UNCHANGED:
            counts["skipped"] += 1
            continue
        try:
            _apply_post_or_update(office, decision, services)
        except Exception:
            logger.exception("Failed to process story", extra={"title": decision.story.title})
            counts["failed"] += 1
            continue
        counts["posted" if decision.outcome is Outcome.POST else "updated"] += 1


def _apply_post_or_update(office: OfficeConfig, decision: Decision, services: Services) -> None:
    """Post a new story or repost a changed one, then delete the message it replaces."""
    story, image = decision.story, decision.image
    if image is None:
        raise AssertionError("unreachable")  # post/update decisions always carry their image

    fingerprint = content_fingerprint(story, image)
    prefix = services.archive.save(story, image, fingerprint)
    message_id = post_story(
        services.telegram,
        office.chat_id,
        office.office_id,
        story,
        image,
        updated=decision.outcome is Outcome.UPDATE,
    )
    # Recorded only after Telegram accepts it: a failure here may cause a repost, never a miss.
    services.store.record_posted(
        story, message_id, prefix, fingerprint, image_sha256=image_sha256(image)
    )
    extra: dict[str, Any] = {
        "image_id": story.image_id,
        "status": "new" if decision.outcome is Outcome.POST else "updated",
        "telegram_message_id": message_id,
        "archive_prefix": prefix,
        "fingerprint": fingerprint,
    }
    replaced = decision.record
    if replaced is not None:
        extra |= {
            "changes": list(decision.changes),
            "previous_image_id": replaced.image_id,
            "previous_fingerprint": replaced.fingerprint,
            "previous_archive_prefix": replaced.archive_prefix,
        }
    logger.info("Story posted", extra=extra)
    if replaced is not None:
        _delete_replaced_message(services.telegram, office, story, replaced)


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
    dynamodb = boto3.client("dynamodb")
    return Services(
        nws=NwsClient(http, settings.nws_user_agent),
        store=PostedStore(dynamodb, settings.state_table),
        lease=OfficeLease(dynamodb, settings.state_table),
        archive=StoryArchive(boto3.client("s3"), settings.archive_bucket),
        telegram=TelegramClient(http, token),
    )


def lambda_handler(event: Any, context: Any) -> dict[str, dict[str, int]]:
    global _services
    configure_logging()
    with _invocation_context(context.aws_request_id):
        settings = Settings.from_env()
        if _services is None:
            _services = _build_services(settings)

        summary = run(settings.offices, _services)
        logger.info("Run complete", extra={"summary": summary})
        if any(counts["failed"] for counts in summary.values()):
            raise ProcessingError(f"Some stories failed: {json.dumps(summary)}")
        return summary
