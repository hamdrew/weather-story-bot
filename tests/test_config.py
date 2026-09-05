from pathlib import Path

import pytest
from pydantic import ValidationError

from weather_story_bot.config import (
    ConfigurationError,
    EnvironmentConfig,
    NWSOfficeSeedSet,
    OfficeCoordinates,
    OfficeRegistry,
    OfficeRegistryRecord,
    derive_timezone,
    load_environment_config,
    load_seed_set,
    validate_environment_isolation,
    validate_telegram_secret,
    weather_stories_url,
)

ROOT = Path(__file__).parent.parent


def test_seed_set_rejects_duplicate_ids_without_requiring_a_specific_office() -> None:
    base = {"schema_version": 1, "source": "https://example.test/offices"}

    with pytest.raises(ValidationError, match="office_ids must be unique"):
        NWSOfficeSeedSet.model_validate(base | {"office_ids": ("MKX", "MKX")})

    assert NWSOfficeSeedSet.model_validate(base | {"office_ids": ("GRB",)}).office_ids == ("GRB",)


def test_versioned_seed_set_contains_every_current_wfo_and_mkx() -> None:
    seeds = load_seed_set(ROOT / "data/nws_office_ids.v1.json")

    assert len(seeds.office_ids) == 124
    assert len(set(seeds.office_ids)) == 124
    assert weather_stories_url("MKX") == "https://api.weather.gov/offices/MKX/weatherstories"


def test_environment_configuration_is_isolated_and_destinations_match_active_offices() -> None:
    configs = [
        load_environment_config(ROOT / "config/environments" / f"{environment}.json")
        for environment in ("dev", "staging", "prod")
    ]

    validate_environment_isolation(configs)
    assert all(set(config.active_office_ids) == set(config.office_channels) for config in configs)
    assert all(
        set(config.nws_image_host_allowlist) == {"weather.gov", "*.weather.gov"}
        for config in configs
    )
    assert configs[0].telegram_mode == "mock"


@pytest.mark.parametrize("offices", [(), ("GRB",), ("GRB", "ARX")])
def test_environment_accepts_configured_offices_without_a_required_office(
    offices: tuple[str, ...],
) -> None:
    base = load_environment_config(ROOT / "config/environments/dev.json")
    config = EnvironmentConfig.model_validate(
        base.model_dump(exclude={"office_channels"})
        | {
            "active_office_ids": offices,
            "office_channels": {office: f"mock:channel-{office}" for office in offices},
        }
    )
    assert config.active_office_ids == offices


def test_active_registry_channels_must_be_present_and_unique() -> None:
    base = {
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
        "active": True,
    }
    with pytest.raises(ValidationError, match="requires a telegram_channel_id"):
        OfficeRegistryRecord.model_validate(base | {"office_id": "MKX"})

    for invalid_url in (
        "https://evil.example/story",
        "https://api.weather.gov/offices/MKX/weatherstories?unexpected=value",
        "https://user:password@api.weather.gov/offices/MKX/weatherstories",
        "https://api.weather.gov/offices/GRB/weatherstories",
    ):
        with pytest.raises(ValidationError, match="canonical NWS"):
            OfficeRegistryRecord.model_validate(
                base | {"office_id": "MKX", "weather_stories_url": invalid_url}
            )

    with pytest.raises(ValidationError, match="derived from the geocoded"):
        OfficeRegistryRecord.model_validate(
            base
            | {
                "office_id": "MKX",
                "telegram_channel_id": "-1001",
                "timezone": "America/New_York",
            }
        )

    with pytest.raises(ValidationError):
        OfficeRegistryRecord.model_validate(
            base
            | {
                "office_id": "MKX",
                "telegram_channel_id": "-1001",
                "coordinates": {"latitude": 91, "longitude": -88.46},
            }
        )

    first = OfficeRegistryRecord.model_validate(
        base | {"office_id": "MKX", "telegram_channel_id": "-1001"}
    )
    second = OfficeRegistryRecord.model_validate(
        base
        | {
            "office_id": "GRB",
            "weather_stories_url": "https://api.weather.gov/offices/GRB/weatherstories",
            "telegram_channel_id": "-1001",
        }
    )
    with pytest.raises(ValidationError, match="must be unique"):
        OfficeRegistry(schema_version=1, offices=(first, second))


def test_registry_rejects_non_https_urls_and_invalid_timezones() -> None:
    base = {
        "office_id": "MKX",
        "weather_stories_url": "http://api.weather.gov/offices/MKX/weatherstories",
        "display_name": "Milwaukee/Sullivan, WI",
        "address": {
            "street_address": "N3533 Hardscrabble Road",
            "locality": "Dousman",
            "region": "WI",
            "postal_code": "53118",
        },
        "coordinates": {"latitude": 43.04, "longitude": -88.46},
        "timezone": "America/Chicago",
        "telegram_channel_id": "-1001",
        "active": True,
    }

    with pytest.raises(ValidationError, match="URL must use HTTPS"):
        OfficeRegistryRecord.model_validate(base)

    with pytest.raises(ValidationError, match="timezone must be a valid IANA timezone"):
        OfficeRegistryRecord.model_validate(
            base
            | {
                "weather_stories_url": "https://api.weather.gov/offices/MKX/weatherstories",
                "timezone": "Not/A-Timezone",
            }
        )


