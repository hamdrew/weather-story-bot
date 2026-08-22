from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

import pytest

from weather_story_bot.history import (
    CURRENT_INDEX_NAME,
    AttemptState,
    HistoryStore,
    ImageMetadata,
    OutcomeCounts,
    PublicationOperation,
    RunStatus,
    revision_hash,
)
from weather_story_bot.ingestion import QuarantinedStoryItem, WeatherStory


class ConditionalCheckFailedException(Exception):
    pass


class TransactionCanceledException(Exception):
    def __init__(self, reasons: list[dict[str, str]]) -> None:
        super().__init__()
        self.response = {"CancellationReasons": reasons}


class Table:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []
        self.updates: list[dict[str, object]] = []
        self.fail_next_conditional = False
        self.fail_update_numbers: set[int] = set()
        self.next_update_response: dict[str, object] = {}

    def put_item(self, **kwargs: object) -> dict[str, object]:
        if self.fail_next_conditional:
            self.fail_next_conditional = False
            raise ConditionalCheckFailedException()
        self.items.append(kwargs["Item"])  # type: ignore[arg-type]
        return {}

    def update_item(self, **kwargs: object) -> dict[str, object]:
        if len(self.updates) + 1 in self.fail_update_numbers:
            self.fail_update_numbers.remove(len(self.updates) + 1)
            raise ConditionalCheckFailedException()
        if self.fail_next_conditional:
            self.fail_next_conditional = False
            raise ConditionalCheckFailedException()
        self.updates.append(kwargs)
        response = self.next_update_response
        self.next_update_response = {}
        return response

    def get_item(self, **kwargs: object) -> dict[str, object]:
        return {}

    def query(self, **kwargs: object) -> dict[str, object]:
        self.query_kwargs = kwargs
        return {"Items": [{"pk": "STORY#MKX#source", "sk": "CURRENT"}]}


class TransactionTable(Table):
    def __init__(self) -> None:
        super().__init__()
        self.transactions: list[list[dict[str, object]]] = []
        self.fail_transaction = False
        self.transaction_error: Exception | None = None

    def transact_write_items(self, **kwargs: object) -> dict[str, object]:
        if self.transaction_error is not None:
            error = self.transaction_error
            self.transaction_error = None
            raise error
        if self.fail_transaction:
            self.fail_transaction = False
            raise ConditionalCheckFailedException()
        self.transactions.append(cast(list[dict[str, object]], kwargs["TransactItems"]))
        return {}


def now() -> datetime:
    return datetime(2026, 8, 16, 12, tzinfo=UTC)


def story(**overrides: object) -> WeatherStory:
    return WeatherStory.model_validate(
        {
            "officeId": "MKX",
            "startTime": "2026-08-16T10:00:00Z",
            "endTime": "2026-08-16T18:00:00Z",
            "updateTime": "2026-08-16T11:00:00Z",
            "title": "Heat advisory",
            "description": "Dangerous heat.",
            "altText": "Heat map",
            "priority": True,
            "order": 1,
            "download": "https://www.weather.gov/images/mkx/123e4567-e89b-12d3-a456-426614174000",
        }
        | overrides
    )


def test_observe_story_creates_one_mutable_current_record() -> None:
    table = Table()
    store = HistoryStore(table, clock=now)

    digest, created = store.observe_story(story())

    assert created is True
    assert len(digest) == 64
    assert table.items[0]["pk"] == "STORY#MKX#123e4567-e89b-12d3-a456-426614174000"
    assert table.items[0]["sk"] == "CURRENT"
    assert table.items[0]["record_type"] == "story_current"
    assert table.items[0]["current_revision_hash"] == digest
    assert table.items[0]["first_seen_at"] == "2026-08-16T12:00:00Z"
    assert table.items[0]["image_status"] == "image_pending"
    assert table.updates == []


