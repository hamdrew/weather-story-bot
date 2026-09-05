import pytest
from operation_fakes import OfficePorts
from pydantic import ValidationError

from weather_story_bot.config import OfficeRegistryRecord, weather_stories_url
from weather_story_bot.operations import (
    AlarmTransition,
    AlertDeliveryOutcome,
    AlertDispatchResult,
    FallbackDeliveryOutcome,
    OfficeInformationCommand,
    OfficeInformationRefreshError,
    OfficeInformationService,
    SafeObservation,
    dispatch_alarm,
    render_office_information,
    render_private_alert,
)


def test_office_information_rendering_excludes_protected_references_and_coordinates() -> None:
    office = OfficePorts().office
    caption = render_office_information(office)
    assert caption.text.startswith(office.display_name)
    assert office.address.street_address in caption.text
    assert office.timezone in caption.text
    assert "mock:" not in caption.text
    assert str(office.coordinates.latitude) not in caption.text
    assert caption.entities[0]["type"] == "bold"


@pytest.mark.parametrize("active", [True, False])
def test_office_refresh_uses_profile_active_state_for_any_office(active: bool) -> None:
    ports = OfficePorts()
    ports.office = OfficeRegistryRecord.model_validate(
        ports.office.model_dump()
        | {
            "office_id": "GRB",
            "weather_stories_url": weather_stories_url("GRB"),
            "active": active,
        }
    )
    service = OfficeInformationService(ports, ports, ports, environment="dev")
    command = OfficeInformationCommand(
        environment="dev", office_id="GRB", operator_id="operator", correlation_id="corr"
    )
    if active:
        assert service.refresh(command).office_id == "GRB"
        assert ports.current is not None
    else:
        with pytest.raises(OfficeInformationRefreshError, match="not authorized"):
            service.refresh(command)
        assert ports.calls == ["load"]
        assert ports.current is None


@pytest.mark.parametrize("summary", ["https://example.invalid", "<b>content</b>", "line\nbreak"])
def test_safe_observations_reject_prohibited_content(summary: str) -> None:
    with pytest.raises(ValueError, match="prohibited"):
        SafeObservation(event_type="alert", classification="failed", summary=summary)


@pytest.mark.parametrize("version", [0, -1, True])
def test_refresh_rejects_invalid_version_before_external_work(version: int) -> None:
    ports = OfficePorts()
    with pytest.raises(OfficeInformationRefreshError, match="version"):
        OfficeInformationService(ports, ports, ports, environment="dev").refresh(
            OfficeInformationCommand(
                environment="dev", office_id="MKX", operator_id="operator", correlation_id="corr"
            ),
            expected_version=version,
        )
    assert ports.calls == []


@pytest.mark.parametrize(
    "failure", ["load", "invite", "message", "pin", "verify", "unverified", "commit"]
)
def test_refresh_failure_never_advances_current_reference(failure: str) -> None:
    ports = OfficePorts()
    ports.failure = failure
    service = OfficeInformationService(ports, ports, ports, environment="dev")
    with pytest.raises(RuntimeError):
        service.refresh(
            OfficeInformationCommand(
                environment="dev", office_id="MKX", operator_id="operator", correlation_id="corr"
            )
        )
    assert ports.current is None
    assert ports.version is None


def test_refresh_reuses_current_reference_and_rejects_stale_version() -> None:
    ports = OfficePorts()
    service = OfficeInformationService(ports, ports, ports, environment="dev")
    command = OfficeInformationCommand(
        environment="dev", office_id="MKX", operator_id="operator", correlation_id="corr"
    )
    service.refresh(command)
    original = ports.current
    service.refresh(command, expected_version=1)
    assert ports.current == original
    assert ports.version == 2
    with pytest.raises(RuntimeError, match="conflict"):
        service.refresh(command, expected_version=1)
    assert ports.version == 2


@pytest.mark.parametrize("expire_before", range(6))
def test_refresh_checks_budget_before_every_external_step(expire_before: int) -> None:
    ports = OfficePorts()
    service = OfficeInformationService(ports, ports, ports, environment="dev")
    checks = 0

    def check() -> None:
        nonlocal checks
        if checks == expire_before:
            raise TimeoutError("budget exhausted")
        checks += 1

    with pytest.raises(TimeoutError):
        service.refresh(
            OfficeInformationCommand(
                environment="dev", office_id="MKX", operator_id="operator", correlation_id="corr"
            ),
            check_budget=check,
        )
    assert len(ports.calls) == expire_before
    assert ports.current is None


def test_alarm_transition_accepts_only_a_bounded_cloudwatch_alarm() -> None:
    alarm = AlarmTransition(
        source="aws.cloudwatch",
        environment="staging",
        alarm_name="publisher-failed",
        state="ALARM",
        summary="publisher failures exceeded the alarm threshold",
    )

    assert alarm.state == "ALARM"