def test_environment_rejects_invalid_telegram_modes_for_every_destination() -> None:
    with pytest.raises(ValidationError, match="nws_image_host_allowlist"):
        EnvironmentConfig(
            schema_version=1,
            environment="dev",
            telegram_mode="mock",
            nws_image_host_allowlist=("weather.gov",),
            active_office_ids=("MKX",),
            office_channels={"MKX": "mock:weather-story-mkx"},
            alert_recipient="mock:weather-story-operator",
        )

    with pytest.raises(ValidationError, match="active_office_ids must be unique"):
        EnvironmentConfig(
            schema_version=1,
            environment="staging",
            telegram_mode="live",
            nws_image_host_allowlist=("weather.gov", "*.weather.gov"),
            active_office_ids=("GRB", "GRB"),
            office_channels={"GRB": "-1001"},
            alert_recipient="-1002",
        )

    with pytest.raises(ValidationError, match="dev must use mock"):
        EnvironmentConfig(
            schema_version=1,
            environment="dev",
            telegram_mode="live",
            nws_image_host_allowlist=("weather.gov", "*.weather.gov"),
            active_office_ids=("MKX",),
            office_channels={"MKX": "-1001"},
            alert_recipient="-1002",
        )

    with pytest.raises(ValidationError, match="dev must use mock"):
        EnvironmentConfig(
            schema_version=1,
            environment="dev",
            telegram_mode="mock",
            nws_image_host_allowlist=("weather.gov", "*.weather.gov"),
            active_office_ids=("MKX",),
            office_channels={"MKX": "mock:weather-story-mkx"},
            alert_recipient="-1002",
        )

    with pytest.raises(ValidationError, match="staging and prod must use live"):
        EnvironmentConfig(
            schema_version=1,
            environment="staging",
            telegram_mode="live",
            nws_image_host_allowlist=("weather.gov", "*.weather.gov"),
            active_office_ids=("MKX",),
            office_channels={"MKX": "-1001"},
            alert_recipient="mock:weather-story-operator",
        )

    staging = EnvironmentConfig(
        schema_version=1,
        environment="staging",
        telegram_mode="live",
        nws_image_host_allowlist=("weather.gov", "*.weather.gov"),
        active_office_ids=("MKX",),
        office_channels={"MKX": "-1001"},
        alert_recipient="-1002",
    )
    prod = staging.model_copy(update={"environment": "prod"})
    dev = load_environment_config(ROOT / "config/environments/dev.json")
    with pytest.raises(ConfigurationError, match="must be distinct"):
        validate_environment_isolation((dev, staging, prod))

    with pytest.raises(ConfigurationError, match="exactly once"):
        validate_environment_isolation((dev, staging, staging, prod))


def test_environment_channel_destinations_are_immutable_after_validation() -> None:
    config = load_environment_config(ROOT / "config/environments/dev.json")

    with pytest.raises(TypeError):
        config.office_channels["MKX"] = "-1000000000001"  # type: ignore[index]


def test_timezone_and_versioned_secret_validation() -> None:
    coordinates = OfficeCoordinates(latitude=43.04, longitude=-88.46)
    assert derive_timezone(coordinates) == "America/Chicago"
    secret = '{"schema_version": 1, "telegram_bot_token": "test-token"}'
    assert validate_telegram_secret(secret) == "test-token"
    with pytest.raises(ConfigurationError):
        validate_telegram_secret('{"schema_version": 2, "telegram_bot_token": "test-token"}')


@pytest.mark.parametrize(
    ("secret_json", "message"),
    [
        ("not-json", "not valid JSON"),
        ("[]", "must be an object"),
        (
            '{"schema_version": 1, "telegram_bot_token": "token", "extra": true}',
            "invalid field set",
        ),
        ('{"schema_version": 1, "telegram_bot_token": 42}', "does not match schema version 1"),
        ('{"schema_version": 1, "telegram_bot_token": "   "}', "cannot be blank"),
    ],
)
def test_versioned_secret_rejects_malformed_json_shapes(secret_json: str, message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        validate_telegram_secret(secret_json)


@pytest.mark.parametrize("field", ["display_name", "telephone", "email", "region_name"])
def test_office_profile_rejects_unbounded_rendered_fields(field: str) -> None:
    from test_runtime import _registry

    value = _registry().offices[0].model_dump() | {field: "a" * 257}
    with pytest.raises(ValueError):
        OfficeRegistryRecord.model_validate(value)
