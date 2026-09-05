"""Bounded domain contracts for protected operations and alarm notification."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from detect_secrets.core.scan import scan_line
from detect_secrets.settings import transient_settings
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from weather_story_bot.config import Environment, OfficeRegistryRecord
from weather_story_bot.telegram import Caption, render_caption


def safe_text(value: str) -> str:
    """Reject sensitive syntax; callers must still map external data to approved messages."""
    with transient_settings({"plugins_used": _STRUCTURED_SECRET_PLUGINS}):
        if any(scan_line(value)):
            raise ValueError("text contains a detected secret")
    if re.search(
        r"[\x00-\x1f\x7f<>@/\\]|https?:|\d{6}|(?:token|secret|password)\s*[=:]", value, re.I
    ):
        raise ValueError("text contains prohibited diagnostic content")
    return value


def unlimited_budget() -> None:
    """Domain-only default; Lambda composition supplies an invocation deadline guard."""


def render_office_information(office: OfficeRegistryRecord) -> Caption:
    """Render public NWS office context as bounded literal text with explicit entities."""
    address = office.address
    lines = [
        address.street_address,
        f"{address.locality}, {address.region} {address.postal_code}",
        office.timezone,
        *[value for value in (office.telephone, office.email, office.region_name) if value],
    ]
    return render_caption(office.display_name, "\n".join(lines), "")


_STRUCTURED_SECRET_PLUGINS = [
    {"name": name}
    for name in (
        "ArtifactoryDetector",
        "AWSKeyDetector",
        "AzureStorageKeyDetector",
        "BasicAuthDetector",
        "CloudantDetector",
        "DiscordBotTokenDetector",
        "GitHubTokenDetector",
        "GitLabTokenDetector",
        "IbmCloudIamDetector",
        "IbmCosHmacDetector",
        "JwtTokenDetector",
        "MailchimpDetector",
        "NpmDetector",
        "OpenAIDetector",
        "PrivateKeyDetector",
        "PypiTokenDetector",
        "SendGridDetector",
        "SlackDetector",
        "SoftlayerDetector",
        "SquareOAuthDetector",
        "StripeDetector",
        "TelegramBotTokenDetector",
        "TwilioKeyDetector",
    )
]


class AlertDeliveryOutcome(StrEnum):
    """Objective result of one private alert attempt."""

    ACKNOWLEDGED = "acknowledged"
    DEFINITIVE_FAILURE = "definitive_failure"
    AMBIGUOUS = "ambiguous"


class FallbackDeliveryOutcome(StrEnum):
    """Result of the single permitted fallback attempt."""

    NOT_ATTEMPTED = "not_attempted"
    DELIVERED = "delivered"
    FAILED = "failed"


class SecretCheckedModel(BaseModel):
    """Base model that rejects secret-bearing summary text before use."""

    @field_validator("*", mode="after")
    @classmethod
    def summary_is_safe(cls, value: object) -> object:
        if isinstance(value, str):
            return safe_text(value)
        return value


class OfficeInformationCommand(BaseModel):
    """Authorized, bounded command that cannot request publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    environment: Environment
    office_id: str = Field(pattern=r"^[A-Z]{3}$")
    operator_id: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)


class OfficeProfileLoader(Protocol):
    """Retrieve the current validated office profile for a protected refresh."""

    def load_office(self, office_id: str) -> OfficeRegistryRecord: ...


class OfficeInformationTelegram(Protocol):
    """The Telegram management operations permitted to office refresh."""

    def create_or_reuse_invite(self, office_id: str) -> str: ...

    def create_or_edit_office_message(self, office: OfficeRegistryRecord) -> str: ...

    def pin_message(self, message_ref: str) -> None: ...

    def is_message_pinned(self, message_ref: str) -> bool: ...


class CurrentOfficeStore(Protocol):
    """Conditionally retain one verified managed office reference."""

    def commit_current_office(
        self,
        office: OfficeRegistryRecord,
        *,
        pinned_message_ref: str,
        invite_ref: str,
        expected_version: int | None = None,
    ) -> int: ...


class OfficeInformationRefreshError(RuntimeError):
    """A required protected refresh step did not complete safely."""


