"""Deterministic operation ports with symbolic references, never Telegram identifiers."""

from test_runtime import _registry

from weather_story_bot.config import OfficeRegistryRecord
from weather_story_bot.operations import AlertDeliveryOutcome, PrivateAlert


class OfficePorts:
    def __init__(self) -> None:
        self.office = _registry().offices[0]
        self.calls: list[str] = []
        self.version: int | None = None
        self.current: tuple[str, str] | None = None
        self.failure = "none"

    def call(self, step: str) -> None:
        self.calls.append(step)
        if self.failure == step:
            raise RuntimeError("mock boundary failure")

    def load_office(self, office_id: str) -> OfficeRegistryRecord:
        self.call("load")
        return self.office

    def create_or_reuse_invite(self, office_id: str) -> str:
        self.call("invite")
        return "mock:invite-reference"

    def create_or_edit_office_message(self, office: OfficeRegistryRecord) -> str:
        self.call("message")
        return "mock:managed-reference"

    def pin_message(self, message_ref: str) -> None:
        self.call("pin")

    def is_message_pinned(self, message_ref: str) -> bool:
        self.call("verify")
        return self.failure != "unverified"

    def commit_current_office(
        self,
        office: OfficeRegistryRecord,
        *,
        pinned_message_ref: str,
        invite_ref: str,
        expected_version: int | None = None,
    ) -> int:
        self.call("commit")
        if self.version != expected_version:
            raise RuntimeError("mock conditional conflict")
        self.version = (self.version or 0) + 1
        self.current = (pinned_message_ref, invite_ref)
        return self.version


class Notifier:
    def __init__(self, outcome: AlertDeliveryOutcome, *, fail_fallback: bool = False) -> None:
        self.outcome = outcome
        self.fail_fallback = fail_fallback
        self.primary_calls = 0
        self.fallback_calls = 0

    def deliver_private_alert(self, alert: PrivateAlert) -> AlertDeliveryOutcome:
        self.primary_calls += 1
        return self.outcome

    def deliver_fallback(self, alert: PrivateAlert) -> None:
        self.fallback_calls += 1
        if self.fail_fallback:
            raise RuntimeError("mock fallback failure")
