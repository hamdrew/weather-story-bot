"""Versioned, validated configuration inputs for the Weather Story service."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from timezonefinder import TimezoneFinder

Environment = Literal["dev", "staging", "prod"]
TelegramMode = Literal["mock", "live"]

OFFICE_ID_PATTERN = re.compile(r"^[A-Z]{3}$")
MOCK_IDENTIFIER_PREFIX = "mock:"
DEFAULT_NWS_IMAGE_HOST_ALLOWLIST = frozenset({"weather.gov", "*.weather.gov"})
TIMEZONE_FINDER = TimezoneFinder()


class ConfigurationError(ValueError):
    """Raised when a versioned service configuration is inconsistent."""


class NWSOfficeSeedSet(BaseModel):
    """The reviewable, versioned source list for future office enrichment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    source: HttpUrl
    office_ids: tuple[Annotated[str, Field(pattern=r"^[A-Z]{3}$")], ...]

    @model_validator(mode="after")
    def has_unique_ids(self) -> NWSOfficeSeedSet:
        if len(self.office_ids) != len(set(self.office_ids)):
            raise ValueError("office_ids must be unique")
        return self


class PostalAddress(BaseModel):
    """Postal fields returned by the NWS office endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    street_address: str = Field(min_length=1, max_length=256)
    locality: str = Field(min_length=1, max_length=128)
    region: str = Field(min_length=1, max_length=64)
    postal_code: str = Field(min_length=1, max_length=32)


class OfficeCoordinates(BaseModel):
    """Geocoded office coordinates retained for timezone derivation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]


class OfficeRegistryRecord(BaseModel):
    """A fully enriched office record; no record is publishable unless valid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    office_id: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    weather_stories_url: HttpUrl
    display_name: str = Field(min_length=1, max_length=256)
    address: PostalAddress
    coordinates: OfficeCoordinates
    timezone: str = Field(min_length=1)
    telegram_channel_id: str | None = None
    active: bool = False
    telephone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=254)
    office_home_url: HttpUrl | None = None
    region_name: str | None = Field(default=None, max_length=256)
    region_home_url: HttpUrl | None = None

    @field_validator("weather_stories_url", "office_home_url", "region_home_url")
    @classmethod
    def requires_https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and value.scheme != "https":
            raise ValueError("URL must use HTTPS")
        return value

    @field_validator("timezone")
    @classmethod
    def requires_iana_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        return value

    @field_validator("telegram_channel_id")
    @classmethod
    def normalizes_channel(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("telegram_channel_id cannot be blank")
        return value

    @model_validator(mode="after")
    def active_record_has_channel(self) -> OfficeRegistryRecord:
        if str(self.weather_stories_url) != weather_stories_url(self.office_id):
            raise ValueError(
                "weather_stories_url must be the canonical NWS Weather Stories endpoint"
            )
        if self.timezone != derive_timezone(self.coordinates):
            raise ValueError("timezone must be derived from the geocoded office coordinates")
        if self.active and self.telegram_channel_id is None:
            raise ValueError("an active office requires a telegram_channel_id")
        return self


class OfficeRegistry(BaseModel):
    """Validated registry that permits inactive offices without destinations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    offices: tuple[OfficeRegistryRecord, ...]

    @model_validator(mode="after")
    def has_unique_ids_and_active_channels(self) -> OfficeRegistry:
        office_ids = [office.office_id for office in self.offices]
        if len(office_ids) != len(set(office_ids)):
            raise ValueError("office_ids must be unique")
        active_channels = [office.telegram_channel_id for office in self.offices if office.active]
        if len(active_channels) != len(set(active_channels)):
            raise ValueError("active office telegram_channel_ids must be unique")
        return self


