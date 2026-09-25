"""One-off migration of story records to the state table's PK/SK keys (2026-09-24).

Before: the MVP table `weather-story-bot-posted` holds one item per story, keyed by
`office_id` (partition) and `image_id = story#<story_key>` (sort).

After: the state table `weather-story-bot-state` holds the same records under
`PK = OFFICE#<id>`, `SK = STORY#<start_utc_iso>#<story_key>` (backend/dynamodb-schema), with
`schema_version`, `story_key` and every other attribute copied verbatim. `telegram_message_id`,
`posted_at`, `fingerprint` and `archive_prefix` come across unchanged, so after the flip the
Lambda skips live stories instead of reposting them, and deletes the right message on an update.

1. Checks every old item before writing anything: each is a `story#` item with the attributes
   the Lambda reads, and its sort key matches `story_key` recomputed from its stored title and
   start time. A mismatch means the flipped Lambda would never find the record and would repost.
2. Copies each item to the state table. Items already there are kept, never overwritten: after
   the flip the Lambda writes them, and the old table is stale.
3. With --delete-old, deletes each old item whose copy exists in the state table. Items stay
   recoverable for 35 days through PITR. Only run this once the flipped Lambda has soaked: the
   old table is the rollback.

Prints the plan and changes nothing unless --apply is given. Every step is idempotent.

Pause the schedule first, so no run writes the old table between the copy and the deploy that
flips STATE_TABLE (Phase 1.2 deploy gate 3; the pause command is in the 2026-09-15 spec's
Verification section):
    uv run python scripts/migrate_table_keys.py            # review the plan
    uv run python scripts/migrate_table_keys.py --apply
    make build && make deploy                               # flips STATE_TABLE, re-enables schedule

Credentials come from the usual boto3 chain (`aws login` profiles work through `boto3[crt]`).
Writes may need the MFA admin profile, which prompts for a code: AWS_PROFILE=<profile> ...
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from weather_story_bot.config import is_valid_office_id
from weather_story_bot.models import parse_time
from weather_story_bot.state import SCHEMA_VERSION, office_pk, story_key_for, story_sk

if TYPE_CHECKING:
    from types_boto3_dynamodb import DynamoDBClient
    from types_boto3_dynamodb.type_defs import AttributeValueTypeDef

DEFAULT_OLD_TABLE = "weather-story-bot-posted"
DEFAULT_NEW_TABLE = "weather-story-bot-state"
OLD_STORY_PREFIX = "story#"
NEW_STORY_PREFIX = "STORY#"
# What PostedStore reads, plus what the new sort key and the key check are built from.
REQUIRED_ATTRIBUTES = (
    "posted_image_id",
    "title",
    "start_time",
    "posted_at",
    "telegram_message_id",
    "archive_prefix",
    "fingerprint",
)


class MigrationError(Exception):
    """The old data doesn't look like the migration expects; nothing was written."""


@dataclass(frozen=True, slots=True)
class Copy:
    """One old item and the state-table item it becomes."""

    old_key: dict[str, AttributeValueTypeDef]
    new_item: dict[str, AttributeValueTypeDef]

    @property
    def pk(self) -> str:
        return self.new_item["PK"]["S"]

    @property
    def sk(self) -> str:
        return self.new_item["SK"]["S"]

    @property
    def title(self) -> str:
        return self.new_item["title"]["S"]


@dataclass(frozen=True, slots=True)
class Plan:
    old_count: int
    copies: tuple[Copy, ...]
    already_copied: tuple[Copy, ...]


def convert(item: dict[str, Any]) -> Copy:
    """Build the state-table item for one old item, or raise if it isn't what we expect."""
    office_id = item.get("office_id", {}).get("S", "")
    sort_key = item.get("image_id", {}).get("S", "")
    if not sort_key.startswith(OLD_STORY_PREFIX):
        raise MigrationError(f"Unexpected item {office_id}/{sort_key}: not a story# record")
    if not is_valid_office_id(office_id):
        raise MigrationError(f"Item {sort_key} has an invalid office_id {office_id!r}")
    missing = [name for name in REQUIRED_ATTRIBUTES if name not in item]
    if missing:
        raise MigrationError(f"Item {office_id}/{sort_key} is missing {', '.join(missing)}")

    key = sort_key.removeprefix(OLD_STORY_PREFIX)
    start_time = parse_time(item["start_time"]["S"])
    if story_key_for(item["title"]["S"], start_time) != key:
        raise MigrationError(
            f"Item {office_id}/{sort_key} doesn't match the story_key of its own title and"
            " start_time; the migrated record would never be found"
        )

    attributes = {name: value for name, value in item.items() if name != "image_id"}
    new_item: dict[str, AttributeValueTypeDef] = {
        **attributes,
        "PK": {"S": office_pk(office_id)},
        "SK": {"S": story_sk(start_time, key)},
        "schema_version": {"N": str(SCHEMA_VERSION)},
        "story_key": {"S": key},
    }
    old_key = {"office_id": item["office_id"], "image_id": item["image_id"]}
    return Copy(old_key=old_key, new_item=new_item)


