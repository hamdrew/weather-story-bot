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
from weather_story_bot.history import StoryHistory
from weather_story_bot.models import Story
from weather_story_bot.nws import NwsClient
from weather_story_bot.planner import Decision, Outcome, decide, select_active
from weather_story_bot.state import (
    EventKind,
    OfficeLease,
    PostedRecord,
    PostedStore,
    content_fingerprint,
    image_sha256,
    story_key,
)
from weather_story_bot.telegram import TelegramClient, TelegramError, build_caption

logger = logging.getLogger("weather_story_bot")

_office: contextvars.ContextVar[str | None] = contextvars.ContextVar("office", default=None)


_base_record_factory = logging.getLogRecordFactory()


def _record_with_office(*args: Any, **kwargs: Any) -> logging.LogRecord:
    """Add `office` to every log record created while an office is being processed.

    Set once per office by `run()` (via `_office_context`), instead of every caller passing it
    through `extra`. `ContextVar.set`'s token makes each scope's cleanup exact, even on an
    exception, rather than relying on a plain attribute someone remembers to reset. A record
    factory rather than a logger filter, because a logger's filters never see its child
    loggers' records (`weather_story_bot.telegram`, `.nws`, `.history`). Installed at import
    time, chained to the factory already in place, so it applies when tests call `run()`
    directly without `configure_logging`. Callers must not pass `office` in `extra`: logging
    refuses to overwrite a record attribute and raises `KeyError`.
    """
    record = _base_record_factory(*args, **kwargs)
    office = _office.get()
    if office is not None:
        record.office = office
    return record


logging.setLogRecordFactory(_record_with_office)


@contextmanager
def _office_context(office_id: str) -> Generator[None]:
    token = _office.set(office_id)
    try:
        yield
    finally:
        _office.reset(token)


def configure_logging() -> None:
    # Keep this equal to `application_log_level` in infra/lambda.tf. No handler or formatter is
    # added here: the Lambda runtime's JSON formatter writes the lines (FR-002).
    logging.getLogger().setLevel(logging.INFO)
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
    history: StoryHistory
    archive: StoryArchive
    telegram: TelegramClient