@pytest.mark.parametrize("summary", ["-----BEGIN PRIVATE KEY-----"])
def test_safe_models_reject_sensitive_summaries(summary: str) -> None:
    with pytest.raises(ValidationError, match="detected secret"):
        SafeObservation(event_type="alert", classification="failed", summary=summary)

    with pytest.raises(ValidationError, match="detected secret"):
        AlarmTransition(
            source="aws.cloudwatch",
            environment="staging",
            alarm_name="publisher-failed",
            state="ALARM",
            summary=summary,
        )


def test_office_command_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        OfficeInformationCommand.model_validate(
            {
                "environment": "staging",
                "office_id": "MKX",
                "operator_id": "operator",
                "correlation_id": "corr-1",
                "publish_story": True,
            }
        )


def test_office_refresh_commits_only_after_pin_verification() -> None:
    calls: list[str] = []
    office = OfficeRegistryRecord.model_validate(
        {
            "office_id": "MKX",
            "weather_stories_url": "https://api.weather.gov/offices/MKX/weatherstories",
            "display_name": "Milwaukee/Sullivan, WI",
            "address": {
                "street_address": "N3533 Hardscrabble Road",
                "locality": "Dousman",
                "region": "WI",
                "postal_code": "53118",
            },
            "coordinates": {"latitude": 43.04, "longitude": -88.46},
            "timezone": "America/Chicago",
            "telegram_channel_id": "mock:mkx",
            "active": True,
        }
    )

    class Loader:
        def load_office(self, office_id: str) -> OfficeRegistryRecord:
            assert office_id == "MKX"
            return office

    class Telegram:
        def create_or_reuse_invite(self, office_id: str) -> str:
            calls.append("invite")
            return "invite"

        def create_or_edit_office_message(self, value: OfficeRegistryRecord) -> str:
            assert value is office
            calls.append("message")
            return "message"

        def pin_message(self, message_ref: str) -> None:
            assert message_ref == "message"
            calls.append("pin")

        def is_message_pinned(self, message_ref: str) -> bool:
            calls.append("verify")
            return True

    class Store:
        def commit_current_office(
            self,
            value: OfficeRegistryRecord,
            *,
            pinned_message_ref: str,
            invite_ref: str,
            expected_version: int | None = None,
        ) -> int:
            assert value is office
            assert pinned_message_ref == "message"
            assert invite_ref == "invite"
            assert expected_version is None
            calls.append("commit")
            return 1

    result = OfficeInformationService(Loader(), Telegram(), Store(), environment="staging").refresh(
        OfficeInformationCommand(
            environment="staging", office_id="MKX", operator_id="operator", correlation_id="corr"
        )
    )

    assert result.model_dump() == {"office_id": "MKX", "outcome": "refreshed", "version": 1}
    assert calls == ["invite", "message", "pin", "verify", "commit"]


def test_office_refresh_does_not_commit_when_pin_is_not_verified() -> None:
    class Loader:
        def load_office(self, office_id: str) -> OfficeRegistryRecord:
            return OfficeRegistryRecord.model_validate(
                {
                    "office_id": "MKX",
                    "weather_stories_url": "https://api.weather.gov/offices/MKX/weatherstories",
                    "display_name": "Office",
                    "address": {
                        "street_address": "1 Main",
                        "locality": "City",
                        "region": "WI",
                        "postal_code": "53118",
                    },
                    "coordinates": {"latitude": 43.04, "longitude": -88.46},
                    "timezone": "America/Chicago",
                    "telegram_channel_id": "mock:mkx",
                    "active": True,
                }
            )

    class Telegram:
        def create_or_reuse_invite(self, office_id: str) -> str:
            return "invite"

        def create_or_edit_office_message(self, office: OfficeRegistryRecord) -> str:
            return "message"

        def pin_message(self, message_ref: str) -> None:
            pass

        def is_message_pinned(self, message_ref: str) -> bool:
            return False

    class Store:
        def commit_current_office(
            self,
            office: OfficeRegistryRecord,
            *,
            pinned_message_ref: str,
            invite_ref: str,
            expected_version: int | None = None,
        ) -> int:
            raise AssertionError("must not commit")

    service = OfficeInformationService(Loader(), Telegram(), Store(), environment="staging")
    with pytest.raises(OfficeInformationRefreshError, match="pin verification"):
        service.refresh(
            OfficeInformationCommand(
                environment="staging",
                office_id="MKX",
                operator_id="operator",
                correlation_id="corr",
            )
        )