def test_unchanged_story_only_updates_last_seen() -> None:
    table = Table()
    table.fail_next_conditional = True
    table.fail_update_numbers.add(1)

    digest, created = HistoryStore(table, clock=now).observe_story(story())

    assert created is False
    assert table.items == []
    assert len(table.updates) == 1
    assert table.updates[0]["UpdateExpression"] == "SET last_seen_at = :last_seen_at"
    assert digest == revision_hash(story())


def test_changed_story_replaces_current_source_state_without_delivery_state() -> None:
    table = Table()
    store = HistoryStore(table, clock=now)
    first_digest, _ = store.observe_story(story())
    table.fail_next_conditional = True

    revised_digest, revised = store.observe_story(
        story(title="Updated advisory", updateTime="2026-08-16T12:00:00Z")
    )

    assert revised is True
    assert revised_digest != first_digest
    revision_update = table.updates[0]
    assert revision_update["Key"] == {
        "pk": "STORY#MKX#123e4567-e89b-12d3-a456-426614174000",
        "sk": "CURRENT",
    }
    assert "telegram" not in str(revision_update)
    assert "first_seen_at" not in str(revision_update)
    assert "REMOVE image_failure" in str(revision_update["UpdateExpression"])
    assert "REMOVE image," not in str(revision_update["UpdateExpression"])


def test_revision_hash_changes_for_source_or_image_changes() -> None:
    assert revision_hash(story()) != revision_hash(story(title="Updated"))
    assert revision_hash(story(), "a") != revision_hash(story(), "b")


def test_history_persists_bounded_quarantine_run_attempt_and_transition_data() -> None:
    table = Table()
    store = HistoryStore(table, clock=now)
    store.put_quarantine("run-1", QuarantinedStoryItem(2, "bad", "title", "x" * 300))
    store.put_run(
        "run-1",
        "MKX",
        collection_outcome="success",
        status=RunStatus.SUCCESS_WITH_QUARANTINED_ITEMS,
        started_at=now(),
        completed_at=now() + timedelta(seconds=2),
        required_work_completed=True,
        counts=OutcomeCounts(discovered=1, quarantined=1),
    )
    store.put_attempt(
        "attempt-1",
        run_id="run-1",
        office_id="MKX",
        source_story_id="source",
        revision_hash="hash",
        operation="create",
        reservation_owner="worker",
        lease_expires_at=now() + timedelta(minutes=1),
    )
    store.append_transition(
        "attempt-1",
        1,
        prior_state=None,
        resulting_state=AttemptState.RESERVED,
        actor="worker",
        response_metadata={"http_status": 200, "token": "not-retained"},
    )

    quarantine, run, attempt, transition = table.items
    assert len(cast(str, quarantine["error_summary"])) == 256
    assert run["aggregate_counts"] == run["counts"]
    assert run["elapsed_ms"] == 2000
    assert attempt["operation"] == "create"
    assert transition["response_metadata"] == {"http_status": "200"}
    expiry = int((now() + timedelta(days=30)).timestamp())
    assert [record["expires_at"] for record in (quarantine, run, attempt, transition)] == [
        expiry,
        expiry + 2,
        expiry,
        expiry,
    ]


def test_history_rejects_invalid_bounded_data_and_marks_images() -> None:
    table = Table()
    store = HistoryStore(table, clock=now)
    with pytest.raises(ValueError, match="bounded"):
        store.put_run(
            "run",
            "MKX",
            collection_outcome="success",
            status=RunStatus.SUCCESS,
            started_at=now(),
            completed_at=now(),
            required_work_completed=True,
            counts=OutcomeCounts(),
            failure_reasons=("x",) * 9,
        )
    with pytest.raises(ValueError, match="staging"):
        ImageMetadata("staging/a", "image/png", 1, "a", 1, 1)

    store.commit_image(
        "MKX", "source", "hash", ImageMetadata("current/a", "image/png", 1, "a", 1, 1)
    )
    store.mark_image_invalid("MKX", "source", "hash", "x" * 300)
    assert len(table.updates) == 2
    assert table.updates[-1]["ExpressionAttributeValues"][":reason"] == "x" * 256  # type: ignore[index]


