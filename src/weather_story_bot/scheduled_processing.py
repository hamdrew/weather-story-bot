"""Pure, single-office scheduling decisions for Weather Story publishing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Protocol
from uuid import uuid4

from weather_story_bot.config import OfficeRegistry
from weather_story_bot.history import (
    ImageMetadata,
    OutcomeCounts,
    PublicationOperation,
    PublicationReservation,
    RunStatus,
)
from weather_story_bot.image_retention import ImageRetentionError, ValidatedImage
from weather_story_bot.ingestion import (
    CollectionValidationError,
    NormalizedCollection,
    QuarantinedStoryItem,
    WeatherStory,
)
from weather_story_bot.nws_client import NWSCollectionRequestError
from weather_story_bot.telegram import PublicationResult, TelegramOutcome

PROCESSING_SECONDS = 14 * 60
SHUTDOWN_RESERVE_SECONDS = 60
MAX_ELIGIBLE_REVISIONS = 25


class ScheduledHistory(Protocol):
    def put_quarantine(self, run_id: str, item: QuarantinedStoryItem) -> None: ...
    def put_deferral(self, run_id: str, story: WeatherStory, reason: str) -> None: ...
    def expire_due_stories(self, office_id: str, *, now: datetime | None = None) -> int: ...
    def observe_story(
        self, story: WeatherStory, *, image_sha256: str | None = None
    ) -> tuple[str, bool]: ...
    def get_current_story(
        self, office_id: str, source_story_id: str
    ) -> dict[str, object] | None: ...
    def reserve_publication(
        self,
        *,
        run_id: str,
        office_id: str,
        source_story_id: str,
        revision_hash: str,
        operation: PublicationOperation,
        reservation_owner: str,
        target_message_ref: str | None = None,
    ) -> PublicationReservation | None: ...
    def put_run(
        self,
        run_id: str,
        office_id: str,
        *,
        collection_outcome: str,
        status: RunStatus,
        started_at: datetime,
        completed_at: datetime,
        required_work_completed: bool,
        counts: OutcomeCounts,
        failure_reasons: tuple[str, ...] = (),
    ) -> None: ...


class CollectionRetriever(Protocol):
    def retrieve(
        self, registry: OfficeRegistry, office_id: str, *, processing_deadline: float
    ) -> NormalizedCollection: ...


class Retainer(Protocol):
    def download(self, url: str) -> ValidatedImage: ...

    def retain(
        self,
        *,
        office_id: str,
        source_story_id: str,
        revision_hash: str,
        url: str,
        image: ValidatedImage,
    ) -> ImageMetadata: ...


class ReservedPublisher(Protocol):
    def publish(
        self, reservation: PublicationReservation, image: ImageMetadata, story: WeatherStory
    ) -> PublicationResult: ...


@dataclass(frozen=True)
class ScheduledRun:
    run_id: str
    status: RunStatus
    counts: OutcomeCounts
    required_work_completed: bool


class OfficeScheduledProcessor:
    """Process one active office; all effects are injected behind narrow protocols."""

    def __init__(
        self,
        registry: OfficeRegistry,
        retriever: CollectionRetriever,
        history: ScheduledHistory,
        retainer: Retainer,
        publisher: ReservedPublisher,
        *,
        worker_id: str = "publisher",
        clock: Callable[[], float] = monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        run_id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._registry, self._retriever, self._history = registry, retriever, history
        self._retainer, self._publisher, self._worker_id = retainer, publisher, worker_id
        self._clock, self._wall_clock, self._run_id_factory = clock, wall_clock, run_id_factory

    def process_office(self, office_id: str) -> ScheduledRun:
        office = next(
            (entry for entry in self._registry.offices if entry.office_id == office_id), None
        )
        if office is None or not office.active:
            raise ValueError("scheduled processing requires exactly one active office")
        run_id, started = self._run_id_factory(), self._wall_clock()
        deadline = self._clock() + PROCESSING_SECONDS
        try:
            self._history.expire_due_stories(office_id, now=started)
        except Exception:
            return self._finish(
                run_id, office_id, started, "not_started", OutcomeCounts(), ("expiration_failed",)
            )
        try:
            collection = self._retriever.retrieve(
                self._registry, office_id, processing_deadline=deadline
            )
        except (NWSCollectionRequestError, CollectionValidationError):
            return self._finish(
                run_id, office_id, started, "failed", OutcomeCounts(), ("collection_failed",)
            )

        try:
            for item in collection.quarantined:
                self._history.put_quarantine(run_id, item)
        except Exception:
            return self._finish(
                run_id,
                office_id,
                started,
                "success",
                OutcomeCounts(discovered=len(collection.stories)),
                ("quarantine_persistence_failed",),
            )
        eligible = tuple(story for story in collection.stories if story.end_time > started)
        ordered = sorted(eligible, key=lambda story: (not story.priority, story.order))
        cap_deferred = list(ordered[MAX_ELIGIBLE_REVISIONS:])
        selected = ordered[:MAX_ELIGIBLE_REVISIONS]
        budget_deferred: list[WeatherStory] = []
        counts = OutcomeCounts(
            discovered=len(collection.stories), quarantined=len(collection.quarantined)
        )
        failures: list[str] = []
        for index, story in enumerate(selected):
            if self._clock() >= deadline - SHUTDOWN_RESERVE_SECONDS:
                budget_deferred.extend(selected[index:])
                break
            counts, failure = self._process_story(
                run_id, office.telegram_channel_id or "", story, counts
            )
            if failure:
                failures.append(failure)
        try:
            for story in cap_deferred:
                self._history.put_deferral(run_id, story, "story_cap")
            for story in budget_deferred:
                self._history.put_deferral(run_id, story, "run_budget")
        except Exception:
            return self._finish(
                run_id,
                office_id,
                started,
                "success",
                counts,
                tuple([*failures, "deferral_persistence_failed"]),
            )
        deferred = cap_deferred + budget_deferred
        counts = counts.increment("deferred", len(deferred))
        if failures:
            return self._finish(run_id, office_id, started, "success", counts, tuple(failures))
        if deferred:
            status = RunStatus.SUCCESS_WITH_DEFERRED
        elif collection.quarantined:
            status = RunStatus.SUCCESS_WITH_QUARANTINED_ITEMS
        else:
            status = RunStatus.SUCCESS
        return self._finish(run_id, office_id, started, "success", counts, (), status=status)

    def _process_story(
        self, run_id: str, channel: str, story: WeatherStory, counts: OutcomeCounts
    ) -> tuple[OutcomeCounts, str | None]:
        try:
            downloaded = self._retainer.download(str(story.download_url))
        except ImageRetentionError:
            return counts, "image_invalid"
        digest, changed = self._history.observe_story(story, image_sha256=downloaded.sha256_hex)
        if not changed:
            return counts.increment("skipped"), None
        try:
            image = self._retainer.retain(
                office_id=story.office_id,
                source_story_id=story.source_story_id,
                revision_hash=digest,
                url=str(story.download_url),
                image=downloaded,
            )
        except ImageRetentionError:
            return counts, "image_invalid"
        current = self._history.get_current_story(story.office_id, story.source_story_id) or {}
        message_ref = current.get("telegram_message_ref")
        target = str(message_ref) if message_ref is not None else None
        operation = PublicationOperation.EDIT if target else PublicationOperation.CREATE
        reservation = self._history.reserve_publication(
            run_id=run_id,
            office_id=story.office_id,
            source_story_id=story.source_story_id,
            revision_hash=digest,
            operation=operation,
            reservation_owner=self._worker_id,
            target_message_ref=target,
        )
        if reservation is None:
            return counts.increment("skipped"), None
        result = self._publisher.publish(reservation, image, story)
        if result.outcome is TelegramOutcome.PUBLISHED:
            if operation is PublicationOperation.EDIT:
                return counts.increment("edited"), None
            return counts.increment("published"), None
        if result.outcome is TelegramOutcome.AMBIGUOUS:
            return counts.increment("ambiguous"), "publication_ambiguous"
        return counts.increment("rejected"), "publication_rejected"

    def _finish(
        self,
        run_id: str,
        office_id: str,
        started: datetime,
        collection_outcome: str,
        counts: OutcomeCounts,
        failures: tuple[str, ...],
        *,
        status: RunStatus = RunStatus.FAILED,
    ) -> ScheduledRun:
        completed = self._wall_clock()
        self._history.put_run(
            run_id,
            office_id,
            collection_outcome=collection_outcome,
            status=status,
            started_at=started,
            completed_at=completed,
            required_work_completed=status is not RunStatus.FAILED,
            counts=counts,
            failure_reasons=failures[:8],
        )
        return ScheduledRun(run_id, status, counts, status is not RunStatus.FAILED)