def build_plan(dynamodb: DynamoDBClient, old_table: str, new_table: str) -> Plan:
    """Read both tables and check every old item before writing anything."""
    old_items = _scan(dynamodb, old_table)
    if not old_items:
        raise MigrationError(f"{old_table} is empty; check the table name and region")
    copies = [convert(item) for item in old_items]
    existing = {
        (item["PK"]["S"], item["SK"]["S"])
        for item in _scan(dynamodb, new_table)
        if item["SK"]["S"].startswith(NEW_STORY_PREFIX)
    }
    return Plan(
        old_count=len(old_items),
        copies=tuple(copy for copy in copies if (copy.pk, copy.sk) not in existing),
        already_copied=tuple(copy for copy in copies if (copy.pk, copy.sk) in existing),
    )


def migrate(
    dynamodb: DynamoDBClient,
    old_table: str,
    new_table: str,
    *,
    apply: bool,
    delete_old: bool,
    out: Callable[[str], None] = print,
) -> Plan:
    plan = build_plan(dynamodb, old_table, new_table)
    mode = "Applying" if apply else "Dry run, nothing will change"
    out(f"{mode}: {old_table} -> {new_table}")

    out(
        f"\n{plan.old_count} story# items: {len(plan.copies)} to copy,"
        f" {len(plan.already_copied)} already in {new_table}"
    )
    for copy in sorted(plan.copies, key=lambda c: (c.pk, c.sk)):
        out(f"  copy     {copy.pk} {_short(copy.sk)} {copy.title!r}")
    for copy in sorted(plan.already_copied, key=lambda c: (c.pk, c.sk)):
        out(f"  keep     {copy.pk} {_short(copy.sk)} already copied")
    if apply:
        for copy in plan.copies:
            # The condition makes a copy never overwrite a record the flipped Lambda wrote.
            dynamodb.put_item(
                TableName=new_table,
                Item=copy.new_item,
                ConditionExpression="attribute_not_exists(PK)",
            )

    if not delete_old:
        out(f"\nOld items kept: {plan.old_count} in {old_table}")
        return plan
    # Only items whose copy existed when the plan was read, so a dry run's count is exact.
    out(f"\nDelete old: {len(plan.already_copied)} items copied to {new_table}")
    if plan.copies:
        out(f"  {len(plan.copies)} items not copied yet are kept; rerun after --apply")
    if apply:
        for copy in plan.already_copied:
            dynamodb.delete_item(TableName=old_table, Key=copy.old_key)
    return plan


def _scan(dynamodb: DynamoDBClient, table: str) -> list[dict[str, Any]]:
    return [
        item
        for page in dynamodb.get_paginator("scan").paginate(TableName=table, ConsistentRead=True)
        for item in page["Items"]
    ]


def _short(sort_key: str) -> str:
    """`STORY#<start>#<first 12 of story_key>…`, enough to tell stories apart."""
    prefix, _, key = sort_key.rpartition("#")
    return f"{prefix}#{key[:12]}…"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Copy story records to the state table's keys.")
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    parser.add_argument(
        "--delete-old", action="store_true", help="also delete old items already copied"
    )
    parser.add_argument("--old-table", default=DEFAULT_OLD_TABLE)
    parser.add_argument("--new-table", default=DEFAULT_NEW_TABLE)
    parser.add_argument("--region", default="us-east-2")
    args = parser.parse_args(argv)

    import boto3  # Dev-only dependency.

    session = boto3.Session(region_name=args.region)
    migrate(
        session.client("dynamodb"),
        args.old_table,
        args.new_table,
        apply=args.apply,
        delete_old=args.delete_old,
    )


if __name__ == "__main__":
    main()