def test_image_commit_targets_only_current_matching_revision() -> None:
    table = Table()
    store = HistoryStore(table, clock=now)

    store.commit_image(
        "MKX", "source", "old-hash", ImageMetadata("current/a", "image/png", 1, "a", 1, 1)
    )

    assert len(table.updates) == 1
    assert cast(dict[str, str], table.updates[0]["Key"])["sk"] == "CURRENT"
    assert table.updates[0]["ReturnValues"] == "ALL_OLD"


def test_image_commit_returns_the_previous_image_metadata() -> None:
    table = Table()
    table.next_update_response = {
        "Attributes": {
            "image": {
                "key": "current/MKX/source/old",
                "content_type": "image/png",
                "byte_size": 42,
                "sha256_hex": "old-digest",
                "width": 10,
                "height": 20,
            }
        }
    }

    previous = HistoryStore(table, clock=now).commit_image(
        "MKX",
        "source",
        "hash",
        ImageMetadata("current/MKX/source/new", "image/png", 43, "new", 11, 21),
    )

    assert previous == ImageMetadata(
        "current/MKX/source/old", "image/png", 42, "old-digest", 10, 20
    )


def test_expiration_and_alert_cooldown_have_conditional_behavior() -> None:
    table = Table()
    store = HistoryStore(table, clock=now)
    assert store.expire_due_stories("MKX") == 1
    assert table.query_kwargs["IndexName"] == CURRENT_INDEX_NAME
    key_expression = cast(Any, table.query_kwargs["KeyConditionExpression"]).get_expression()
    assert key_expression["values"][0].get_expression()["values"][0].name == "office_current_pk"
    assert cast(dict[str, str], table.updates[0]["Key"])["sk"] == "CURRENT"
    assert table.updates[0]["UpdateExpression"] == "SET lifecycle_status = :expired"
    table.fail_next_conditional = True

    immediate = store.update_alert_fingerprint(
        "fingerprint",
        severity="error",
        run_id="run",
        cooldown_until=now() + timedelta(hours=4),
        dispatch_outcome="sent",
    )

    assert immediate is False
    assert len(table.updates) == 2
    alert_values = cast(dict[str, object], table.updates[-1]["ExpressionAttributeValues"])
    assert alert_values[":expires_at"] == int((now() + timedelta(days=30)).timestamp())


def test_expiration_race_does_not_count_story_as_expired() -> None:
    table = Table()
    table.fail_next_conditional = True

    expired = HistoryStore(table, clock=now).expire_due_stories("MKX")

    assert expired == 0
    assert table.updates == []


def test_create_and_edit_reservations_are_atomic_and_expire_in_sixty_seconds() -> None:
    table = TransactionTable()
    store = HistoryStore(table, clock=now)

    create = store.reserve_publication(
        run_id="run-1",
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision-1",
        operation=PublicationOperation.CREATE,
        reservation_owner="worker-1",
    )
    edit = store.reserve_publication(
        run_id="run-2",
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision-2",
        operation=PublicationOperation.EDIT,
        reservation_owner="worker-2",
        target_message_ref="message-7",
    )

    assert create is not None
    UUID(create.attempt_id)
    assert create.run_id == "run-1"
    assert create.lease_expires_at == now() + timedelta(seconds=60)
    assert edit is not None
    assert edit.target_message_ref == "message-7"
    first = table.transactions[0]
    assert len(first) == 3
    current_update = cast(dict[str, object], first[0]["Update"])
    assert current_update["Key"] == {"pk": "STORY#MKX#source", "sk": "CURRENT"}
    assert "current_revision_hash = :revision" in cast(str, current_update["ConditionExpression"])
    attempt = cast(dict[str, object], first[1]["Put"])["Item"]
    transition = cast(dict[str, object], first[2]["Put"])["Item"]
    assert cast(dict[str, object], attempt)["run_id"] == "run-1"
    assert cast(dict[str, object], transition)["resulting_state"] is AttemptState.RESERVED


