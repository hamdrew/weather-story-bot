from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from scripts.migrate_table_keys import MigrationError, Plan, migrate
from tests.conftest import MVP_TABLE_NAME, TABLE_NAME, make_story
from weather_story_bot.models import Story
from weather_story_bot.state import PostedRecord, PostedStore, description_sha256, story_key

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


def put_mvp_record(
    dynamodb: DynamoDBClient, story: Story, message_id: int, fingerprint: str, **extra: str
) -> None:
    """A `story#` item as the Lambda wrote it to the MVP table."""
    dynamodb.put_item(
        TableName=MVP_TABLE_NAME,
        Item={
            "office_id": {"S": story.office_id},
            "image_id": {"S": f"story#{story_key(story)}"},
            "posted_image_id": {"S": story.image_id},
            "title": {"S": story.title},
            "start_time": {"S": story.start_time.isoformat()},
            "end_time": {"S": story.end_time.isoformat()},
            "update_time": {"S": story.update_time.isoformat()},
            "posted_at": {"S": "2026-09-12T20:00:00+00:00"},
            "telegram_message_id": {"N": str(message_id)},
            "archive_prefix": {"S": f"stories/MKX/{fingerprint}"},
            "fingerprint": {"S": fingerprint},
            **{name: {"S": value} for name, value in extra.items()},
        },
    )


@pytest.fixture
def seeded(mvp_table: DynamoDBClient) -> None:
    """Two story# records; one predates the stored content hashes."""
    put_mvp_record(
        mvp_table,
        STORMS,
        9,
        "fp-storms",
        image_sha256="img-storms",
        description_sha256=description_sha256(STORMS),
    )
    put_mvp_record(mvp_table, HEAT, 11, "fp-heat")


def run(dynamodb: DynamoDBClient, **flags: bool) -> tuple[list[str], Plan]:
    lines: list[str] = []
    plan = migrate(
        dynamodb,
        MVP_TABLE_NAME,
        TABLE_NAME,
        apply=flags.get("apply", False),
        delete_old=flags.get("delete_old", False),
        out=lines.append,
    )
    return lines, plan


def items(dynamodb: DynamoDBClient, table: str) -> list[dict[str, Any]]:
    return dynamodb.scan(TableName=table)["Items"]


