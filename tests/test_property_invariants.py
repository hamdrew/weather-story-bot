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
from PIL import Image

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