def test_create_reservations_reject_target_message_references() -> None:
    with pytest.raises(ValueError, match="create reservations cannot have a target_message_ref"):
        HistoryStore(TransactionTable(), clock=now).reserve_publication(
            run_id="run",
            office_id="MKX",
            source_story_id="source",
            revision_hash="revision",
            operation=PublicationOperation.CREATE,
            reservation_owner="worker",
            target_message_ref="message-7",
        )


def test_create_success_requires_the_telegram_acknowledgement_reference() -> None:
    table = TransactionTable()
    store = HistoryStore(table, clock=now)
    reservation = store.reserve_publication(
        run_id="run",
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision",
        operation=PublicationOperation.CREATE,
        reservation_owner="worker",
    )
    assert reservation is not None
    assert store.start_publication_send(reservation)

    with pytest.raises(ValueError, match="successful publication requires a message_ref"):
        store.transition_publication(reservation, AttemptState.PUBLISHED)


def test_nonconditional_transaction_cancellation_is_not_treated_as_a_race() -> None:
    table = TransactionTable()
    error = TransactionCanceledException([{"Code": "ProvisionedThroughputExceeded"}])
    table.transaction_error = error

    with pytest.raises(TransactionCanceledException):
        HistoryStore(table, clock=now).reserve_publication(
            run_id="run",
            office_id="MKX",
            source_story_id="source",
            revision_hash="revision",
            operation=PublicationOperation.CREATE,
            reservation_owner="worker",
        )

    reservation = HistoryStore(table, clock=now).reserve_publication(
        run_id="run",
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision",
        operation=PublicationOperation.CREATE,
        reservation_owner="worker",
    )
    assert reservation is not None
    table.transaction_error = error
    with pytest.raises(TransactionCanceledException):
        HistoryStore(table, clock=now).start_publication_send(reservation)


def test_transaction_cancellation_with_only_conditional_failures_is_a_race() -> None:
    table = TransactionTable()
    table.transaction_error = TransactionCanceledException(
        [{"Code": "None"}, {"Code": "ConditionalCheckFailed"}]
    )

    assert (
        HistoryStore(table, clock=now).reserve_publication(
            run_id="run",
            office_id="MKX",
            source_story_id="source",
            revision_hash="revision",
            operation=PublicationOperation.CREATE,
            reservation_owner="worker",
        )
        is None
    )


def test_reservation_races_and_only_expired_unstarted_leases_can_be_reclaimed() -> None:
    table = TransactionTable()
    store = HistoryStore(table, clock=now)
    reserved = store.reserve_publication(
        run_id="run-1",
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision",
        operation=PublicationOperation.CREATE,
        reservation_owner="worker-1",
    )
    assert reserved is not None
    table.fail_transaction = True
    assert (
        store.reserve_publication(
            run_id="run-2",
            office_id="MKX",
            source_story_id="source",
            revision_hash="revision",
            operation=PublicationOperation.CREATE,
            reservation_owner="worker-2",
        )
        is None
    )
    # The DynamoDB condition is deliberately narrow: only a reserved, expired lease can win.
    condition = cast(dict[str, object], table.transactions[0][0]["Update"])["ConditionExpression"]
    assert "publication_reservation_state = :reserved" in cast(str, condition)
    assert "reservation_lease_expires_at <= :now" in cast(str, condition)
    assert store.start_publication_send(reserved) is True
    transition_condition = cast(dict[str, object], table.transactions[-1][0]["Update"])[
        "ConditionExpression"
    ]
    for required in (
        "active_attempt_id = :attempt_id",
        "reservation_owner = :owner",
        "reservation_revision_hash = :revision",
        "publication_reservation_state = :prior",
        "reservation_lease_expires_at > :now",
    ):
        assert required in cast(str, transition_condition)


