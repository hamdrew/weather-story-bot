from __future__ import annotations

import json

import pytest

from weather_story_bot.config import ConfigError, OfficeConfig, Settings, parse_offices

ENV = {
    "OFFICES_JSON": json.dumps({"MKX": {"chat_id": "-1001", "name": "Milwaukee/Sullivan"}}),
    "STATE_TABLE": "table",
    "ARCHIVE_BUCKET": "bucket",
    "TELEGRAM_TOKEN_PARAM": "/weather-story-bot/telegram-token",
    "NWS_USER_AGENT": "ua",
}


def test_from_env() -> None:
    settings = Settings.from_env(ENV)
    assert settings.offices == (OfficeConfig("MKX", "-1001", "Milwaukee/Sullivan"),)
    assert settings.state_table == "table"


def test_missing_variable() -> None:
    with pytest.raises(ConfigError, match="ARCHIVE_BUCKET"):
        Settings.from_env({**ENV, "ARCHIVE_BUCKET": " "})


def test_numeric_chat_id_and_default_name() -> None:
    assert parse_offices('{"GRB": {"chat_id": -1002}}') == (OfficeConfig("GRB", "-1002", "GRB"),)


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        "{}",
        '{"mkx": {"chat_id": "1"}}',
        '{"../X": {"chat_id": "1"}}',
        '{"MKX": {}}',
    ],
)
def test_invalid_offices(raw: str) -> None:
    with pytest.raises(ConfigError):
        parse_offices(raw)