class OfficeRefreshResult(BaseModel):
    """Safe result that never returns Telegram-managed references."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    office_id: str = Field(pattern=r"^[A-Z]{3}$")
    outcome: str = Field(pattern=r"^refreshed$")
    version: int = Field(ge=1)


class OfficeInformationService:
    """Perform a protected refresh and commit only independently verified references."""

    def __init__(
        self,
        profile_loader: OfficeProfileLoader,
        telegram: OfficeInformationTelegram,
        store: CurrentOfficeStore,
        *,
        environment: str,
    ) -> None:
        self._profile_loader = profile_loader
        self._telegram = telegram
        self._store = store
        self._environment = environment

    def refresh(
        self,
        command: OfficeInformationCommand,
        *,
        expected_version: int | None = None,
        check_budget: Callable[[], None] = unlimited_budget,
    ) -> OfficeRefreshResult:
        """Refresh one office without creating a publication attempt or schedule action."""
        if command.environment != self._environment:
            raise OfficeInformationRefreshError("command environment is not authorized")
        if expected_version is not None and (
            isinstance(expected_version, bool) or expected_version < 1
        ):
            raise OfficeInformationRefreshError("invalid current office version")
        check_budget()
        office = self._profile_loader.load_office(command.office_id)
        if office.office_id != command.office_id or not office.active:
            raise OfficeInformationRefreshError("office is not authorized for refresh")
        check_budget()
        invite_ref = self._telegram.create_or_reuse_invite(office.office_id)
        check_budget()
        message_ref = self._telegram.create_or_edit_office_message(office)
        check_budget()
        self._telegram.pin_message(message_ref)
        check_budget()
        if not self._telegram.is_message_pinned(message_ref):
            raise OfficeInformationRefreshError("office message pin verification failed")
        check_budget()
        version = self._store.commit_current_office(
            office,
            pinned_message_ref=message_ref,
            invite_ref=invite_ref,
            expected_version=expected_version,
        )
        return OfficeRefreshResult(office_id=office.office_id, outcome="refreshed", version=version)


class AlarmTransition(SecretCheckedModel):
    """Safe subset of a CloudWatch alarm transition supplied by the SNS trigger."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    source: str = Field(pattern=r"^aws\.cloudwatch$")
    environment: Environment
    alarm_name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,127}$")
    state: str = Field(pattern=r"^ALARM$")
    summary: str = Field(min_length=1, max_length=512)
    event_time: AwareDatetime | None = None


class SafeObservation(SecretCheckedModel):
    """Allowlisted, bounded diagnostic record."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_type: str = Field(min_length=1, max_length=64)
    classification: str = Field(min_length=1, max_length=64)
    correlation_id: str | None = Field(default=None, max_length=128)
    summary: str = Field(min_length=1, max_length=512)


def sanitize_observation(candidate: Mapping[str, object]) -> SafeObservation:
    """Project safe classifications; never pass through arbitrary external diagnostic text."""
    allowed = {"office", "alert", "refreshed", "acknowledged", "ambiguous", "failed", "rejected"}
    event = candidate.get("event_type")
    classification = candidate.get("classification")
    return SafeObservation(
        event_type=event if isinstance(event, str) and event in {"office", "alert"} else "alert",
        classification=(
            classification
            if isinstance(classification, str) and classification in allowed
            else "failed"
        ),
        summary="Protected operation outcome",
    )


def observation_record(candidate: Mapping[str, object], request_id: str) -> dict[str, object]:
    """Create a centralized structured record without serializing exceptions or input payloads."""
    safe_request = request_id if re.fullmatch(r"[a-f0-9-]{1,36}", request_id) else "unavailable"
    observation = sanitize_observation(candidate)
    return {
        **observation.model_dump(),
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "ERROR"
        if observation.classification in {"failed", "rejected", "ambiguous"}
        else "INFO",
        "request_id": safe_request,
    }


class PrivateAlert(SecretCheckedModel):
    """Bounded private alert text derived from an accepted alarm transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    summary: str = Field(min_length=1, max_length=512)


class AlertDispatchResult(BaseModel):
    """Safe, terminal result of a private alert and its optional fallback."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    primary_outcome: AlertDeliveryOutcome
    fallback_outcome: FallbackDeliveryOutcome


class AlertNotifier(Protocol):
    """Private alert and independent fallback operations."""

    def deliver_private_alert(self, alert: PrivateAlert) -> AlertDeliveryOutcome: ...

    def deliver_fallback(self, alert: PrivateAlert) -> None: ...


def render_private_alert(alarm: AlarmTransition) -> PrivateAlert:
    """Render only the bounded, already secret-checked alarm fields."""
    summary = f"Alarm {alarm.alarm_name} is {alarm.state}: {alarm.summary}"
    if alarm.event_time is not None:
        event_time = alarm.event_time.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%SZ")
        summary = f"ERROR {event_time} {summary}"
    return PrivateAlert(summary=summary[:512])


def dispatch_alarm(
    alarm: AlarmTransition,
    notifier: AlertNotifier,
    *,
    check_budget: Callable[[], None] = unlimited_budget,
) -> AlertDispatchResult:
    """Deliver one private alert and at most one fallback, with a terminal safe result."""
    alert = render_private_alert(alarm)
    check_budget()
    try:
        outcome = notifier.deliver_private_alert(alert)
    except Exception:
        # An exception after starting delivery cannot prove that Telegram rejected it.
        outcome = AlertDeliveryOutcome.AMBIGUOUS
    if outcome is AlertDeliveryOutcome.DEFINITIVE_FAILURE:
        try:
            check_budget()
            notifier.deliver_fallback(alert)
        except Exception:
            return AlertDispatchResult(
                primary_outcome=outcome,
                fallback_outcome=FallbackDeliveryOutcome.FAILED,
            )
        return AlertDispatchResult(
            primary_outcome=outcome,
            fallback_outcome=FallbackDeliveryOutcome.DELIVERED,
        )
    return AlertDispatchResult(
        primary_outcome=outcome,
        fallback_outcome=FallbackDeliveryOutcome.NOT_ATTEMPTED,
    )