def test_transitions_enforce_ownership_legal_order_and_preserve_failed_edit_reference() -> None:
    table = TransactionTable()
    store = HistoryStore(table, clock=now)
    reservation = store.reserve_publication(
        run_id="run",
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision",
        operation=PublicationOperation.EDIT,
        reservation_owner="worker",
        target_message_ref="old-message",
    )
    assert reservation is not None
    assert store.start_publication_send(reservation) is True
    assert (
        store.transition_publication(
            reservation,
            AttemptState.REJECTED,
            response_metadata={"http_status": 400, "token": "forbidden", "body": "forbidden"},
            error_class="telegram_rejected",
        )
        is True
    )
    terminal_update = cast(dict[str, object], table.transactions[-1][0]["Update"])
    assert "telegram_message_ref" not in cast(str, terminal_update["UpdateExpression"])
    transition = cast(dict[str, object], table.transactions[-1][1]["Put"])["Item"]
    assert cast(dict[str, object], transition)["response_metadata"] == {"http_status": "400"}
    with pytest.raises(ValueError, match="invalid publication transition"):
        store.transition_publication(reservation, AttemptState.RESERVED)


def test_success_and_ambiguity_transitions_update_current_story_facts() -> None:
    table = TransactionTable()
    store = HistoryStore(table, clock=now)
    reservation = store.reserve_publication(
        run_id="run",
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision",
        operation=PublicationOperation.CREATE,
        reservation_owner="worker",
    )
    assert reservation is not None
    assert store.start_publication_send(reservation)
    assert store.transition_publication(reservation, AttemptState.AMBIGUOUS)
    assert store.transition_publication(
        reservation, AttemptState.CONFIRMED_RECEIVED, actor="operator", message_ref="message-9"
    )
    success_update = cast(dict[str, object], table.transactions[-1][0]["Update"])
    assert "applied_revision_hash = :revision" in cast(str, success_update["UpdateExpression"])
    assert (
        cast(dict[str, object], success_update["ExpressionAttributeValues"])[":message_ref"]
        == "message-9"
    )
    assert "REMOVE active_attempt_id" in cast(str, success_update["UpdateExpression"])


def test_direct_publication_and_confirmed_not_received_follow_the_remaining_legal_paths() -> None:
    table = TransactionTable()
    store = HistoryStore(table, clock=now)
    published = store.reserve_publication(
        run_id="run-1",
        office_id="MKX",
        source_story_id="source-1",
        revision_hash="revision-1",
        operation=PublicationOperation.CREATE,
        reservation_owner="worker",
    )
    assert published is not None
    assert store.start_publication_send(published)
    assert store.transition_publication(published, AttemptState.PUBLISHED, message_ref="message-1")
    retryable = store.reserve_publication(
        run_id="run-2",
        office_id="MKX",
        source_story_id="source-2",
        revision_hash="revision-2",
        operation=PublicationOperation.CREATE,
        reservation_owner="worker",
    )
    assert retryable is not None
    assert store.start_publication_send(retryable)
    assert store.transition_publication(retryable, AttemptState.AMBIGUOUS)
    assert store.transition_publication(
        retryable, AttemptState.CONFIRMED_NOT_RECEIVED, actor="operator"
    )
    final_update = cast(dict[str, object], table.transactions[-1][0]["Update"])
    assert "latest_publication_status = :state" in cast(str, final_update["UpdateExpression"])
    assert "telegram_message_ref" not in cast(str, final_update["UpdateExpression"])


def test_stale_or_non_owner_workers_cannot_start_or_complete_a_reservation() -> None:
    table = TransactionTable()
    store = HistoryStore(table, clock=now)
    reservation = store.reserve_publication(
        run_id="run",
        office_id="MKX",
        source_story_id="source",
        revision_hash="revision",
        operation=PublicationOperation.CREATE,
        reservation_owner="worker",
    )
    assert reservation is not None
    table.fail_transaction = True
    assert store.start_publication_send(reservation) is False
    with pytest.raises(ValueError, match="message_ref"):
        store.transition_publication(reservation, AttemptState.PUBLISHED)