def test_office_refresh_rejects_wrong_environment_before_profile_load() -> None:
    class Loader:
        def load_office(self, office_id: str) -> OfficeRegistryRecord:
            raise AssertionError("must not load an unauthorized environment")

    class Telegram:
        def create_or_reuse_invite(self, office_id: str) -> str:
            raise AssertionError("must not use Telegram")

        def create_or_edit_office_message(self, office: OfficeRegistryRecord) -> str:
            raise AssertionError("must not use Telegram")

        def pin_message(self, message_ref: str) -> None:
            raise AssertionError("must not use Telegram")

        def is_message_pinned(self, message_ref: str) -> bool:
            raise AssertionError("must not use Telegram")

    class Store:
        def commit_current_office(
            self,
            office: OfficeRegistryRecord,
            *,
            pinned_message_ref: str,
            invite_ref: str,
            expected_version: int | None = None,
        ) -> int:
            raise AssertionError("must not commit")

    service = OfficeInformationService(Loader(), Telegram(), Store(), environment="staging")
    with pytest.raises(OfficeInformationRefreshError, match="environment"):
        service.refresh(
            OfficeInformationCommand(
                environment="prod", office_id="MKX", operator_id="operator", correlation_id="corr"
            )
        )


def test_office_refresh_propagates_expected_version_to_conditional_store() -> None:
    expected_versions: list[int | None] = []
    office = OfficeRegistryRecord.model_validate(
        {
            "office_id": "MKX",
            "weather_stories_url": "https://api.weather.gov/offices/MKX/weatherstories",
            "display_name": "Office",
            "address": {
                "street_address": "1 Main",
                "locality": "City",
                "region": "WI",
                "postal_code": "53118",
            },
            "coordinates": {"latitude": 43.04, "longitude": -88.46},
            "timezone": "America/Chicago",
            "telegram_channel_id": "mock:mkx",
            "active": True,
        }
    )

    class Loader:
        def load_office(self, office_id: str) -> OfficeRegistryRecord:
            return office

    class Telegram:
        def create_or_reuse_invite(self, office_id: str) -> str:
            return "invite"

        def create_or_edit_office_message(self, office: OfficeRegistryRecord) -> str:
            return "message"

        def pin_message(self, message_ref: str) -> None:
            pass

        def is_message_pinned(self, message_ref: str) -> bool:
            return True

    class Store:
        def commit_current_office(
            self,
            office: OfficeRegistryRecord,
            *,
            pinned_message_ref: str,
            invite_ref: str,
            expected_version: int | None = None,
        ) -> int:
            expected_versions.append(expected_version)
            return 5

    OfficeInformationService(Loader(), Telegram(), Store(), environment="staging").refresh(
        OfficeInformationCommand(
            environment="staging", office_id="MKX", operator_id="operator", correlation_id="corr"
        ),
        expected_version=4,
    )
    assert expected_versions == [4]


@pytest.mark.parametrize(
    ("outcome", "expected_fallback"),
    [
        (AlertDeliveryOutcome.ACKNOWLEDGED, 0),
        (AlertDeliveryOutcome.AMBIGUOUS, 0),
        (AlertDeliveryOutcome.DEFINITIVE_FAILURE, 1),
    ],
)
def test_alarm_dispatch_falls_back_only_after_definitive_failure(
    outcome: AlertDeliveryOutcome, expected_fallback: int
) -> None:
    fallback_calls = 0

    class Notifier:
        def deliver_private_alert(self, alert: object) -> AlertDeliveryOutcome:
            return outcome

        def deliver_fallback(self, alert: object) -> None:
            nonlocal fallback_calls
            fallback_calls += 1

    result = dispatch_alarm(
        AlarmTransition(
            source="aws.cloudwatch",
            environment="staging",
            alarm_name="publisher-failed",
            state="ALARM",
            summary="publisher failures exceeded the alarm threshold",
        ),
        Notifier(),
    )

    assert result == AlertDispatchResult(
        primary_outcome=outcome,
        fallback_outcome=(
            FallbackDeliveryOutcome.DELIVERED
            if outcome is AlertDeliveryOutcome.DEFINITIVE_FAILURE
            else FallbackDeliveryOutcome.NOT_ATTEMPTED
        ),
    )
    assert fallback_calls == expected_fallback


def test_alarm_dispatch_terminates_when_fallback_fails() -> None:
    fallback_calls = 0

    class Notifier:
        def deliver_private_alert(self, alert: object) -> AlertDeliveryOutcome:
            return AlertDeliveryOutcome.DEFINITIVE_FAILURE

        def deliver_fallback(self, alert: object) -> None:
            nonlocal fallback_calls
            fallback_calls += 1
            raise RuntimeError("fallback unavailable")

    result = dispatch_alarm(
        AlarmTransition(
            source="aws.cloudwatch",
            environment="staging",
            alarm_name="failed",
            state="ALARM",
            summary="safe failure",
        ),
        Notifier(),
    )
    assert result == AlertDispatchResult(
        primary_outcome=AlertDeliveryOutcome.DEFINITIVE_FAILURE,
        fallback_outcome=FallbackDeliveryOutcome.FAILED,
    )
    assert fallback_calls == 1


def test_private_alert_rendering_bounds_large_safe_inputs() -> None:
    alert = render_private_alert(
        AlarmTransition(
            source="aws.cloudwatch",
            environment="staging",
            alarm_name="a" * 128,
            state="ALARM",
            summary="b" * 512,
        )
    )
    assert len(alert.summary) == 512