class EnvironmentConfig(BaseModel):
    """Non-secret, environment-specific Telegram and scheduling configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    environment: Environment
    telegram_mode: TelegramMode
    nws_image_host_allowlist: tuple[str, ...]
    active_office_ids: tuple[Annotated[str, Field(pattern=r"^[A-Z]{3}$")], ...]
    office_channels: Mapping[Annotated[str, Field(pattern=r"^[A-Z]{3}$")], str]
    alert_recipient: str = Field(min_length=1)

    @field_validator("office_channels", "alert_recipient")
    @classmethod
    def strips_destination_values(cls, value: Mapping[str, str] | str) -> Mapping[str, str] | str:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("destination cannot be blank")
            return value
        cleaned = {office_id: channel.strip() for office_id, channel in value.items()}
        if any(not channel for channel in cleaned.values()):
            raise ValueError("office channel cannot be blank")
        return MappingProxyType(cleaned)

    @model_validator(mode="after")
    def has_valid_environment_destinations(self) -> EnvironmentConfig:
        if set(self.nws_image_host_allowlist) != DEFAULT_NWS_IMAGE_HOST_ALLOWLIST:
            raise ValueError("nws_image_host_allowlist must contain weather.gov and *.weather.gov")
        active_ids = self.active_office_ids
        if len(active_ids) != len(set(active_ids)):
            raise ValueError("active_office_ids must be unique")
        if set(self.office_channels) != set(active_ids):
            raise ValueError("office_channels must contain exactly the active office IDs")
        channels = list(self.office_channels.values())
        if len(channels) != len(set(channels)):
            raise ValueError("active office channels must be unique")
        destinations = [*channels, self.alert_recipient]
        has_mock_destination = any(
            value.startswith(MOCK_IDENTIFIER_PREFIX) for value in destinations
        )
        if self.environment == "dev":
            if self.telegram_mode != "mock" or not has_mock_destination:
                raise ValueError("dev must use mock Telegram destinations")
            if not all(value.startswith(MOCK_IDENTIFIER_PREFIX) for value in destinations):
                raise ValueError("dev must use mock Telegram destinations")
        elif self.telegram_mode != "live" or has_mock_destination:
            raise ValueError("staging and prod must use live non-mock Telegram destinations")
        if self.alert_recipient in channels:
            raise ValueError("alert_recipient must differ from public office channels")
        return self


class OperationsConfig(BaseModel):
    """Non-secret trust boundaries for the two protected operation entry points."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: Environment
    account_id: str = Field(pattern=r"^[0-9]{12}$")
    region: Literal["us-east-2"] = "us-east-2"
    office_function_arn: str
    alert_function_arn: str
    trigger_topic_arn: str
    fallback_topic_arn: str
    alarm_names: tuple[Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,127}$")], ...]
    log_level: Literal["INFO", "WARNING", "ERROR", "DEBUG"] = "INFO"

    @model_validator(mode="after")
    def scopes_resources(self) -> OperationsConfig:
        prefix = f"weather-story-{self.environment}-"
        for value, service, kind in (
            (self.office_function_arn, "lambda", "function:"),
            (self.alert_function_arn, "lambda", "function:"),
            (self.trigger_topic_arn, "sns", ""),
            (self.fallback_topic_arn, "sns", ""),
        ):
            expected = f"arn:aws:{service}:{self.region}:{self.account_id}:{kind}{prefix}"
            if not value.startswith(expected) or not re.fullmatch(
                r"[a-z0-9-]+", value[len(expected) :]
            ):
                raise ValueError("operation resource is outside the configured scope")
        if self.office_function_arn == self.alert_function_arn:
            raise ValueError("operation functions must be distinct")
        if self.trigger_topic_arn == self.fallback_topic_arn:
            raise ValueError("trigger and fallback topics must be distinct")
        if not 1 <= len(self.alarm_names) <= 20 or len(set(self.alarm_names)) != len(
            self.alarm_names
        ):
            raise ValueError("one to twenty unique alarms are required")
        if any(not name.startswith(prefix) for name in self.alarm_names):
            raise ValueError("alarm is outside the configured environment")
        if self.environment == "prod" and self.log_level == "DEBUG":
            raise ValueError("production DEBUG is prohibited")
        return self


def derive_timezone(coordinates: OfficeCoordinates) -> str:
    """Derive a validated IANA timezone from NWS-geocoded office coordinates."""
    timezone = TIMEZONE_FINDER.timezone_at(lat=coordinates.latitude, lng=coordinates.longitude)
    if timezone is None:
        raise ConfigurationError("no IANA timezone found for office coordinates")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ConfigurationError("timezone lookup returned an invalid IANA timezone") from error
    return timezone


def load_seed_set(path: Path) -> NWSOfficeSeedSet:
    """Load the immutable NWS office-ID seed set."""
    return NWSOfficeSeedSet.model_validate_json(path.read_text(encoding="utf-8"))


def load_environment_config(path: Path) -> EnvironmentConfig:
    """Load one non-secret environment configuration document."""
    return EnvironmentConfig.model_validate_json(path.read_text(encoding="utf-8"))


def validate_environment_isolation(configs: Iterable[EnvironmentConfig]) -> None:
    """Ensure separately deployed environments never share Telegram destinations."""
    config_list = list(configs)
    environments = [config.environment for config in config_list]
    if len(environments) != len(set(environments)):
        raise ConfigurationError("configs must contain each environment exactly once")
    by_environment = {config.environment: config for config in config_list}
    if set(by_environment) != {"dev", "staging", "prod"}:
        raise ConfigurationError("configs must include dev, staging, and prod exactly once")
    live_destinations = {
        config.environment: set(config.office_channels.values()) | {config.alert_recipient}
        for config in by_environment.values()
        if config.telegram_mode == "live"
    }
    if live_destinations["staging"] & live_destinations["prod"]:
        raise ConfigurationError("staging and prod Telegram destinations must be distinct")


def weather_stories_url(office_id: str) -> str:
    """Return the canonical NWS Weather Stories API URL for a seeded office."""
    if not OFFICE_ID_PATTERN.fullmatch(office_id):
        raise ConfigurationError("office_id must be a three-letter uppercase NWS ID")
    return f"https://api.weather.gov/offices/{office_id}/weatherstories"


def validate_telegram_secret(secret_json: str) -> str:
    """Validate the versioned secret shape without retaining or logging the token."""
    try:
        parsed_secret = json.loads(secret_json)
    except json.JSONDecodeError as error:
        raise ConfigurationError("Telegram secret is not valid JSON") from error
    if not isinstance(parsed_secret, dict):
        raise ConfigurationError("Telegram secret must be an object")
    secret: dict[str, object] = parsed_secret
    if set(secret) != {"schema_version", "telegram_bot_token"}:
        raise ConfigurationError("Telegram secret has an invalid field set")
    raw_token = secret["telegram_bot_token"]
    if secret.get("schema_version") != 1 or not isinstance(raw_token, str):
        raise ConfigurationError("Telegram secret does not match schema version 1")
    token = raw_token.strip()
    if not token:
        raise ConfigurationError("Telegram secret telegram_bot_token cannot be blank")
    return token