def snapshot(dynamodb: DynamoDBClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return items(dynamodb, MVP_TABLE_NAME), items(dynamodb, TABLE_NAME)


def new_item(dynamodb: DynamoDBClient, sk: str) -> dict[str, Any]:
    return dynamodb.get_item(
        TableName=TABLE_NAME, Key={"PK": {"S": "OFFICE#MKX"}, "SK": {"S": sk}}
    )["Item"]


@pytest.mark.usefixtures("seeded")
def test_dry_run_plans_every_copy_and_changes_nothing(mvp_table: DynamoDBClient) -> None:
    before = snapshot(mvp_table)

    lines, plan = run(mvp_table)

    assert snapshot(mvp_table) == before
    assert len(plan.copies) == 2
    output = "\n".join(lines)
    assert "2 story# items: 2 to copy, 0 already in weather-story-bot-state" in output
    assert "'Heat Index'" in output


@pytest.mark.usefixtures("seeded")
def test_apply_copies_each_record_under_the_new_keys(mvp_table: DynamoDBClient) -> None:
    old = {item["image_id"]["S"]: item for item in items(mvp_table, MVP_TABLE_NAME)}

    run(mvp_table, apply=True)

    storms = new_item(mvp_table, STORMS_SK)
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
    heat = new_item(mvp_table, HEAT_SK)
    assert heat["fingerprint"] == {"S": "fp-heat"}
    assert heat["start_time"] == {"S": "2026-09-12T14:24:00-05:00"}
    assert "image_sha256" not in heat
    assert len(items(mvp_table, TABLE_NAME)) == 2
    assert len(items(mvp_table, MVP_TABLE_NAME)) == 2


@pytest.mark.usefixtures("seeded")
def test_the_lambda_finds_every_migrated_record(mvp_table: DynamoDBClient) -> None:
    run(mvp_table, apply=True)

    store = PostedStore(mvp_table, TABLE_NAME)
    # Found, with the same message and fingerprint, so the first run after the flip skips both
    # live stories instead of reposting them.
    assert store.find_story(STORMS) == PostedRecord(
        image_id=STORMS.image_id,
        telegram_message_id=9,
        archive_prefix="stories/MKX/fp-storms",
        fingerprint="fp-storms",
        image_sha256="img-storms",
        description_sha256=description_sha256(STORMS),
    )
    heat = store.find_story(HEAT)
    assert heat is not None
    assert (heat.telegram_message_id, heat.fingerprint, heat.image_sha256) == (11, "fp-heat", None)


@pytest.mark.usefixtures("seeded")
def test_migrated_items_match_what_the_lambda_writes(mvp_table: DynamoDBClient) -> None:
    run(mvp_table, apply=True)
    migrated = new_item(mvp_table, STORMS_SK)

    PostedStore(mvp_table, TABLE_NAME).record_posted(
        STORMS, 9, "stories/MKX/fp-storms", "fp-storms", image_sha256="img-storms"
    )

    # Same attributes either way, so an S3 export sees one shape, not two.
    assert set(new_item(mvp_table, STORMS_SK)) == set(migrated)


@pytest.mark.usefixtures("seeded")
def test_rerun_keeps_records_already_in_the_new_table(mvp_table: DynamoDBClient) -> None:
    run(mvp_table, apply=True)
    # After the flip the Lambda updates the new table; the old table is stale.
    mvp_table.update_item(
        TableName=TABLE_NAME,
        Key={"PK": {"S": "OFFICE#MKX"}, "SK": {"S": STORMS_SK}},
        UpdateExpression="SET telegram_message_id = :id",
        ExpressionAttributeValues={":id": {"N": "99"}},
    )
    before = snapshot(mvp_table)

    lines, _ = run(mvp_table, apply=True)

    assert snapshot(mvp_table) == before
    assert new_item(mvp_table, STORMS_SK)["telegram_message_id"] == {"N": "99"}
    assert "2 story# items: 0 to copy, 2 already in weather-story-bot-state" in "\n".join(lines)


@pytest.mark.usefixtures("seeded")
def test_delete_old_removes_only_items_already_copied(mvp_table: DynamoDBClient) -> None:
    mvp_table.put_item(
        TableName=TABLE_NAME,
        Item={"PK": {"S": "OFFICE#MKX"}, "SK": {"S": STORMS_SK}, "schema_version": {"N": "1"}},
    )

    lines, _ = run(mvp_table, apply=True, delete_old=True)

    # HEAT is copied by this run but only deleted by the next, once its copy was seen.
    remaining = {item["image_id"]["S"] for item in items(mvp_table, MVP_TABLE_NAME)}
    assert remaining == {f"story#{story_key(HEAT)}"}
    assert "1 items not copied yet are kept" in "\n".join(lines)

    run(mvp_table, apply=True, delete_old=True)

    assert items(mvp_table, MVP_TABLE_NAME) == []
    assert len(items(mvp_table, TABLE_NAME)) == 2


@pytest.mark.usefixtures("seeded")
def test_delete_old_without_apply_changes_nothing(mvp_table: DynamoDBClient) -> None:
    run(mvp_table, apply=True)
    before = snapshot(mvp_table)

    lines, _ = run(mvp_table, delete_old=True)

    assert snapshot(mvp_table) == before
    assert "Delete old: 2 items copied to weather-story-bot-state" in "\n".join(lines)


def test_empty_old_table_fails(mvp_table: DynamoDBClient) -> None:
    with pytest.raises(MigrationError, match="is empty"):
        run(mvp_table, apply=True)


def put_old(dynamodb: DynamoDBClient, sort_key: str, **attributes: str) -> None:
    dynamodb.put_item(
        TableName=MVP_TABLE_NAME,
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
    mvp_table: DynamoDBClient, sort_key: str, attributes: dict[str, str], error: str
) -> None:
    put_old(mvp_table, sort_key, **attributes)
    before = snapshot(mvp_table)

    with pytest.raises(MigrationError, match=error):
        run(mvp_table, apply=True)

    assert snapshot(mvp_table) == before


@pytest.mark.usefixtures("seeded")
def test_sort_key_not_matching_title_and_start_fails_before_writing(
    mvp_table: DynamoDBClient,
) -> None:
    mvp_table.update_item(
        TableName=MVP_TABLE_NAME,
        Key={"office_id": {"S": "MKX"}, "image_id": {"S": f"story#{story_key(HEAT)}"}},
        UpdateExpression="SET title = :title",
        ExpressionAttributeValues={":title": {"S": "Heat Index Tomorrow"}},
    )
    before = snapshot(mvp_table)

    with pytest.raises(MigrationError, match="would never be found"):
        run(mvp_table, apply=True)

    assert snapshot(mvp_table) == before
