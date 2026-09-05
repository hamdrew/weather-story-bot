"""Validated non-secret inputs used to compose the publisher Lambda runtime."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from weather_story_bot.config import (
    EnvironmentConfig,
    OfficeRegistry,
    OperationsConfig,
    load_environment_config,
)
from weather_story_bot.operations import (
    AlarmTransition,
    AlertNotifier,
    OfficeInformationCommand,
    OfficeInformationService,
)


class InvocationContext(Protocol):
    """AWS-supplied invocation metadata, never taken from event fields."""

    invoked_function_arn: str
    aws_request_id: str

    def get_remaining_time_in_millis(self) -> int: ...


@dataclass(frozen=True)
class InvocationBudget:
    """Reserve a full bounded adapter attempt and time for a safe terminal observation."""

    context: InvocationContext
    attempt_ms: int = 10_000
    reserve_ms: int = 2_000

    def check(self) -> None:
        if self.context.get_remaining_time_in_millis() < self.attempt_ms + self.reserve_ms:
            raise TimeoutError("insufficient operation budget")


class SNSNotification(BaseModel):
    """The bounded SNS fields needed for authentication of the configured delivery path."""

    model_config = ConfigDict(extra="ignore")
    Type: Literal["Notification"]
    TopicArn: str = Field(max_length=256)
    Message: str = Field(max_length=12_000)
    Timestamp: AwareDatetime


class SNSRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    EventSource: Literal["aws:sns"]
    EventSubscriptionArn: str = Field(max_length=300)
    Sns: SNSNotification


class AlarmNotification(BaseModel):
    """Actual CloudWatch SNS schema; free-form reason/description is intentionally discarded."""

    model_config = ConfigDict(extra="ignore")
    AlarmName: str = Field(pattern=r"^[a-z][a-z0-9-]{0,127}$")
    AlarmArn: str = Field(max_length=300)
    AWSAccountId: str = Field(pattern=r"^[0-9]{12}$")
    NewStateValue: Literal["ALARM"]
    OldStateValue: Literal["OK", "INSUFFICIENT_DATA"]
    StateChangeTime: AwareDatetime


def parse_alarm_notification(
    event: Mapping[str, object], config: OperationsConfig
) -> AlarmTransition:
    """Accept one CloudWatch transition from the exact configured SNS subscription path."""
    if len(json.dumps(event)) > 16_384 or set(event) != {"Records"}:
        raise ValueError("invalid notification envelope")
    records = event["Records"]
    if not isinstance(records, list) or len(records) != 1:
        raise ValueError("exactly one notification is required")
    record = SNSRecord.model_validate(records[0])
    if (
        record.Sns.TopicArn != config.trigger_topic_arn
        or not record.EventSubscriptionArn.startswith(config.trigger_topic_arn + ":")
    ):
        raise ValueError("notification source is not authorized")
    alarm = AlarmNotification.model_validate_json(record.Sns.Message)
    expected = f"arn:aws:cloudwatch:{config.region}:{config.account_id}:alarm:{alarm.AlarmName}"
    if (
        alarm.AlarmArn != expected
        or alarm.AWSAccountId != config.account_id
        or alarm.AlarmName not in config.alarm_names
    ):
        raise ValueError("alarm is not authorized")
    return AlarmTransition(
        source="aws.cloudwatch",
        environment=config.environment,
        alarm_name=alarm.AlarmName,
        state="ALARM",
        summary="CloudWatch alarm entered ALARM",
        event_time=alarm.StateChangeTime,
    )


@dataclass(frozen=True)
class OperationsRuntime:
    """U-01 composition contract; U-03 supplies bounded concrete ports and IAM integration.

    office_authorizer must use trusted invocation context, not command.operator_id. Live direct
    Lambda invocation is authenticated by AWS IAM before execution; U-03 must supply the reviewed
    authorization binding. No default authorizer or live adapter is silently installed.
    """

    config: OperationsConfig
    environment: EnvironmentConfig
    office_service: OfficeInformationService
    notifier: AlertNotifier
    office_authorizer: Callable[[InvocationContext], bool]
    telegram_mode: Literal["mock", "live"]
    office_version: Callable[[str], int | None]

    def __post_init__(self) -> None:
        if self.config.environment != self.environment.environment:
            raise ValueError("runtime environment mismatch")
        if self.telegram_mode != self.environment.telegram_mode:
            raise ValueError("runtime Telegram mode mismatch")

    def authorize_office(
        self, command: OfficeInformationCommand, context: InvocationContext
    ) -> None:
        if (
            context.invoked_function_arn != self.config.office_function_arn
            or command.environment != self.config.environment
            or command.office_id not in self.environment.active_office_ids
            or not self.office_authorizer(context)
        ):
            raise PermissionError("office operation is not authorized")


def load_operations_config(environment: Mapping[str, str] | None = None) -> OperationsConfig:
    """Validate the single non-secret runtime contract through its Pydantic model."""
    values = environment if environment is not None else os.environ
    return OperationsConfig.model_validate_json(_required(values, "OPERATIONS_CONFIG"))


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
