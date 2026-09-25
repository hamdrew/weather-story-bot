from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from scripts.migrate_table_keys import MigrationError, Plan, migrate
from tests.conftest import STATE_TABLE_NAME, TABLE_NAME, make_story
from weather_story_bot.state import PostedStore, story_key

if TYPE_CHECKING:
    from types_boto3_dynamodb import DynamoDBClient

STORMS = make_story()
# Stored with its original offset; the new sort key must still use the UTC start.
HEAT = make_story(
    title="Heat Index",
    startTime="2026-09-12T14:24:00-05:00",
    download="https://api.weather.gov/offices/MKX/weatherstories/download/dddd-4444",
)
STORMS_SK = f"STORY#2026-09-12T19:24:00+00:00#{story_key(STORMS)}"
HEAT_SK = f"STORY#2026-09-12T19:24:00+00:00#{story_key(HEAT)}"


@pytest.fixture
def seeded(state_table: DynamoDBClient) -> None:
    """Two story# records as the Lambda writes them; one predates the stored image hash."""
    store = PostedStore(state_table, TABLE_NAME)
    store.record_posted(
        STORMS, 9, "stories/MKX/storms/fp-storms", "fp-storms", image_sha256="img-storms"
    )
    store.record_posted(HEAT, 11, "stories/MKX/heat/fp-heat", "fp-heat")


def run(dynamodb: DynamoDBClient, **flags: bool) -> tuple[list[str], Plan]:
    lines: list[str] = []
    plan = migrate(
        dynamodb,
        TABLE_NAME,
        STATE_TABLE_NAME,
        apply=flags.get("apply", False),
        delete_old=flags.get("delete_old", False),
        out=lines.append,
    )
    return lines, plan


def items(dynamodb: DynamoDBClient, table: str) -> list[dict[str, Any]]:
    return dynamodb.scan(TableName=table)["Items"]


