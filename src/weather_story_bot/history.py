"""Current Weather Story state and immutable operational audit records."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from json import dumps
from typing import Any, Literal, Protocol, cast
from uuid import uuid4

from boto3.dynamodb.conditions import Attr, Key

from weather_story_bot.config import OfficeRegistryRecord
from weather_story_bot.ingestion import QuarantinedStoryItem, WeatherStory

MAX_FAILURE_REASONS = 8
MAX_FAILURE_SUMMARY_LENGTH = 256
CURRENT_INDEX_NAME = "office-current-index"
OPERATIONAL_RECORD_TTL_DAYS = 30
PUBLICATION_LEASE_SECONDS = 60


class RunStatus(StrEnum):
    """The only persisted terminal statuses for a single-office run."""

    SUCCESS = "success"
    SUCCESS_WITH_DEFERRED = "success_with_deferred"
    SUCCESS_WITH_QUARANTINED_ITEMS = "success_with_quarantined_items"
    FAILED = "failed"


class ImageStatus(StrEnum):
    """Usability state for a current story image reference."""

    PENDING = "image_pending"
    COMMITTED = "committed"
    INVALID = "invalid"


class AttemptState(StrEnum):
    """Persisted publication states for one Telegram publication attempt."""

    RESERVED = "reserved"
    SEND_STARTED = "send_started"
    PUBLISHED = "published"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"
    CONFIRMED_RECEIVED = "confirmed_received"
    CONFIRMED_NOT_RECEIVED = "confirmed_not_received"


class PublicationOperation(StrEnum):
    """The Telegram operation protected by a publication reservation."""

    CREATE = "create"
    EDIT = "edit"


@dataclass(frozen=True)
class PublicationReservation:
    """A successfully acquired, single-use lease for one story revision."""

    attempt_id: str
    run_id: str
    office_id: str
    source_story_id: str
    revision_hash: str
    operation: PublicationOperation
    reservation_owner: str
    lease_expires_at: datetime
    target_message_ref: str | None = None


@dataclass(frozen=True)
class OutcomeCounts:
    """Per-office and invocation aggregate outcome counts."""

    discovered: int = 0
    published: int = 0
    edited: int = 0
    skipped: int = 0
    deferred: int = 0
    quarantined: int = 0
    rejected: int = 0
    ambiguous: int = 0

    def __post_init__(self) -> None:
        if any(value < 0 for value in asdict(self).values()):
            raise ValueError("outcome counts cannot be negative")

    def increment(self, field: OutcomeField, value: int = 1) -> OutcomeCounts:
        """Return counts with one named outcome advanced by a non-negative amount."""
        if value < 0:
            raise ValueError("outcome increment cannot be negative")
        return replace(self, **{field: getattr(self, field) + value})


OutcomeField = Literal[
    "discovered",
    "published",
    "edited",
    "skipped",
    "deferred",
    "quarantined",
    "rejected",
    "ambiguous",
]


@dataclass(frozen=True)
class ImageMetadata:
    """Verified metadata for a retained image object."""

    key: str
    content_type: str
    byte_size: int
    sha256_hex: str
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.key.startswith("staging/") or not self.key:
            raise ValueError("committed image keys must not use staging/")
        if self.byte_size <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("image metadata dimensions and size must be positive")


class DynamoTable(Protocol):
    """Native-type DynamoDB table operations used by the history service."""

    def put_item(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def get_item(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def update_item(self, **kwargs: Any) -> Mapping[str, Any]: ...

    def query(self, **kwargs: Any) -> Mapping[str, Any]: ...


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def timestamp(value: datetime) -> str:
    """Serialize timestamps consistently for DynamoDB and query ordering."""
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def revision_hash(story: WeatherStory, image_sha256: str | None = None) -> str:
    """Return the stable hash of normalized source fields and image identity."""
    document = {
        "alt_text": story.alt_text,
        "description": story.description,
        "download_url": str(story.download_url),
        "end_time": timestamp(story.end_time),
        "image_sha256": image_sha256,
        "order": story.order,
        "priority": story.priority,
        "start_time": timestamp(story.start_time),
        "title": story.title,
        "update_time": timestamp(story.update_time),
    }
    return sha256(dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class HistoryStore:
    """Store mutable current stories and immutable operational audit records."""

    def __init__(self, table: DynamoTable, *, clock: Callable[[], datetime] = utc_now) -> None:
        self._table = table
        self._clock = clock

    def put_office(
        self,
        office: OfficeRegistryRecord,
        *,
        pinned_message_ref: str | None = None,
        invite_ref: str | None = None,
    ) -> None:
        """Persist the enriched office record without exposing private values in keys."""
        item: dict[str, object] = {
            "pk": f"OFFICE#{office.office_id}",
            "sk": f"METADATA#{timestamp(self._clock())}",
            "record_type": "office",
            "office_id": office.office_id,
            "weather_stories_url": str(office.weather_stories_url),
            "display_name": office.display_name,
            "address": office.address.model_dump(),
            "coordinates": office.coordinates.model_dump(),
            "timezone": office.timezone,
            "telegram_channel_id": office.telegram_channel_id,
            "active": office.active,
            "telephone": office.telephone,
            "email": office.email,
            "office_home_url": str(office.office_home_url) if office.office_home_url else None,
            "region_name": office.region_name,
            "region_home_url": str(office.region_home_url) if office.region_home_url else None,
            "pinned_message_ref": pinned_message_ref,
            "invite_ref": invite_ref,
            "recorded_at": timestamp(self._clock()),
        }
        self._table.put_item(Item=_without_none(item), ConditionExpression=Attr("sk").not_exists())

    def get_current_office(self, office_id: str) -> dict[str, object] | None:
        """Return the one retained current-office record for an authorized review."""
        return self._get_current_record(f"OFFICE#{office_id}")

    def get_current_story(self, office_id: str, source_story_id: str) -> dict[str, object] | None:
        """Return retained current state, first-seen facts, and image metadata for one story."""
        return self._get_current_record(_story_pk(office_id, source_story_id))

    def list_current_stories(self, office_id: str) -> list[dict[str, object]]:
        """List an office's retained current stories by source expiration without a table scan."""
        return self._query_all(
            IndexName=CURRENT_INDEX_NAME,
            KeyConditionExpression=Key("office_current_pk").eq(f"OFFICE#{office_id}"),
            ConsistentRead=False,
        )

    def get_run_result(self, run_id: str) -> dict[str, object] | None:
        """Return a non-expired immutable result for one single-office invocation."""
        return self._get_operational_record(f"RUN#{run_id}", "RESULT")

    def list_quarantined_items(self, run_id: str) -> list[dict[str, object]]:
        """Return non-expired bounded validation facts for a run, in source-array order."""
        return self._operational_query(
            KeyConditionExpression=Key("pk").eq(f"QUARANTINE#{run_id}")
            & Key("sk").begins_with("ITEM#")
        )

    def get_publication_attempt(
        self, attempt_id: str
    ) -> tuple[dict[str, object], list[dict[str, object]]] | None:
        """Return an attempt and its append-only transitions for authorized reconciliation review.

        The returned transition metadata was sanitized at write time.  Expired operational
        records are intentionally treated as unavailable even while DynamoDB TTL deletion is
        pending.
        """
        attempt = self._get_operational_record(f"ATTEMPT#{attempt_id}", "RECORD")
        if attempt is None:
            return None
        transitions = self._operational_query(
            KeyConditionExpression=Key("pk").eq(f"ATTEMPT#{attempt_id}")
            & Key("sk").begins_with("TRANSITION#"),
            ConsistentRead=True,
        )
        return attempt, transitions

    def _get_current_record(self, pk: str) -> dict[str, object] | None:
        response = self._table.get_item(Key={"pk": pk, "sk": "CURRENT"}, ConsistentRead=True)
        item = response.get("Item")
        return dict(item) if isinstance(item, Mapping) else None

    def _get_operational_record(self, pk: str, sk: str) -> dict[str, object] | None:
        response = self._table.get_item(Key={"pk": pk, "sk": sk}, ConsistentRead=True)
        item = response.get("Item")
        if not isinstance(item, Mapping) or _is_operationally_expired(item, self._clock()):
            return None
        return dict(item)

    def _operational_query(self, **kwargs: object) -> list[dict[str, object]]:
        """Query operational history and hide records awaiting asynchronous TTL deletion."""
        return [
            item
            for item in self._query_all(**kwargs)
            if not _is_operationally_expired(item, self._clock())
        ]

    def _query_all(self, **kwargs: object) -> list[dict[str, object]]:
        """Read every page from a bounded DynamoDB key-family query without using Scan."""
        items: list[dict[str, object]] = []
        query_kwargs = dict(kwargs)
        while True:
            response = self._table.query(**query_kwargs)
            page = response.get("Items", [])
            if not isinstance(page, list):
                raise ValueError("DynamoDB query Items must be a list")
            items.extend(dict(item) for item in page if isinstance(item, Mapping))
            last_key = response.get("LastEvaluatedKey")
            if not isinstance(last_key, Mapping):
                return items
            query_kwargs["ExclusiveStartKey"] = dict(last_key)

    def observe_story(
        self, story: WeatherStory, *, image_sha256: str | None = None
    ) -> tuple[str, bool]:
        """Create or conditionally advance one current record for a story."""
        office_id, source_story_id = story.canonical_identity
        digest = revision_hash(story, image_sha256)
        now = timestamp(self._clock())
        story_pk = _story_pk(office_id, source_story_id)
        current_story = {
            "pk": story_pk,
            "sk": "CURRENT",
            "record_type": "story_current",
            "office_id": office_id,
            "source_story_id": source_story_id,
            "current_revision_hash": digest,
            "start_time": timestamp(story.start_time),
            "end_time": timestamp(story.end_time),
            "update_time": timestamp(story.update_time),
            "title": story.title,
            "description": story.description,
            "alt_text": story.alt_text,
            "priority": story.priority,
            "order": story.order,
            "download_url": str(story.download_url),
            "image_status": ImageStatus.PENDING,
            "first_seen_at": now,
            "last_seen_at": now,
            "office_current_pk": f"OFFICE#{office_id}",
            "office_current_sk": f"{timestamp(story.end_time)}#{source_story_id}",
            "lifecycle_status": "current",
        }
        try:
            self._table.put_item(Item=current_story, ConditionExpression=Attr("sk").not_exists())
        except Exception as error:  # DynamoDB's typed exception is client-specific.
            if not _is_conditional_failure(error):
                raise
            return digest, self._advance_current_story(story, digest, now)
        return digest, True

    def _advance_current_story(self, story: WeatherStory, digest: str, observed_at: str) -> bool:
        """Replace newer source state without overwriting delivery state or first seen time."""
        office_id, source_story_id = story.canonical_identity
        source_update_time = timestamp(story.update_time)
        try:
            self._table.update_item(
                Key={"pk": _story_pk(office_id, source_story_id), "sk": "CURRENT"},
                UpdateExpression=(
                    "SET record_type = :record_type, office_id = :office_id, "
                    "source_story_id = :source_story_id, current_revision_hash = :revision_hash, "
                    "start_time = :start_time, end_time = :end_time, update_time = :update_time, "
                    "title = :title, description = :description, alt_text = :alt_text, "
                    "priority = :priority, #order = :order, download_url = :download_url, "
                    "office_current_pk = :office_current_pk, "
                    "office_current_sk = :office_current_sk, "
                    "lifecycle_status = :current, image_status = :image_pending, "
                    "last_seen_at = :last_seen_at REMOVE image_failure"
                ),
                ExpressionAttributeNames={"#order": "order"},
                ExpressionAttributeValues={
                    ":record_type": "story_current",
                    ":office_id": office_id,
                    ":source_story_id": source_story_id,
                    ":revision_hash": digest,
                    ":start_time": timestamp(story.start_time),
                    ":end_time": timestamp(story.end_time),
                    ":update_time": source_update_time,
                    ":title": story.title,
                    ":description": story.description,
                    ":alt_text": story.alt_text,
                    ":priority": story.priority,
                    ":order": story.order,
                    ":download_url": str(story.download_url),
                    ":office_current_pk": f"OFFICE#{office_id}",
                    ":office_current_sk": f"{timestamp(story.end_time)}#{source_story_id}",
                    ":current": "current",
                    ":image_pending": ImageStatus.PENDING,
                    ":last_seen_at": observed_at,
                },
                ConditionExpression=(
                    Attr("update_time").not_exists()
                    | (
                        Attr("update_time").lte(source_update_time)
                        & Attr("current_revision_hash").ne(digest)
                    )
                ),
            )
        except Exception as error:
            if not _is_conditional_failure(error):
                raise
            self._table.update_item(
                Key={"pk": _story_pk(office_id, source_story_id), "sk": "CURRENT"},
                UpdateExpression="SET last_seen_at = :last_seen_at",
                ExpressionAttributeValues={":last_seen_at": observed_at},
            )
            return False
        return True

    def commit_image(
        self, office_id: str, source_story_id: str, digest: str, image: ImageMetadata
    ) -> ImageMetadata | None:
        """Make a verified current image usable; staging keys are rejected by the type."""
        key = {"pk": _story_pk(office_id, source_story_id), "sk": "CURRENT"}
        values = {":status": ImageStatus.COMMITTED, ":image": asdict(image)}
        response = self._table.update_item(
            Key=key,
            UpdateExpression="SET image_status = :status, image = :image",
            ExpressionAttributeValues=values,
            ConditionExpression=Attr("current_revision_hash").eq(digest)
            & Attr("image_status").eq(ImageStatus.PENDING),
            ReturnValues="ALL_OLD",
        )
        previous = response.get("Attributes", {}).get("image")
        if not isinstance(previous, Mapping):
            return None
        return ImageMetadata(
            key=str(previous["key"]),
            content_type=str(previous["content_type"]),
            byte_size=int(previous["byte_size"]),
            sha256_hex=str(previous["sha256_hex"]),
            width=int(previous["width"]),
            height=int(previous["height"]),
        )

    def mark_image_invalid(
        self, office_id: str, source_story_id: str, digest: str, reason: str
    ) -> None:
        """Record a bounded failure without ever storing raw upstream data."""
        try:
            self._table.update_item(
                Key={"pk": _story_pk(office_id, source_story_id), "sk": "CURRENT"},
                UpdateExpression="SET image_status = :status, image_failure = :reason",
                ExpressionAttributeValues={
                    ":status": ImageStatus.INVALID,
                    ":reason": reason[:MAX_FAILURE_SUMMARY_LENGTH],
                },
                ConditionExpression=Attr("current_revision_hash").eq(digest),
            )
        except Exception as error:
            if not _is_conditional_failure(error):
                raise

    def expire_due_stories(self, office_id: str, *, now: datetime | None = None) -> int:
        """Expire current stories whose source end time has passed."""
        now_value = timestamp(now or self._clock())
        response = self._table.query(
            IndexName=CURRENT_INDEX_NAME,
            KeyConditionExpression=Key("office_current_pk").eq(f"OFFICE#{office_id}")
            & Key("office_current_sk").lte(f"{now_value}#\uffff"),
            FilterExpression=Attr("lifecycle_status").eq("current"),
        )
        expired = 0
        for item in response.get("Items", []):
            try:
                self._table.update_item(
                    Key={"pk": item["pk"], "sk": "CURRENT"},
                    UpdateExpression="SET lifecycle_status = :expired",
                    ExpressionAttributeValues={":expired": "expired"},
                    ConditionExpression=Attr("lifecycle_status").eq("current")
                    & Attr("end_time").lte(now_value),
                )
            except Exception as error:
                if not _is_conditional_failure(error):
                    raise
            else:
                expired += 1
        return expired

    def put_quarantine(self, run_id: str, item: QuarantinedStoryItem) -> None:
        """Persist only bounded validation facts for malformed source items."""
        recorded_at = self._clock()
        self._table.put_item(
            Item={
                "pk": f"QUARANTINE#{run_id}",
                "sk": f"ITEM#{item.array_index:06d}",
                "record_type": "quarantine",
                "run_id": run_id,
                "array_index": item.array_index,
                "error_code": item.error_code[:64],
                "affected_field": item.affected_field[:64],
                "error_summary": item.error_summary[:MAX_FAILURE_SUMMARY_LENGTH],
                "recorded_at": timestamp(recorded_at),
                "expires_at": _operational_expiry(recorded_at),
            },
            ConditionExpression=Attr("sk").not_exists(),
        )

    def put_deferral(self, run_id: str, story: WeatherStory, reason: str) -> None:
        """Persist a bounded record for controlled, unstarted work only."""
        if reason not in {"story_cap", "run_budget"}:
            raise ValueError("deferral reason must be story_cap or run_budget")
        recorded_at = self._clock()
        self._table.put_item(
            Item={
                "pk": f"RUN#{run_id}",
                "sk": f"DEFERRAL#{story.office_id}#{story.source_story_id}",
                "record_type": "controlled_deferral",
                "run_id": run_id,
                "office_id": story.office_id,
                "source_story_id": story.source_story_id,
                "reason": reason,
                "recorded_at": timestamp(recorded_at),
                "expires_at": _operational_expiry(recorded_at),
            },
            ConditionExpression=Attr("sk").not_exists(),
        )

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
    ) -> None:
        """Write exactly one objective immutable result for one office invocation."""
        if len(failure_reasons) > MAX_FAILURE_REASONS:
            raise ValueError("failure_reasons exceed the bounded limit")
        elapsed_ms = int((completed_at - started_at).total_seconds() * 1000)
        if elapsed_ms < 0:
            raise ValueError("run completion cannot precede start")
        failures = tuple(reason[:MAX_FAILURE_SUMMARY_LENGTH] for reason in failure_reasons)
        self._table.put_item(
            Item={
                "pk": f"RUN#{run_id}",
                "sk": "RESULT",
                "record_type": "run_result",
                "run_id": run_id,
                "office_id": office_id,
                "collection_outcome": collection_outcome,
                "status": status,
                "started_at": timestamp(started_at),
                "completed_at": timestamp(completed_at),
                "elapsed_ms": elapsed_ms,
                "required_work_completed": required_work_completed,
                "counts": asdict(counts),
                "aggregate_counts": asdict(counts),
                "failure_reasons": failures,
                "expires_at": _operational_expiry(completed_at),
            },
            ConditionExpression=Attr("sk").not_exists(),
        )

    def update_alert_fingerprint(
        self,
        fingerprint: str,
        *,
        severity: str,
        run_id: str | None,
        cooldown_until: datetime,
        dispatch_outcome: str,
    ) -> bool:
        """Conditionally claim the immediate alert decision and increment occurrences."""
        now = self._clock()
        now_text = timestamp(now)
        try:
            self._table.update_item(
                Key={"pk": f"ALERT#{fingerprint}", "sk": "STATE"},
                UpdateExpression=(
                    "SET first_seen_at = if_not_exists(first_seen_at, :now), severity = :severity, "
                    "last_seen_at = :now, latest_run_id = :run, "
                    "cooldown_until = :cooldown, latest_dispatch_outcome = :outcome, "
                    "expires_at = :expires_at "
                    "ADD occurrence_count :one"
                ),
                ExpressionAttributeValues={
                    ":severity": severity,
                    ":now": now_text,
                    ":run": run_id,
                    ":cooldown": timestamp(cooldown_until),
                    ":outcome": dispatch_outcome,
                    ":expires_at": _operational_expiry(now),
                    ":one": 1,
                },
                ConditionExpression=Attr("cooldown_until").not_exists()
                | Attr("cooldown_until").lte(now_text),
            )
        except Exception as error:
            if not _is_conditional_failure(error):
                raise
            self._table.update_item(
                Key={"pk": f"ALERT#{fingerprint}", "sk": "STATE"},
                UpdateExpression=(
                    "SET last_seen_at = :now, latest_run_id = :run, expires_at = :expires_at "
                    "ADD occurrence_count :one"
                ),
                ExpressionAttributeValues={
                    ":now": now_text,
                    ":run": run_id,
                    ":expires_at": _operational_expiry(now),
                    ":one": 1,
                },
            )
            return False
        return True

    def put_attempt(
        self,
        attempt_id: str,
        *,
        run_id: str,
        office_id: str,
        source_story_id: str,
        revision_hash: str,
        operation: str,
        reservation_owner: str,
        lease_expires_at: datetime,
        target_message_ref: str | None = None,
    ) -> None:
        """Persist an immutable publication reservation audit record."""
        if operation not in {"create", "edit"}:
            raise ValueError("attempt operation must be create or edit")
        created_at = self._clock()
        self._table.put_item(
            Item=_without_none(
                {
                    "pk": f"ATTEMPT#{attempt_id}",
                    "sk": "RECORD",
                    "record_type": "publication_attempt",
                    "attempt_id": attempt_id,
                    "run_id": run_id,
                    "office_id": office_id,
                    "source_story_id": source_story_id,
                    "revision_hash": revision_hash,
                    "operation": operation,
                    "reservation_owner": reservation_owner,
                    "lease_expires_at": timestamp(lease_expires_at),
                    "target_message_ref": target_message_ref,
                    "created_at": timestamp(created_at),
                    "expires_at": _operational_expiry(created_at),
                }
            ),
            ConditionExpression=Attr("sk").not_exists(),
        )

    def append_transition(
        self,
        attempt_id: str,
        ordinal: int,
        *,
        prior_state: AttemptState | None,
        resulting_state: AttemptState,
        actor: str,
        response_metadata: Mapping[str, object] | None = None,
        error_class: str | None = None,
        reconciliation_reason: str | None = None,
    ) -> None:
        """Append a bounded, sanitized publication state transition event."""
        metadata = _sanitize_transition_metadata(response_metadata)
        transitioned_at = self._clock()
        self._table.put_item(
            Item=_without_none(
                {
                    "pk": f"ATTEMPT#{attempt_id}",
                    "sk": f"TRANSITION#{ordinal:06d}",
                    "record_type": "publication_transition",
                    "attempt_id": attempt_id,
                    "ordinal": ordinal,
                    "prior_state": prior_state,
                    "resulting_state": resulting_state,
                    "actor": actor[:128],
                    "transitioned_at": timestamp(transitioned_at),
                    "expires_at": _operational_expiry(transitioned_at),
                    "error_class": error_class[:128] if error_class else None,
                    "response_metadata": metadata,
                    "reconciliation_reason": (
                        reconciliation_reason[:MAX_FAILURE_SUMMARY_LENGTH]
                        if reconciliation_reason
                        else None
                    ),
                }
            ),
            ConditionExpression=Attr("sk").not_exists(),
        )

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
    ) -> PublicationReservation | None:
        """Atomically reserve a current revision, or return ``None`` when it is protected.

        Only an expired reservation that never started its Telegram request is reclaimable.
        In particular, an expired `send_started` lease remains visible for ambiguity recovery.
        """
        if operation is PublicationOperation.EDIT and not target_message_ref:
            raise ValueError("edit reservations require a target_message_ref")
        if operation is PublicationOperation.CREATE and target_message_ref is not None:
            raise ValueError("create reservations cannot have a target_message_ref")
        now = self._clock()
        lease_expires_at = now + timedelta(seconds=PUBLICATION_LEASE_SECONDS)
        reservation = PublicationReservation(
            attempt_id=str(uuid4()),
            run_id=run_id,
            office_id=office_id,
            source_story_id=source_story_id,
            revision_hash=revision_hash,
            operation=operation,
            reservation_owner=reservation_owner,
            lease_expires_at=lease_expires_at,
            target_message_ref=target_message_ref,
        )
        now_text = timestamp(now)
        story_key = {"pk": _story_pk(office_id, source_story_id), "sk": "CURRENT"}
        try:
            self._transact_write(
                [
                    {
                        "Update": {
                            "Key": story_key,
                            "UpdateExpression": _reservation_current_update(target_message_ref),
                            "ExpressionAttributeValues": _without_none(
                                {
                                    ":attempt_id": reservation.attempt_id,
                                    ":run_id": run_id,
                                    ":owner": reservation_owner,
                                    ":lease": timestamp(lease_expires_at),
                                    ":reserved": AttemptState.RESERVED,
                                    ":operation": operation,
                                    ":revision": revision_hash,
                                    ":ordinal": 1,
                                    ":target_message_ref": target_message_ref,
                                    ":now": now_text,
                                }
                            ),
                            "ConditionExpression": (
                                "current_revision_hash = :revision AND "
                                "(attribute_not_exists(active_attempt_id) OR "
                                "(publication_reservation_state = :reserved AND "
                                "reservation_lease_expires_at <= :now)) AND "
                                "(attribute_not_exists(applied_revision_hash) OR "
                                "applied_revision_hash <> :revision)"
                            ),
                        }
                    },
                    {
                        "Put": {
                            "Item": self._attempt_item(reservation, now),
                            "ConditionExpression": "attribute_not_exists(sk)",
                        }
                    },
                    {
                        "Put": {
                            "Item": self._transition_item(
                                reservation,
                                ordinal=1,
                                prior_state=None,
                                resulting_state=AttemptState.RESERVED,
                                actor=reservation_owner,
                                transitioned_at=now,
                            ),
                            "ConditionExpression": "attribute_not_exists(sk)",
                        }
                    },
                ]
            )
        except Exception as error:
            if _is_conditional_failure(error):
                return None
            raise
        return reservation

    def start_publication_send(self, reservation: PublicationReservation) -> bool:
        """Atomically enter ``send_started`` before the one permitted Telegram call."""
        return self._transition_reservation(reservation, AttemptState.SEND_STARTED)

    def transition_publication(
        self,
        reservation: PublicationReservation,
        resulting_state: AttemptState,
        *,
        actor: str | None = None,
        message_ref: str | None = None,
        response_metadata: Mapping[str, object] | None = None,
        error_class: str | None = None,
        reconciliation_reason: str | None = None,
    ) -> bool:
        """Append one legal state transition and update current publication facts.

        ``published`` and ``confirmed_received`` require the resulting Telegram message
        reference.  Failed edits deliberately leave an existing message reference intact.
        """
        if resulting_state in {AttemptState.PUBLISHED, AttemptState.CONFIRMED_RECEIVED}:
            if reservation.operation is PublicationOperation.EDIT:
                message_ref = message_ref or reservation.target_message_ref
            elif reservation.target_message_ref is not None:
                raise ValueError("create reservations cannot have a target_message_ref")
            if not message_ref:
                raise ValueError("successful publication requires a message_ref")
        return self._transition_reservation(
            reservation,
            resulting_state,
            actor=actor or reservation.reservation_owner,
            message_ref=message_ref,
            response_metadata=response_metadata,
            error_class=error_class,
            reconciliation_reason=reconciliation_reason,
        )

    def reconcile_ambiguous_attempt(
        self,
        attempt_id: str,
        resulting_state: AttemptState,
        *,
        actor: str,
        reason: str,
        message_ref: str | None = None,
    ) -> bool:
        """Conditionally reconcile one ambiguous attempt with an operator audit record.

        Repeating a completed reconciliation is safe: no additional transition is
        written and ``False`` is returned. Only ``ambiguous`` attempts are eligible.
        """
        if resulting_state not in {
            AttemptState.CONFIRMED_RECEIVED,
            AttemptState.CONFIRMED_NOT_RECEIVED,
        }:
            raise ValueError("reconciliation requires a confirmation state")
        if not actor.strip():
            raise ValueError("reconciliation requires an operator identity")
        if not reason.strip():
            raise ValueError("reconciliation requires a reason")
        if resulting_state is AttemptState.CONFIRMED_NOT_RECEIVED and message_ref is not None:
            raise ValueError("confirmed_not_received cannot have a message_ref")

        attempt = self._table.get_item(
            Key={"pk": f"ATTEMPT#{attempt_id}", "sk": "RECORD"}, ConsistentRead=True
        ).get("Item")
        if not isinstance(attempt, Mapping):
            return False
        latest_state = self._latest_attempt_state(attempt_id)
        if latest_state is not AttemptState.AMBIGUOUS:
            return False
        try:
            reservation = PublicationReservation(
                attempt_id=attempt_id,
                run_id=str(attempt["run_id"]),
                office_id=str(attempt["office_id"]),
                source_story_id=str(attempt["source_story_id"]),
                revision_hash=str(attempt["revision_hash"]),
                operation=PublicationOperation(str(attempt["operation"])),
                reservation_owner=str(attempt["reservation_owner"]),
                lease_expires_at=datetime.fromisoformat(
                    str(attempt["lease_expires_at"]).replace("Z", "+00:00")
                ),
                target_message_ref=(
                    str(attempt["target_message_ref"])
                    if attempt.get("target_message_ref") is not None
                    else None
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("publication attempt record is invalid") from error
        if resulting_state is AttemptState.CONFIRMED_RECEIVED:
            message_ref = message_ref or reservation.target_message_ref
            if not message_ref:
                raise ValueError("confirmed_received requires a message_ref")
        return self._transition_reservation(
            reservation,
            resulting_state,
            actor=actor,
            message_ref=message_ref,
            reconciliation_reason=reason,
        )

    def _transition_reservation(
        self,
        reservation: PublicationReservation,
        resulting_state: AttemptState,
        *,
        actor: str | None = None,
        message_ref: str | None = None,
        response_metadata: Mapping[str, object] | None = None,
        error_class: str | None = None,
        reconciliation_reason: str | None = None,
    ) -> bool:
        prior_state, ordinal = _prior_state_and_ordinal(resulting_state)
        if prior_state is AttemptState.RESERVED:
            condition = (
                "active_attempt_id = :attempt_id AND reservation_owner = :owner AND "
                "reservation_revision_hash = :revision AND publication_reservation_state = :prior "
                "AND reservation_lease_expires_at > :now"
            )
        else:
            condition = (
                "active_attempt_id = :attempt_id AND reservation_owner = :owner AND "
                "reservation_revision_hash = :revision AND publication_reservation_state = :prior"
            )
        now = self._clock()
        current_update, values = _current_transition_update(
            resulting_state, reservation, message_ref
        )
        values.update(
            {
                ":attempt_id": reservation.attempt_id,
                ":owner": reservation.reservation_owner,
                ":revision": reservation.revision_hash,
                ":prior": prior_state,
                ":now": timestamp(now),
                ":state": resulting_state,
                ":ordinal": ordinal,
            }
        )
        try:
            self._transact_write(
                [
                    {
                        "Update": {
                            "Key": {
                                "pk": _story_pk(reservation.office_id, reservation.source_story_id),
                                "sk": "CURRENT",
                            },
                            "UpdateExpression": current_update,
                            "ExpressionAttributeValues": values,
                            "ConditionExpression": condition,
                        }
                    },
                    {
                        "Put": {
                            "Item": self._transition_item(
                                reservation,
                                ordinal=ordinal,
                                prior_state=prior_state,
                                resulting_state=resulting_state,
                                actor=actor or reservation.reservation_owner,
                                transitioned_at=now,
                                response_metadata=response_metadata,
                                error_class=error_class,
                                reconciliation_reason=reconciliation_reason,
                                completed_at=now
                                if resulting_state is not AttemptState.SEND_STARTED
                                else None,
                            ),
                            "ConditionExpression": "attribute_not_exists(sk)",
                        }
                    },
                ]
            )
        except Exception as error:
            if _is_conditional_failure(error):
                return False
            raise
        return True

    def _attempt_item(
        self, reservation: PublicationReservation, created_at: datetime
    ) -> dict[str, object]:
        return _without_none(
            {
                "pk": f"ATTEMPT#{reservation.attempt_id}",
                "sk": "RECORD",
                "record_type": "publication_attempt",
                "attempt_id": reservation.attempt_id,
                "run_id": reservation.run_id,
                "office_id": reservation.office_id,
                "source_story_id": reservation.source_story_id,
                "revision_hash": reservation.revision_hash,
                "operation": reservation.operation,
                "reservation_owner": reservation.reservation_owner,
                "lease_expires_at": timestamp(reservation.lease_expires_at),
                "target_message_ref": reservation.target_message_ref,
                "created_at": timestamp(created_at),
                "expires_at": _operational_expiry(created_at),
            }
        )

    def _transition_item(
        self,
        reservation: PublicationReservation,
        *,
        ordinal: int,
        prior_state: AttemptState | None,
        resulting_state: AttemptState,
        actor: str,
        transitioned_at: datetime,
        response_metadata: Mapping[str, object] | None = None,
        error_class: str | None = None,
        reconciliation_reason: str | None = None,
        completed_at: datetime | None = None,
    ) -> dict[str, object]:
        return _without_none(
            {
                "pk": f"ATTEMPT#{reservation.attempt_id}",
                "sk": f"TRANSITION#{ordinal:06d}",
                "record_type": "publication_transition",
                "attempt_id": reservation.attempt_id,
                "ordinal": ordinal,
                "prior_state": prior_state,
                "resulting_state": resulting_state,
                "actor": actor[:128],
                "transitioned_at": timestamp(transitioned_at),
                "completed_at": timestamp(completed_at) if completed_at else None,
                "lease_expires_at": timestamp(reservation.lease_expires_at),
                "expires_at": _operational_expiry(transitioned_at),
                "error_class": error_class[:128] if error_class else None,
                "response_metadata": _sanitize_transition_metadata(response_metadata),
                "reconciliation_reason": (
                    reconciliation_reason[:MAX_FAILURE_SUMMARY_LENGTH]
                    if reconciliation_reason
                    else None
                ),
            }
        )

    def _latest_attempt_state(self, attempt_id: str) -> AttemptState | None:
        """Return the latest append-only transition state for one bounded attempt history."""
        response = self._table.query(
            KeyConditionExpression=Key("pk").eq(f"ATTEMPT#{attempt_id}")
            & Key("sk").begins_with("TRANSITION#"),
            ScanIndexForward=False,
            Limit=1,
            ConsistentRead=True,
        )
        items = response.get("Items", [])
        if not isinstance(items, list) or not items:
            return None
        state = items[0].get("resulting_state") if isinstance(items[0], Mapping) else None
        try:
            return AttemptState(str(state))
        except ValueError:
            return None

    def _transact_write(self, items: list[dict[str, object]]) -> None:
        """Execute a transaction with either a test adapter or a boto3 table resource."""
        transact = getattr(self._table, "transact_write_items", None)
        if callable(transact):
            transact(TransactItems=items)
            return
        client = self._table.meta.client  # type: ignore[attr-defined]
        serializer = __import__(
            "boto3.dynamodb.types", fromlist=["TypeSerializer"]
        ).TypeSerializer()
        serialized: list[dict[str, object]] = []
        for item in items:
            operation, payload = next(iter(item.items()))
            payload = dict(cast(Mapping[str, object], payload))
            if "Key" in payload:
                payload["Key"] = {
                    key: serializer.serialize(value)
                    for key, value in cast(Mapping[str, object], payload["Key"]).items()
                }
            if "Item" in payload:
                payload["Item"] = {
                    key: serializer.serialize(value)
                    for key, value in cast(Mapping[str, object], payload["Item"]).items()
                }
            if "ExpressionAttributeValues" in payload:
                payload["ExpressionAttributeValues"] = {
                    key: serializer.serialize(value)
                    for key, value in cast(
                        Mapping[str, object], payload["ExpressionAttributeValues"]
                    ).items()
                }
            payload["TableName"] = self._table.name  # type: ignore[attr-defined]
            serialized.append({operation: payload})
        client.transact_write_items(TransactItems=serialized)


def _story_pk(office_id: str, source_story_id: str) -> str:
    return f"STORY#{office_id}#{source_story_id}"


def _operational_expiry(recorded_at: datetime) -> int:
    """Return the DynamoDB TTL timestamp for one operational record."""
    return int((recorded_at + timedelta(days=OPERATIONAL_RECORD_TTL_DAYS)).timestamp())


def _is_operationally_expired(item: Mapping[str, object], now: datetime) -> bool:
    """Respect the TTL boundary before DynamoDB asynchronously removes a record."""
    expires_at = _epoch_seconds(item.get("expires_at"))
    return expires_at is not None and expires_at <= int(now.timestamp())


def _epoch_seconds(value: object) -> int | None:
    """Normalize DynamoDB's integral numeric TTL representation without accepting fractions."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        return int(value)
    return None


def _without_none(item: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in item.items() if value is not None}


def _is_conditional_failure(error: Exception) -> bool:
    error_name = error.__class__.__name__
    if error_name == "ConditionalCheckFailedException":
        return True
    if error_name != "TransactionCanceledException":
        return False

    response = getattr(error, "response", None)
    if not isinstance(response, Mapping):
        return False
    reasons = response.get("CancellationReasons")
    if not isinstance(reasons, list):
        return False
    codes = [reason.get("Code") for reason in reasons if isinstance(reason, Mapping)]
    return (
        bool(codes)
        and "ConditionalCheckFailed" in codes
        and all(code in {"None", "ConditionalCheckFailed"} for code in codes)
    )


def _sanitize_transition_metadata(metadata: Mapping[str, object] | None) -> dict[str, str]:
    """Keep only bounded, response-level fields that are safe in durable audit data."""
    permitted = {
        "http_status",
        "telegram_error_code",
        "telegram_error_description",
        "request_id",
        "correlation_id",
        "latency_ms",
        "retry_after_seconds",
        "retry_ordinal",
        "retry_decision",
    }
    return {
        key: str(value)[:MAX_FAILURE_SUMMARY_LENGTH]
        for key, value in (metadata or {}).items()
        if key in permitted
    }


def _reservation_current_update(target_message_ref: str | None) -> str:
    update = (
        "SET active_attempt_id = :attempt_id, active_run_id = :run_id, "
        "reservation_owner = :owner, reservation_lease_expires_at = :lease, "
        "publication_reservation_state = :reserved, publication_operation = :operation, "
        "reservation_revision_hash = :revision, transition_ordinal = :ordinal"
    )
    return (
        f"{update}, target_message_ref = :target_message_ref"
        if target_message_ref
        else f"{update} REMOVE target_message_ref"
    )


def _prior_state_and_ordinal(resulting_state: AttemptState) -> tuple[AttemptState, int]:
    legal_transitions = {
        AttemptState.SEND_STARTED: (AttemptState.RESERVED, 2),
        AttemptState.PUBLISHED: (AttemptState.SEND_STARTED, 3),
        AttemptState.REJECTED: (AttemptState.SEND_STARTED, 3),
        AttemptState.AMBIGUOUS: (AttemptState.SEND_STARTED, 3),
        AttemptState.CONFIRMED_RECEIVED: (AttemptState.AMBIGUOUS, 4),
        AttemptState.CONFIRMED_NOT_RECEIVED: (AttemptState.AMBIGUOUS, 4),
    }
    try:
        return legal_transitions[resulting_state]
    except KeyError as error:
        raise ValueError(f"invalid publication transition to {resulting_state}") from error


def _current_transition_update(
    resulting_state: AttemptState,
    reservation: PublicationReservation,
    message_ref: str | None,
) -> tuple[str, dict[str, object]]:
    if resulting_state is AttemptState.SEND_STARTED:
        return "SET publication_reservation_state = :state, transition_ordinal = :ordinal", {}
    if resulting_state is AttemptState.AMBIGUOUS:
        return (
            "SET publication_reservation_state = :state, transition_ordinal = :ordinal, "
            "latest_publication_status = :state"
        ), {}
    if resulting_state in {AttemptState.PUBLISHED, AttemptState.CONFIRMED_RECEIVED}:
        return (
            "SET latest_publication_status = :state, applied_revision_hash = :revision, "
            "telegram_message_ref = :message_ref, transition_ordinal = :ordinal "
            "REMOVE active_attempt_id, active_run_id, reservation_owner, "
            "reservation_lease_expires_at, publication_reservation_state, publication_operation, "
            "reservation_revision_hash, target_message_ref"
        ), {":message_ref": message_ref}
    # A definitive rejection and confirmed-not-received result leave any prior Telegram
    # message reference untouched, while releasing the story for a later reservation.
    return (
        "SET latest_publication_status = :state, transition_ordinal = :ordinal "
        "REMOVE active_attempt_id, active_run_id, reservation_owner, reservation_lease_expires_at, "
        "publication_reservation_state, publication_operation, reservation_revision_hash, "
        "target_message_ref"
    ), {}
