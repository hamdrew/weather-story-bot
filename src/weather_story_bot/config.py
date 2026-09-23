"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

_OFFICE_ID = re.compile(r"^[A-Z]{3}$")


class ConfigError(Exception):
    """Required configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class OfficeConfig:
    office_id: str
    chat_id: str
    name: str


@dataclass(frozen=True, slots=True)
class Settings:
    offices: tuple[OfficeConfig, ...]
    state_table: str
    archive_bucket: str
    telegram_token_param: str
    nws_user_agent: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Settings:
        def require(name: str) -> str:
            value = env.get(name, "").strip()
            if not value:
                raise ConfigError(f"Environment variable {name} is required")
            return value

        return cls(
            offices=parse_offices(require("OFFICES_JSON")),
            state_table=require("STATE_TABLE"),
            archive_bucket=require("ARCHIVE_BUCKET"),
            telegram_token_param=require("TELEGRAM_TOKEN_PARAM"),
            nws_user_agent=require("NWS_USER_AGENT"),
        )


def is_valid_office_id(value: str) -> bool:
    """A real NWS office id: exactly three uppercase letters, e.g. `MKX`."""
    return bool(_OFFICE_ID.match(value))


def parse_offices(raw: str) -> tuple[OfficeConfig, ...]:
    """Parse `{"MKX": {"chat_id": "-100…", "name": "Milwaukee/Sullivan"}, ...}`."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"OFFICES_JSON is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise ConfigError("OFFICES_JSON must be a non-empty object keyed by office id")

    offices = []
    for office_id, entry in data.items():
        if not is_valid_office_id(office_id):
            raise ConfigError(f"Invalid office id {office_id!r}: expected e.g. 'MKX'")
        if not isinstance(entry, dict) or not str(entry.get("chat_id", "")).strip():
            raise ConfigError(f"Office {office_id} needs a chat_id")
        offices.append(
            OfficeConfig(
                office_id=office_id,
                chat_id=str(entry["chat_id"]).strip(),
                name=str(entry.get("name") or office_id),
            )
        )
    return tuple(offices)
