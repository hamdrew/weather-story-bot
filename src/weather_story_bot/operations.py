"""Bounded domain contracts for protected operations and alarm notification."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from detect_secrets.core.scan import scan_line
from detect_secrets.settings import transient_settings
from pydantic import BaseModel, ConfigDict, Field, field_validator

from weather_story_bot.config import OfficeRegistryRecord

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

    @field_validator("summary", check_fields=False)
    @classmethod
    def summary_is_safe(cls, value: str) -> str:
        with transient_settings({"plugins_used": _STRUCTURED_SECRET_PLUGINS}):
            detected = any(scan_line(value))
        if detected:
            raise ValueError("summary contains a detected secret")
        return value


class OfficeInformationCommand(BaseModel):
    """Authorized, bounded command that cannot request publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    environment: str = Field(min_length=1, max_length=16)
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
        self, command: OfficeInformationCommand, *, expected_version: int | None = None
    ) -> OfficeRefreshResult:
        """Refresh one office without creating a publication attempt or schedule action."""
        if command.environment != self._environment:
            raise OfficeInformationRefreshError("command environment is not authorized")
        office = self._profile_loader.load_office(command.office_id)
        if office.office_id != command.office_id or not office.active:
            raise OfficeInformationRefreshError("office is not authorized for refresh")
        invite_ref = self._telegram.create_or_reuse_invite(office.office_id)
        message_ref = self._telegram.create_or_edit_office_message(office)
        self._telegram.pin_message(message_ref)
        if not self._telegram.is_message_pinned(message_ref):
            raise OfficeInformationRefreshError("office message pin verification failed")
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
    environment: str = Field(min_length=1, max_length=16)
    alarm_name: str = Field(min_length=1, max_length=128)
    state: str = Field(pattern=r"^ALARM$")
    summary: str = Field(min_length=1, max_length=512)


class SafeObservation(SecretCheckedModel):
    """Allowlisted, bounded diagnostic record."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_type: str = Field(min_length=1, max_length=64)
    classification: str = Field(min_length=1, max_length=64)
    correlation_id: str | None = Field(default=None, max_length=128)
    summary: str = Field(min_length=1, max_length=512)


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
    return PrivateAlert(summary=summary[:512])


def dispatch_alarm(alarm: AlarmTransition, notifier: AlertNotifier) -> AlertDispatchResult:
    """Deliver one private alert and at most one fallback, with a terminal safe result."""
    alert = render_private_alert(alarm)
    outcome = notifier.deliver_private_alert(alert)
    if outcome is AlertDeliveryOutcome.DEFINITIVE_FAILURE:
        try:
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
