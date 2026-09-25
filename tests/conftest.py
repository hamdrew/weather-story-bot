from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import boto3
import pytest
from moto import mock_aws

from weather_story_bot.models import Story

if TYPE_CHECKING:
    from types_boto3_dynamodb import DynamoDBClient
    from types_boto3_s3 import S3Client

FIXTURES = Path(__file__).parent / "fixtures"
TABLE_NAME = "weather-story-bot-state"
MVP_TABLE_NAME = "weather-story-bot-posted"
BUCKET_NAME = "weather-story-bot-archive-test"


@pytest.fixture(autouse=True)
def aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake AWS credentials, and no Telegram creds, so a dev's real ones can never be used."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)


@pytest.fixture
def mkx_payload() -> dict[str, Any]:
    return json.loads((FIXTURES / "mkx_weatherstories.json").read_text())


@pytest.fixture
def mkx_stories(mkx_payload: dict[str, Any]) -> list[Story]:
    return [Story.from_api(item) for item in mkx_payload["stories"]]


def make_story(**overrides: Any) -> Story:
    data = {
        "officeId": "MKX",
        "startTime": "2026-09-12T19:24:00+00:00",
        "endTime": "2026-09-13T19:24:00+00:00",
        "updateTime": "2026-09-12T19:30:25+00:00",
        "title": "Storms Monday Night",
        "description": "Showers and storms expected.",
        "altText": "Graphic of storm timing.",
        "priority": False,
        "order": 1,
        "download": "https://api.weather.gov/offices/MKX/weatherstories/download/aaaa-1111",
    }
    data.update(overrides)
    return Story.from_api(data)


@pytest.fixture
def aws() -> Iterator[None]:
    with mock_aws():
        yield


@pytest.fixture
def dynamodb(aws: None) -> DynamoDBClient:
    """The state table the Lambda uses (PK/SK keys, backend/dynamodb-schema)."""
    client = boto3.client("dynamodb")
    _create_table(client, TABLE_NAME, "PK", "SK")
    return client


@pytest.fixture
def mvp_table(dynamodb: DynamoDBClient) -> DynamoDBClient:
    """The MVP table (`office_id` / `image_id`), which only the migration scripts use."""
    _create_table(dynamodb, MVP_TABLE_NAME, "office_id", "image_id")
    return dynamodb


def _create_table(client: DynamoDBClient, name: str, hash_key: str, range_key: str) -> None:
    client.create_table(
        TableName=name,
        KeySchema=[
            {"AttributeName": hash_key, "KeyType": "HASH"},
            {"AttributeName": range_key, "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": hash_key, "AttributeType": "S"},
            {"AttributeName": range_key, "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def s3(aws: None) -> S3Client:
    client = boto3.client("s3")
    client.create_bucket(
        Bucket=BUCKET_NAME,
        CreateBucketConfiguration={"LocationConstraint": "us-east-2"},
    )
    return client
