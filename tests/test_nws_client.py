from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest

from weather_story_bot.nws_client import (
    NWS_ACCEPT,
    NWS_REQUEST_TIMEOUT_SECONDS,
    NWS_SHUTDOWN_RESERVE_SECONDS,
    NWS_USER_AGENT,
    NWSCollectionClient,
    NWSCollectionFailureClass,
    NWSCollectionRequestError,
    RetryDecision,
    parse_retry_after,
)

URL = "https://api.weather.gov/offices/MKX/weatherstories"


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_collection_request_uses_identifying_headers_and_ten_second_timeout() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json={"stories": []})

    client = client_for(handler)
    response = NWSCollectionClient(client, clock=lambda: 0).fetch(URL, processing_deadline=100)

    assert response.status_code == 200
    assert seen_request is not None
    assert seen_request.headers["Accept"] == NWS_ACCEPT
    assert seen_request.headers["User-Agent"] == NWS_USER_AGENT
    assert "https://github.com/hamdrew/weather-story-bot" in seen_request.headers["User-Agent"]
    assert NWS_REQUEST_TIMEOUT_SECONDS == 10


@pytest.mark.parametrize(
    ("status", "error_class", "error_code"),
    [
        (404, NWSCollectionFailureClass.NOT_FOUND, "nws_collection_not_found"),
        (400, NWSCollectionFailureClass.CLIENT_ERROR, "nws_client_error"),
        (418, NWSCollectionFailureClass.CLIENT_ERROR, "nws_client_error"),
    ],
)
def test_non_rate_limited_4xx_fail_without_a_retry(
    status: int, error_class: NWSCollectionFailureClass, error_code: str
) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(status, text="untrusted upstream response body")

    with pytest.raises(NWSCollectionRequestError) as caught:
        NWSCollectionClient(client_for(handler), clock=lambda: 0).fetch(
            URL, processing_deadline=100
        )

    assert requests == 1
    assert caught.value.failure.error_class is error_class
    assert caught.value.failure.error_code == error_code
    assert caught.value.failure.retry_decision is RetryDecision.NOT_RETRYABLE
    assert "untrusted" not in caught.value.failure.error_summary


def test_rate_limit_retries_once_after_retry_after_when_within_budget() -> None:
    statuses = iter((429, 200))
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return httpx.Response(status, headers={"Retry-After": "2"})

    response = NWSCollectionClient(
        client_for(handler), clock=lambda: 0, sleeper=sleeps.append
    ).fetch(URL, processing_deadline=100)

    assert response.status_code == 200
    assert sleeps == [2]


def test_rate_limit_does_not_retry_when_delay_and_request_do_not_fit_budget() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(429, headers={"Retry-After": "31"})

    with pytest.raises(NWSCollectionRequestError) as caught:
        NWSCollectionClient(client_for(handler), clock=lambda: 0).fetch(
            URL, processing_deadline=100
        )

    assert NWS_SHUTDOWN_RESERVE_SECONDS == 60
    assert requests == 1
    assert caught.value.failure.error_class is NWSCollectionFailureClass.RATE_LIMITED
    assert caught.value.failure.retry_after_seconds == 31
    assert caught.value.failure.retry_decision is RetryDecision.INSUFFICIENT_BUDGET


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(503),
        httpx.ConnectError("private connection details"),
        httpx.ReadTimeout("private timeout details"),
    ],
)
def test_transient_failures_retry_once_and_report_only_sanitized_metadata(
    failure: httpx.Response | httpx.RequestError,
) -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if isinstance(failure, httpx.Response):
            return failure
        raise failure

    with pytest.raises(NWSCollectionRequestError) as caught:
        NWSCollectionClient(client_for(handler), clock=lambda: 0, sleeper=sleeps.append).fetch(
            URL, processing_deadline=100
        )

    assert attempts == 2
    assert sleeps == [1]
    assert caught.value.failure.retry_ordinal == 1
    assert caught.value.failure.retry_decision is RetryDecision.RETRY_FAILED
    assert "private" not in caught.value.failure.error_summary
    assert set(caught.value.failure.structured_fields()) == {
        "http_status",
        "error_class",
        "error_code",
        "error_summary",
        "retry_after_seconds",
        "retry_ordinal",
        "retry_decision",
    }


def test_invalid_or_absent_retry_after_is_not_retried() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "not-a-delay"})

    with pytest.raises(NWSCollectionRequestError) as caught:
        NWSCollectionClient(client_for(handler), clock=lambda: 0).fetch(
            URL, processing_deadline=100
        )

    assert caught.value.failure.retry_after_seconds is None
    assert caught.value.failure.retry_decision is RetryDecision.NOT_RETRYABLE


def test_parse_retry_after_parses_seconds_and_rejects_invalid_values() -> None:
    assert parse_retry_after("1.5") == 1.5
    assert parse_retry_after("-1") == 0
    assert parse_retry_after(None) is None
    assert parse_retry_after("invalid") is None


def test_parse_retry_after_http_date_uses_controlled_wall_clock_and_clamps_past_dates() -> None:
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC).timestamp()
    future = format_datetime(datetime(2026, 8, 15, 12, 0, 7, tzinfo=UTC), usegmt=True)
    past = format_datetime(datetime(2026, 8, 15, 11, 59, 59, tzinfo=UTC), usegmt=True)

    assert parse_retry_after(future, now=now) == 7
    assert parse_retry_after(past, now=now) == 0


def test_rate_limit_http_date_retry_after_is_used_for_the_single_retry() -> None:
    statuses = iter((429, 200))
    sleeps: list[float] = []
    retry_at = format_datetime(datetime(2026, 8, 15, 12, 0, 4, tzinfo=UTC), usegmt=True)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(statuses), headers={"Retry-After": retry_at})

    response = NWSCollectionClient(
        client_for(handler),
        clock=lambda: 0,
        wall_clock=lambda: datetime(2026, 8, 15, 12, 0, tzinfo=UTC).timestamp(),
        sleeper=sleeps.append,
    ).fetch(URL, processing_deadline=100)

    assert response.status_code == 200
    assert sleeps == [4]