def run(
    offices: tuple[OfficeConfig, ...],
    services: Services,
    *,
    now: datetime | None = None,
    aws_request_id: str | None = None,
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
                logger.exception(
                    "Failed to take office lease", extra={"event": "office.lease_failed"}
                )
                counts["failed"] += 1
                continue
            if holder is None:
                logger.info("Office run already in progress")
                counts["skipped"] += 1
                continue
            try:
                stories_seen = _run_office(office, services, now, counts)
            finally:
                _release_lease(services.lease, office.office_id, holder)
            # Only runs that held the lease are recorded: a missing RUN# item means no run.
            services.history.record_run(
                office.office_id,
                at=now,
                nws_failed=stories_seen is None,
                stories_seen=stories_seen or 0,
                counts=counts,
                aws_request_id=aws_request_id,
            )
    return summary


def _run_office(
    office: OfficeConfig, services: Services, now: datetime, counts: dict[str, int]
) -> int | None:
    """List, download, decide and act for one office, while holding its lease.

    Returns how many stories NWS listed, or `None` if the listing failed.
    """
    try:
        stories = services.nws.list_stories(office.office_id)
    except Exception:
        logger.exception("Failed to list stories", extra={"event": "nws.list_failed"})
        counts["failed"] += 1
        return None

    # The office catch-all, inside the lease so the run is still recorded
    # as one that saw NWS. Per-step catches below keep their own, more specific messages.
    try:
        _act_on_stories(office, stories, services, now, counts)
    except Exception:
        logger.exception("Failed to process office", extra={"event": "office.process_failed"})
        counts["failed"] += 1
    return len(stories)


def _act_on_stories(
    office: OfficeConfig,
    stories: list[Story],
    services: Services,
    now: datetime,
    counts: dict[str, int],
) -> None:
    """Download, decide and act on one office's listing."""
    active, expired = select_active(stories, now)
    counts["skipped"] += len(expired)

    downloaded: list[tuple[Story, bytes]] = []
    for story in active:
        try:
            downloaded.append((story, services.nws.download_image(story)))
        except Exception:
            logger.exception(
                "Failed to download story image",
                extra={"event": "nws.image_download_failed", "title": story.title},
            )
            counts["failed"] += 1

    # All or nothing: deciding without a record would repost its story, and dropping the story
    # would hide it from the ambiguity checks, so one failed read fails the office.
    records: dict[str, PostedRecord] = {}
    try:
        for story, _ in downloaded:
            record = services.store.find_story(story)
            if record is not None:
                records[story_key(story)] = record
    except Exception:
        logger.exception("Failed to read posted stories", extra={"event": "store.read_failed"})
        counts["failed"] += 1
        return
    decisions = decide(office.office_id, downloaded, records, now)
    _apply_decisions(office, decisions, services, now, counts)


def _release_lease(lease: OfficeLease, office_id: str, holder: str) -> None:
    """Free the office for the next run; if this fails, the lease expires before that run."""
    try:
        lease.release(office_id, holder)
    except (BotoCoreError, ClientError) as exc:
        logger.warning(
            "Office lease release failed",
            extra={"event": "office.lease_release_failed", "error": repr(exc)},
        )


def _apply_decisions(
    office: OfficeConfig,
    decisions: list[Decision],
    services: Services,
    now: datetime,
    counts: dict[str, int],
) -> None:
    """Log and record rejections once per office, then act on every remaining decision."""
    rejected = [d for d in decisions if d.outcome is Outcome.REJECTED]
    if rejected:
        # The `nws-ambiguous` alarm's metric filter counts the event `nws.ambiguous_stories`.
        logger.error(
            "Ambiguous stories from NWS",
            extra={
                "event": "nws.ambiguous_stories",
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
    for decision in rejected:
        _record_rejection(services.history, decision)

    for decision in decisions:
        if decision.outcome is Outcome.REJECTED:
            continue
        if decision.outcome is Outcome.UNCHANGED:
            counts["skipped"] += 1
            if decision.record is not None:
                services.history.touch_last_seen(
                    decision.story, decision.record.last_seen_at, now=now
                )
            continue
        try:
            _apply_post_or_update(office, decision, services)
        except Exception:
            logger.exception(
                "Failed to process story",
                extra={"event": "story.process_failed", "title": decision.story.title},
            )
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
    # The posted/updated ledger event is part of the same transaction.
    services.store.record_posted(
        story,
        message_id,
        prefix,
        fingerprint,
        image_sha256=image_sha256(image),
        posted_at=datetime.now(UTC),
        updated=decision.outcome is Outcome.UPDATE,
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
    delete_event: tuple[EventKind, datetime] | None = None
    if replaced is not None:
        deleted = _delete_replaced_message(services.telegram, office, story, replaced)
        delete_event = (
            EventKind.DELETED if deleted else EventKind.DELETE_FAILED,
            datetime.now(UTC),
        )

    # History goes after the whole chain, never between its steps.
    if replaced is not None and delete_event is not None:
        kind, deleted_at = delete_event
        services.history.record_deletion(story, replaced, kind, at=deleted_at)


def _delete_replaced_message(
    telegram: TelegramClient, office: OfficeConfig, story: Story, replaced: PostedRecord
) -> bool:
    """Delete the message a repost replaced; if Telegram refuses, both stay in the channel."""
    try:
        telegram.delete_message(office.chat_id, replaced.telegram_message_id)
    except TelegramError as exc:
        logger.warning(
            "Telegram delete failed, old message kept",
            extra={
                "event": "telegram.delete_failed",
                "image_id": story.image_id,
                "telegram_message_id": replaced.telegram_message_id,
                "error": repr(exc),
            },
        )
        return False
    return True


def _record_rejection(history: StoryHistory, decision: Decision) -> None:
    fingerprint = (
        content_fingerprint(decision.story, decision.image) if decision.image is not None else None
    )
    history.record_event(
        decision.story,
        EventKind.REJECTED,
        # Read per event: stories rejected as duplicate_title_and_start share a story_key.
        at=datetime.now(UTC),
        fingerprint=fingerprint,
        reasons=decision.reasons,
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
        history=StoryHistory(dynamodb, settings.state_table),
        archive=StoryArchive(boto3.client("s3"), settings.archive_bucket),
        telegram=TelegramClient(http, token),
    )


def lambda_handler(event: Any, context: Any) -> dict[str, dict[str, int]]:
    global _services
    configure_logging()
    settings = Settings.from_env()
    if _services is None:
        _services = _build_services(settings)

    summary = run(settings.offices, _services, aws_request_id=context.aws_request_id)
    logger.info("Run complete", extra={"summary": summary})
    if any(counts["failed"] for counts in summary.values()):
        raise ProcessingError(f"Some stories failed: {json.dumps(summary)}")
    return summary
