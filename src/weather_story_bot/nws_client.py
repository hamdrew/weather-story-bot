"""Safe, bounded HTTP access to National Weather Service collections."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from enum import StrEnum
from time import monotonic, sleep, time
from typing import Final, Protocol

import httpx

NWS_USER_AGENT: Final = "weather-story-bot/0.1.0 (https://github.com/hamdrew/weather-story-bot)"
NWS_ACCEPT: Final = "application/ld+json, application/json;q=0.9"
NWS_REQUEST_TIMEOUT_SECONDS: Final = 10.0
NWS_SHUTDOWN_RESERVE_SECONDS: Final = 60.0
TRANSIENT_RETRY_DELAY_SECONDS: Final = 1.0
MAX_ERROR_SUMMARY_LENGTH: Final = 256


class NWSCollectionFailureClass(StrEnum):
    """Stable, bounded categories for collection-request failures."""

    NOT_FOUND = "not_found"
    CLIENT_ERROR = "client_error"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"


class RetryDecision(StrEnum):
    """The single retry decision recorded for an unsuccessful request."""

    NOT_RETRYABLE = "not_retryable"
    RETRIED = "retried"
    INSUFFICIENT_BUDGET = "insufficient_budget"
    RETRY_FAILED = "retry_failed"


@dataclass(frozen=True)
class NWSCollectionFailure:
    """Sanitized metadata suitable for durable records and structured logs."""

    error_class: NWSCollectionFailureClass
    error_code: str
    error_summary: str
    retry_ordinal: int
    retry_decision: RetryDecision
    http_status: int | None = None
    retry_after_seconds: float | None = None

    def structured_fields(self) -> Mapping[str, int | float | str | None]:
        """Return only allowlisted, bounded fields; never expose upstream bodies."""
        return {
            "http_status": self.http_status,
            "error_class": self.error_class,
            "error_code": self.error_code,
            "error_summary": self.error_summary,
            "retry_after_seconds": self.retry_after_seconds,
            "retry_ordinal": self.retry_ordinal,
            "retry_decision": self.retry_decision,
        }


class NWSCollectionRequestError(Exception):
    """Raised when an NWS collection cannot be retrieved within its retry policy."""

    def __init__(self, failure: NWSCollectionFailure) -> None:
        self.failure = failure
        super().__init__(failure.error_code)


class SupportsGet(Protocol):
    """The subset of ``httpx.Client`` used by the NWS collection client."""

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: float,
    ) -> httpx.Response: ...


class NWSCollectionClient:
    """Retrieve one NWS collection with safe headers, deadlines, and one retry."""

    def __init__(
        self,
        client: SupportsGet,
        *,
        request_timeout_seconds: float = NWS_REQUEST_TIMEOUT_SECONDS,
        shutdown_reserve_seconds: float = NWS_SHUTDOWN_RESERVE_SECONDS,
        clock: Callable[[], float] = monotonic,
        wall_clock: Callable[[], float] = time,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        if shutdown_reserve_seconds < 0:
            raise ValueError("shutdown_reserve_seconds cannot be negative")
        self._client = client
        self._request_timeout_seconds = request_timeout_seconds
        self._shutdown_reserve_seconds = shutdown_reserve_seconds
        self._clock = clock
        self._wall_clock = wall_clock
        self._sleeper = sleeper

    def fetch(self, url: str, *, processing_deadline: float) -> httpx.Response:
        """Fetch a collection, retrying exactly once only when the budget permits it."""
        retry_ordinal = 0
        while True:
            failure, response = self._request_once(url, retry_ordinal)
            if response is not None:
                return response
            assert failure is not None

            retry_delay = self._retry_delay(failure)
            if retry_ordinal == 1:
                raise NWSCollectionRequestError(
                    self._with_retry_decision(failure, RetryDecision.RETRY_FAILED)
                )
            if retry_delay is None:
                raise NWSCollectionRequestError(
                    self._with_retry_decision(failure, RetryDecision.NOT_RETRYABLE)
                )
            if not self._fits_before_reserve(retry_delay, processing_deadline):
                raise NWSCollectionRequestError(
                    self._with_retry_decision(failure, RetryDecision.INSUFFICIENT_BUDGET)
                )

            self._sleeper(retry_delay)
            retry_ordinal = 1

    def _request_once(
        self, url: str, retry_ordinal: int
    ) -> tuple[NWSCollectionFailure | None, httpx.Response | None]:
        try:
            response = self._client.get(
                url,
                headers={"Accept": NWS_ACCEPT, "User-Agent": NWS_USER_AGENT},
                timeout=self._request_timeout_seconds,
            )
        except httpx.TimeoutException:
            return self._failure(
                NWSCollectionFailureClass.TIMEOUT,
                "nws_request_timeout",
                "NWS collection request timed out",
                retry_ordinal,
            ), None
        except httpx.RequestError:
            return self._failure(
                NWSCollectionFailureClass.CONNECTION_ERROR,
                "nws_connection_failure",
                "NWS collection connection failed",
                retry_ordinal,
            ), None

        if 200 <= response.status_code < 300:
            return None, response
        return self._failure_from_response(response, retry_ordinal), None

    def _failure_from_response(
        self, response: httpx.Response, retry_ordinal: int
    ) -> NWSCollectionFailure:
        status = response.status_code
        if status == 404:
            return self._failure(
                NWSCollectionFailureClass.NOT_FOUND,
                "nws_collection_not_found",
                "NWS collection was not found",
                retry_ordinal,
                http_status=status,
            )
        if status == 429:
            retry_after = parse_retry_after(
                response.headers.get("Retry-After"), now=self._wall_clock()
            )
            return self._failure(
                NWSCollectionFailureClass.RATE_LIMITED,
                "nws_rate_limited",
                "NWS collection request was rate limited",
                retry_ordinal,
                http_status=status,
                retry_after_seconds=retry_after,
            )
        if 400 <= status < 500:
            return self._failure(
                NWSCollectionFailureClass.CLIENT_ERROR,
                "nws_client_error",
                "NWS collection request was rejected",
                retry_ordinal,
                http_status=status,
            )
        if 500 <= status < 600:
            return self._failure(
                NWSCollectionFailureClass.SERVER_ERROR,
                "nws_server_error",
                "NWS collection service failed",
                retry_ordinal,
                http_status=status,
            )
        return self._failure(
            NWSCollectionFailureClass.SERVER_ERROR,
            "nws_unexpected_status",
            "NWS collection returned an unexpected status",
            retry_ordinal,
            http_status=status,
        )

    def _fits_before_reserve(self, delay: float, processing_deadline: float) -> bool:
        return (
            self._clock() + delay + self._request_timeout_seconds
            <= processing_deadline - self._shutdown_reserve_seconds
        )

    @staticmethod
    def _retry_delay(failure: NWSCollectionFailure) -> float | None:
        if failure.error_class is NWSCollectionFailureClass.RATE_LIMITED:
            return failure.retry_after_seconds
        if failure.error_class in {
            NWSCollectionFailureClass.SERVER_ERROR,
            NWSCollectionFailureClass.CONNECTION_ERROR,
            NWSCollectionFailureClass.TIMEOUT,
        }:
            return TRANSIENT_RETRY_DELAY_SECONDS
        return None

    @staticmethod
    def _with_retry_decision(
        failure: NWSCollectionFailure, decision: RetryDecision
    ) -> NWSCollectionFailure:
        return NWSCollectionFailure(
            error_class=failure.error_class,
            error_code=failure.error_code,
            error_summary=failure.error_summary,
            retry_ordinal=failure.retry_ordinal,
            retry_decision=decision,
            http_status=failure.http_status,
            retry_after_seconds=failure.retry_after_seconds,
        )

    @staticmethod
    def _failure(
        error_class: NWSCollectionFailureClass,
        error_code: str,
        error_summary: str,
        retry_ordinal: int,
        *,
        http_status: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> NWSCollectionFailure:
        return NWSCollectionFailure(
            error_class=error_class,
            error_code=error_code,
            error_summary=error_summary[:MAX_ERROR_SUMMARY_LENGTH],
            retry_ordinal=retry_ordinal,
            retry_decision=RetryDecision.NOT_RETRYABLE,
            http_status=http_status,
            retry_after_seconds=retry_after_seconds,
        )


def parse_retry_after(value: str | None, *, now: float | None = None) -> float | None:
    """Parse a non-negative HTTP ``Retry-After`` value without retaining the header."""
    if value is None:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        delay = retry_at.timestamp() - (time() if now is None else now)
    return max(delay, 0.0)