def snapshot(dynamodb: DynamoDBClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return items(dynamodb, TABLE_NAME), items(dynamodb, STATE_TABLE_NAME)


def new_item(dynamodb: DynamoDBClient, sk: str) -> dict[str, Any]:
    return dynamodb.get_item(
        TableName=STATE_TABLE_NAME, Key={"PK": {"S": "OFFICE#MKX"}, "SK": {"S": sk}}
    )["Item"]


@pytest.mark.usefixtures("seeded")
def test_dry_run_plans_every_copy_and_changes_nothing(state_table: DynamoDBClient) -> None:
    before = snapshot(state_table)

    lines, plan = run(state_table)

    assert snapshot(state_table) == before
    assert len(plan.copies) == 2
    output = "\n".join(lines)
    assert "2 story# items: 2 to copy, 0 already in weather-story-bot-state" in output
    assert "'Heat Index'" in output


@pytest.mark.usefixtures("seeded")
def test_apply_copies_each_record_under_the_new_keys(state_table: DynamoDBClient) -> None:
    old = {item["image_id"]["S"]: item for item in items(state_table, TABLE_NAME)}

    run(state_table, apply=True)

    storms = new_item(state_table, STORMS_SK)
    # Everything the Lambda reads comes across verbatim, so the live story is skipped, not
    # reposted, after the flip.
    expected = {k: v for k, v in old[f"story#{story_key(STORMS)}"].items() if k != "image_id"}
    assert storms == {
        **expected,
        "PK": {"S": "OFFICE#MKX"},
        "SK": {"S": STORMS_SK},
        "schema_version": {"N": "1"},
        "story_key": {"S": story_key(STORMS)},
    }
    assert storms["telegram_message_id"] == {"N": "9"}
    assert storms["image_sha256"] == {"S": "img-storms"}
    heat = new_item(state_table, HEAT_SK)
    assert heat["fingerprint"] == {"S": "fp-heat"}
    assert heat["start_time"] == {"S": "2026-09-12T14:24:00-05:00"}
    assert "image_sha256" not in heat
    assert len(items(state_table, STATE_TABLE_NAME)) == 2
    assert len(items(state_table, TABLE_NAME)) == 2


@pytest.mark.usefixtures("seeded")
def test_rerun_keeps_records_already_in_the_new_table(state_table: DynamoDBClient) -> None:
    run(state_table, apply=True)
    # After the flip the Lambda updates the new table; the old table is stale.
    state_table.update_item(
        TableName=STATE_TABLE_NAME,
        Key={"PK": {"S": "OFFICE#MKX"}, "SK": {"S": STORMS_SK}},
        UpdateExpression="SET telegram_message_id = :id",
        ExpressionAttributeValues={":id": {"N": "99"}},
    )
    before = snapshot(state_table)

    lines, _ = run(state_table, apply=True)

    assert snapshot(state_table) == before
    assert new_item(state_table, STORMS_SK)["telegram_message_id"] == {"N": "99"}
    assert "2 story# items: 0 to copy, 2 already in weather-story-bot-state" in "\n".join(lines)


@pytest.mark.usefixtures("seeded")
def test_delete_old_removes_only_items_already_copied(state_table: DynamoDBClient) -> None:
    state_table.put_item(
        TableName=STATE_TABLE_NAME,
        Item={"PK": {"S": "OFFICE#MKX"}, "SK": {"S": STORMS_SK}, "schema_version": {"N": "1"}},
    )

    lines, _ = run(state_table, apply=True, delete_old=True)

    # HEAT is copied by this run but only deleted by the next, once its copy was seen.
    remaining = {item["image_id"]["S"] for item in items(state_table, TABLE_NAME)}
    assert remaining == {f"story#{story_key(HEAT)}"}
    assert "1 items not copied yet are kept" in "\n".join(lines)

    run(state_table, apply=True, delete_old=True)

    assert items(state_table, TABLE_NAME) == []
    assert len(items(state_table, STATE_TABLE_NAME)) == 2


@pytest.mark.usefixtures("seeded")
def test_delete_old_without_apply_changes_nothing(state_table: DynamoDBClient) -> None:
    run(state_table, apply=True)
    before = snapshot(state_table)

    lines, _ = run(state_table, delete_old=True)

    assert snapshot(state_table) == before
    assert "Delete old: 2 items copied to weather-story-bot-state" in "\n".join(lines)


def test_empty_old_table_fails(state_table: DynamoDBClient) -> None:
    with pytest.raises(MigrationError, match="is empty"):
        run(state_table, apply=True)


def put_old(dynamodb: DynamoDBClient, sort_key: str, **attributes: str) -> None:
    dynamodb.put_item(
        TableName=TABLE_NAME,
        Item={
            "office_id": {"S": attributes.pop("office_id", "MKX")},
            "image_id": {"S": sort_key},
            **{name: {"S": value} for name, value in attributes.items()},
        },
    )


@pytest.mark.usefixtures("seeded")
@pytest.mark.parametrize(
    ("sort_key", "attributes", "error"),
    [
        pytest.param("content#abc", {}, "not a story# record", id="legacy-item"),
        pytest.param(
            f"story#{story_key(STORMS)}", {"office_id": "../x"}, "invalid office_id", id="office"
        ),
        pytest.param("story#abc", {"title": "Storms"}, "is missing .*start_time", id="missing"),
    ],
)
def test_unexpected_items_fail_before_writing(
    state_table: DynamoDBClient, sort_key: str, attributes: dict[str, str], error: str
) -> None:
    put_old(state_table, sort_key, **attributes)
    before = snapshot(state_table)

    with pytest.raises(MigrationError, match=error):
        run(state_table, apply=True)

    assert snapshot(state_table) == before


@pytest.mark.usefixtures("seeded")
def test_sort_key_not_matching_title_and_start_fails_before_writing(
    state_table: DynamoDBClient,
) -> None:
    state_table.update_item(
        TableName=TABLE_NAME,
        Key={"office_id": {"S": "MKX"}, "image_id": {"S": f"story#{story_key(HEAT)}"}},
        UpdateExpression="SET title = :title",
        ExpressionAttributeValues={":title": {"S": "Heat Index Tomorrow"}},
    )
    before = snapshot(state_table)

    with pytest.raises(MigrationError, match="would never be found"):
        run(state_table, apply=True)

    assert snapshot(state_table) == before
