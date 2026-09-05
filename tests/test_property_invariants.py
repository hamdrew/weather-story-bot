"""Focused deterministic property tests for core offline invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import cast
from uuid import UUID

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from operation_fakes import Notifier, OfficePorts
from PIL import Image
from test_runtime import alarm_event, operations_config

from weather_story_bot.history import (
    MAX_FAILURE_SUMMARY_LENGTH,
    AttemptState,
    revision_hash,
    timestamp,
)
from weather_story_bot.history import _prior_state_and_ordinal as prior_state_and_ordinal
from weather_story_bot.history import _sanitize_transition_metadata as sanitize_transition_metadata
from weather_story_bot.image_retention import (
    MAX_REDIRECTS,
    ImageHistory,
    ImageRetainer,
    ImageRetentionError,
    S3Client,
)
from weather_story_bot.ingestion import WeatherStory, normalize_collection
from weather_story_bot.nws_client import (
    NWSCollectionClient,
    NWSCollectionRequestError,
    RetryDecision,
)
from weather_story_bot.operations import (
    AlertDeliveryOutcome,
    OfficeInformationCommand,
    OfficeInformationService,
    dispatch_alarm,
    render_office_information,
    render_private_alert,
    sanitize_observation,
)
from weather_story_bot.runtime import load_operations_config, parse_alarm_notification
from weather_story_bot.telegram import render_caption

PBT_SETTINGS = settings(derandomize=True, max_examples=50, database=None, deadline=None)
VALID_TRANSITIONS = {
    AttemptState.SEND_STARTED: (AttemptState.RESERVED, 2),
    AttemptState.PUBLISHED: (AttemptState.SEND_STARTED, 3),
    AttemptState.REJECTED: (AttemptState.SEND_STARTED, 3),
    AttemptState.AMBIGUOUS: (AttemptState.SEND_STARTED, 3),
    AttemptState.CONFIRMED_RECEIVED: (AttemptState.AMBIGUOUS, 4),
    AttemptState.CONFIRMED_NOT_RECEIVED: (AttemptState.AMBIGUOUS, 4),
}
PERMITTED_METADATA = {
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
SAFE_DATETIMES = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2030, 12, 31, 23, 59, 59),
    timezones=st.timezones(),
)

OPERATION_OUTCOMES = st.sampled_from(tuple(AlertDeliveryOutcome))
OFFICE_FAILURES = st.sampled_from(
    ("none", "load", "invite", "message", "pin", "unverified", "commit")
)


@PBT_SETTINGS
@given(office_id=st.from_regex(r"[A-Z]{3}", fullmatch=True), active=st.booleans())
def test_refresh_eligibility_depends_on_active_state_not_office_identity(
    office_id: str, active: bool
) -> None:
    from weather_story_bot.config import OfficeRegistryRecord, weather_stories_url
    from weather_story_bot.operations import OfficeInformationRefreshError

    ports = OfficePorts()
    ports.office = OfficeRegistryRecord.model_validate(
        ports.office.model_dump()
        | {
            "office_id": office_id,
            "weather_stories_url": weather_stories_url(office_id),
            "active": active,
        }
    )
    command = OfficeInformationCommand(
        environment="dev", office_id=office_id, operator_id="operator", correlation_id="corr"
    )
    service = OfficeInformationService(ports, ports, ports, environment="dev")
    if active:
        assert service.refresh(command).office_id == office_id
    else:
        with pytest.raises(OfficeInformationRefreshError):
            service.refresh(command)
        assert ports.calls == ["load"]


SAFE_UNICODE = st.text(alphabet=st.characters(exclude_categories=["Cs"]), max_size=1500)


@PBT_SETTINGS
@given(
    environment=st.sampled_from(("dev", "staging", "prod")),
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
)
def test_operations_configuration_round_trip_preserves_valid_scope(
    environment: str, suffix: str
) -> None:
    from weather_story_bot.config import OperationsConfig

    config = OperationsConfig.model_validate_json(
        operations_config().model_dump_json().replace("dev", environment)
    )
    config = OperationsConfig.model_validate(
        config.model_dump() | {"alarm_names": [f"weather-story-{environment}-{suffix}"]}
    )
    assert load_operations_config({"OPERATIONS_CONFIG": config.model_dump_json()}) == config


@PBT_SETTINGS
@given(title=st.text(alphabet="Office Milwaukee 天気 🌤️", min_size=1, max_size=256))
def test_office_rendering_is_bounded_and_independent_of_private_destination(title: str) -> None:
    office = OfficePorts().office
    from weather_story_bot.config import OfficeRegistryRecord

    original = OfficeRegistryRecord.model_validate(office.model_dump() | {"display_name": title})
    other = OfficeRegistryRecord.model_validate(
        original.model_dump() | {"telegram_channel_id": "mock:other"}
    )
    rendered = render_office_information(original)
    assert rendered == render_office_information(other)
    assert len(rendered.text.encode("utf-16-le")) // 2 <= 1024
    assert "mock:" not in rendered.text


@PBT_SETTINGS
@given(candidate=st.dictionaries(st.text(max_size=30), SAFE_UNICODE, max_size=10))
def test_observation_projection_is_allowlisted_and_idempotent(candidate: dict[str, str]) -> None:
    result = sanitize_observation(candidate)
    assert sanitize_observation(result.model_dump()) == result
    assert result.summary == "Protected operation outcome"
    assert result.correlation_id is None
    assert set(result.model_dump()) == {"event_type", "classification", "correlation_id", "summary"}


@PBT_SETTINGS
@given(failures=st.lists(OFFICE_FAILURES, max_size=20))
def test_office_refresh_sequences_match_one_current_record_model(failures: list[str]) -> None:
    ports = OfficePorts()
    service = OfficeInformationService(ports, ports, ports, environment="dev")
    command = OfficeInformationCommand(
        environment="dev", office_id="MKX", operator_id="operator", correlation_id="corr"
    )
    model_version: int | None = None
    expected_ref: tuple[str, str] | None = None
    for failure in failures:
        ports.failure = failure
        if failure == "none":
            service.refresh(command, expected_version=model_version)
            model_version = (model_version or 0) + 1
            expected_ref = ("mock:managed-reference", "mock:invite-reference")
        else:
            with pytest.raises(RuntimeError):
                service.refresh(command, expected_version=model_version)
        assert ports.version == model_version
        assert ports.current == expected_ref
        assert set(ports.calls) <= {"load", "invite", "message", "pin", "verify", "commit"}


@PBT_SETTINGS
@given(sequence=st.lists(st.tuples(OPERATION_OUTCOMES, st.booleans()), max_size=20))
def test_notification_sequences_are_terminal_and_match_fallback_model(
    sequence: list[tuple[AlertDeliveryOutcome, bool]],
) -> None:
    alarm = parse_alarm_notification(alarm_event(), operations_config())
    for outcome, failure in sequence:
        notifier = Notifier(outcome, fail_fallback=failure)
        result = dispatch_alarm(alarm, notifier)
        assert notifier.primary_calls == 1
        permitted = outcome is AlertDeliveryOutcome.DEFINITIVE_FAILURE
        assert notifier.fallback_calls == int(permitted)
        assert (
            result.fallback_outcome.value == ("failed" if failure else "delivered")
            if permitted
            else result.fallback_outcome.value == "not_attempted"
        )


@PBT_SETTINGS
@given(
    account=st.sampled_from(("123456789012", "000000000000")),
    state=st.sampled_from(("ALARM", "OK", "INSUFFICIENT_DATA")),
    reason=st.text(alphabet=st.characters(exclude_categories=["Cs"]), max_size=512),
)
def test_alarm_acceptance_and_rendering_ignore_untrusted_reason(
    account: str, state: str, reason: str
) -> None:
    event = alarm_event(AWSAccountId=account, NewStateValue=state, NewStateReason=reason)
    if account != "123456789012" or state != "ALARM":
        with pytest.raises(ValueError):
            parse_alarm_notification(event, operations_config())
    else:
        alarm = parse_alarm_notification(event, operations_config())
        alert = render_private_alert(alarm)
        assert alert.summary == (
            f"ERROR 2026-09-04 00:00:00Z Alarm {alarm.alarm_name} is ALARM: "
            "CloudWatch alarm entered ALARM"
        )
        assert len(alert.summary) <= 512


@PBT_SETTINGS
@given(title=SAFE_UNICODE, body=SAFE_UNICODE)
def test_explicit_telegram_entities_remain_in_utf16_bounds(title: str, body: str) -> None:
    caption = render_caption(title, body, "")
    units = len(caption.text.encode("utf-16-le")) // 2
    assert units <= 1024
    for entity in caption.entities:
        offset, length = entity["offset"], entity["length"]
        assert isinstance(offset, int) and isinstance(length, int)
        assert 0 <= offset <= offset + length <= units
        encoded = caption.text.encode("utf-16-le")
        assert encoded[offset * 2 : (offset + length) * 2].decode("utf-16-le")
        assert entity["type"] == "bold"


def _story_payload(
    timestamp_value: datetime, source_id: UUID, **overrides: object
) -> dict[str, object]:
    return {
        "officeId": "MKX",
        "startTime": timestamp_value.isoformat(),
        "endTime": timestamp_value.isoformat(),
        "updateTime": timestamp_value.isoformat(),
        "title": "Weather story",
        "description": "Conditions are changing.",
        "altText": "A weather map",
        "priority": True,
        "order": 1,
        "download": f"https://www.weather.gov/images/mkx/{source_id}",
    } | overrides


def _tiny_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1, 1), "blue").save(output, format="PNG")
    return output.getvalue()


@PBT_SETTINGS
@given(resulting_state=st.sampled_from(tuple(AttemptState)))
def test_publication_state_transitions_are_limited_to_the_defined_graph(
    resulting_state: AttemptState,
) -> None:
    if resulting_state is AttemptState.RESERVED:
        with pytest.raises(ValueError, match="invalid publication transition"):
            prior_state_and_ordinal(resulting_state)
    else:
        assert prior_state_and_ordinal(resulting_state) == VALID_TRANSITIONS[resulting_state]


@PBT_SETTINGS
@given(
    source_id=st.uuids(),
    timestamp_value=SAFE_DATETIMES,
    title=st.text(min_size=1, max_size=80),
    description=st.text(min_size=1, max_size=160),
    alt_text=st.text(max_size=160),
    priority=st.booleans(),
    order=st.integers(),
    unknown_fields=st.dictionaries(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=24).map(
            lambda suffix: f"extra_{suffix}"
        ),
        st.text(max_size=32),
        max_size=8,
    ),
)
def test_valid_nws_items_normalize_with_their_office_scoped_uuid_identity(
    source_id: UUID,
    timestamp_value: datetime,
    title: str,
    description: str,
    alt_text: str,
    priority: bool,
    order: int,
    unknown_fields: dict[str, str],
) -> None:
    payload = (
        _story_payload(
            timestamp_value,
            source_id,
            title=title,
            description=description,
            altText=alt_text,
            priority=priority,
            order=order,
        )
        | unknown_fields
    )

    collection = normalize_collection(
        httpx.Response(
            200, json={"stories": [payload]}, headers={"content-type": "application/json"}
        ),
        "MKX",
    )

    assert collection.quarantined == ()
    assert collection.stories[0].canonical_identity == ("MKX", str(source_id))


@PBT_SETTINGS
@given(retry_after_seconds=st.integers(min_value=0, max_value=300), deadline=st.integers(0, 400))
def test_rate_limited_retry_honors_the_complete_request_and_shutdown_reserve_budget(
    retry_after_seconds: int, deadline: int
) -> None:
    requests = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(429, headers={"Retry-After": str(retry_after_seconds)})
        return httpx.Response(200, json={"stories": []})

    client = NWSCollectionClient(
        httpx.Client(transport=httpx.MockTransport(handler)), clock=lambda: 0, sleeper=sleeps.append
    )
    retry_fits = retry_after_seconds + 10 <= deadline - 60

    if retry_fits:
        assert client.fetch(
            "https://api.weather.gov/offices/MKX/weatherstories", processing_deadline=deadline
        )
        assert requests == 2
        assert sleeps == [retry_after_seconds]
    else:
        with pytest.raises(NWSCollectionRequestError) as caught:
            client.fetch(
                "https://api.weather.gov/offices/MKX/weatherstories", processing_deadline=deadline
            )
        assert requests == 1
        assert sleeps == []
        assert caught.value.failure.retry_decision is RetryDecision.INSUFFICIENT_BUDGET


@PBT_SETTINGS
@given(
    metadata=st.dictionaries(
        st.text(min_size=1, max_size=40),
        st.one_of(st.integers(), st.text(max_size=400), st.booleans(), st.none()),
        max_size=20,
    )
)
def test_transition_metadata_is_allowlisted_and_bounded(metadata: dict[str, object]) -> None:
    sanitized = sanitize_transition_metadata(metadata)

    assert set(sanitized).issubset(PERMITTED_METADATA)
    assert all(len(value) <= MAX_FAILURE_SUMMARY_LENGTH for value in sanitized.values())
    assert sanitized == {
        key: str(value)[:MAX_FAILURE_SUMMARY_LENGTH]
        for key, value in metadata.items()
        if key in PERMITTED_METADATA
    }


@PBT_SETTINGS
@given(
    timestamp_value=SAFE_DATETIMES,
    source_id=st.uuids(),
    image_sha256=st.one_of(st.none(), st.text(max_size=80)),
)
def test_timestamp_and_revision_hash_are_stable_for_equivalent_utc_instants(
    timestamp_value: datetime, source_id: UUID, image_sha256: str | None
) -> None:
    utc_value = timestamp_value.astimezone(UTC)
    original_story = WeatherStory.model_validate(_story_payload(timestamp_value, source_id))
    utc_story = WeatherStory.model_validate(_story_payload(utc_value, source_id))

    assert timestamp(timestamp_value) == timestamp(utc_value)
    assert revision_hash(original_story, image_sha256) == revision_hash(utc_story, image_sha256)


@PBT_SETTINGS
@given(redirects=st.integers(min_value=0, max_value=MAX_REDIRECTS + 1))
def test_image_download_accepts_only_the_configured_number_of_safe_redirects(
    redirects: int,
) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        redirect_index = int(request.url.path.lstrip("/"))
        if redirect_index < redirects:
            return httpx.Response(302, headers={"location": f"/{redirect_index + 1}"})
        return httpx.Response(200, content=_tiny_png(), headers={"content-type": "image/png"})

    retainer = ImageRetainer(
        httpx.Client(transport=httpx.MockTransport(handler)),
        cast(S3Client, object()),
        cast(ImageHistory, object()),
        bucket="images",
        allowed_hosts={"weather.gov", "*.weather.gov"},
        clock=lambda: 0,
    )

    if redirects <= MAX_REDIRECTS:
        assert retainer.download("https://www.weather.gov/0").content_type == "image/png"
        assert requests == redirects + 1
    else:
        with pytest.raises(ImageRetentionError, match="redirect policy"):
            retainer.download("https://www.weather.gov/0")
        assert requests == MAX_REDIRECTS + 1
