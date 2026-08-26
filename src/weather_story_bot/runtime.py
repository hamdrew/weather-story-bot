"""Validated non-secret inputs used to compose the publisher Lambda runtime."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from weather_story_bot.config import EnvironmentConfig, OfficeRegistry, load_environment_config


@dataclass(frozen=True)
class PublisherRuntimeSettings:
    """Exact environment-scoped references and validated packaged configuration."""

    registry: OfficeRegistry
    environment: EnvironmentConfig
    history_table_name: str
    image_bucket_name: str
    alert_trigger_topic_arn: str
    telegram_secret_arn: str


def load_publisher_runtime_settings(
    environment: Mapping[str, str] | None = None,
) -> PublisherRuntimeSettings:
    """Load only validated, non-secret inputs required before story processing."""
    values = environment if environment is not None else os.environ
    registry_path = Path(_required(values, "OFFICE_REGISTRY_PATH"))
    config_path = Path(_required(values, "ENVIRONMENT_CONFIG_PATH"))
    try:
        registry = OfficeRegistry.model_validate_json(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("OFFICE_REGISTRY_PATH must contain a valid office registry") from error
    try:
        config = load_environment_config(config_path)
    except (OSError, ValueError) as error:
        raise RuntimeError(
            "ENVIRONMENT_CONFIG_PATH must contain valid environment config"
        ) from error

    active_registry_ids = tuple(office.office_id for office in registry.offices if office.active)
    if active_registry_ids != config.active_office_ids:
        raise RuntimeError("packaged registry active offices must match environment configuration")
    if any(
        office.telegram_channel_id != config.office_channels.get(office.office_id)
        for office in registry.offices
        if office.active
    ):
        raise RuntimeError("packaged registry channels must match environment configuration")
    return PublisherRuntimeSettings(
        registry=registry,
        environment=config,
        history_table_name=_required(values, "HISTORY_TABLE_NAME"),
        image_bucket_name=_required(values, "IMAGE_BUCKET_NAME"),
        alert_trigger_topic_arn=_required(values, "ALERT_TRIGGER_TOPIC_ARN"),
        telegram_secret_arn=_required(values, "TELEGRAM_SECRET_ARN"),
    )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
