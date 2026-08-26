from pathlib import Path

import pytest

from weather_story_bot.config import OfficeRegistry
from weather_story_bot.runtime import load_publisher_runtime_settings


def _registry() -> OfficeRegistry:
    return OfficeRegistry.model_validate(
        {
            "schema_version": 1,
            "offices": [
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
                    "telegram_channel_id": "mock:weather-story-mkx",
                    "active": True,
                }
            ],
        }
    )


def _environment(tmp_path: Path) -> dict[str, str]:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(_registry().model_dump_json(), encoding="utf-8")
    return {
        "OFFICE_REGISTRY_PATH": str(registry_path),
        "ENVIRONMENT_CONFIG_PATH": str(
            Path(__file__).parent.parent / "config/environments/dev.json"
        ),
        "HISTORY_TABLE_NAME": "weather-story-dev-history",
        "IMAGE_BUCKET_NAME": "weather-story-dev-images",
        "ALERT_TRIGGER_TOPIC_ARN": "arn:aws:sns:us-east-2:123456789012:weather-story-dev-alerts",
        "TELEGRAM_SECRET_ARN": "arn:aws:secretsmanager:us-east-2:123456789012:secret:dev",
    }


def test_load_publisher_runtime_settings_validates_packaged_configuration(tmp_path: Path) -> None:
    settings = load_publisher_runtime_settings(_environment(tmp_path))

    assert settings.environment.environment == "dev"
    assert tuple(office.office_id for office in settings.registry.offices if office.active) == (
        "MKX",
    )
    assert settings.history_table_name == "weather-story-dev-history"


def test_load_publisher_runtime_settings_rejects_missing_resource_reference(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    del environment["IMAGE_BUCKET_NAME"]

    with pytest.raises(RuntimeError, match="IMAGE_BUCKET_NAME"):
        load_publisher_runtime_settings(environment)


def test_load_publisher_runtime_settings_rejects_mismatched_active_registry(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    registry_path = Path(environment["OFFICE_REGISTRY_PATH"])
    registry = _registry().model_copy(
        update={"offices": (_registry().offices[0].model_copy(update={"active": False}),)}
    )
    registry_path.write_text(registry.model_dump_json(), encoding="utf-8")

    with pytest.raises(RuntimeError, match="active offices"):
        load_publisher_runtime_settings(environment)
