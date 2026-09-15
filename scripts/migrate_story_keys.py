"""One-off migration to story-keyed archive paths and `story#` records (2026-09-15).

Before this change the archive was keyed by image UUID and `updateTime`, and DynamoDB held one
item per image UUID (a post or a `duplicate_of` marker) plus `content#<fingerprint>` items.

1. Copies every old archive pair to `archive_prefix(story, fingerprint)`. Re-issues with
   identical content collapse into one pair, keeping the earliest copy's JSON, as the Lambda would.
2. Writes a `story#` record for each story from its latest post, so the new Lambda skips
   unchanged stories and deletes the right message on an update. Existing `story#` records,
   written by the new Lambda, are left alone.
3. With --delete-old, deletes the old archive pairs (once their copy exists) and every per-image
   and `content#` item. Old files stay recoverable for 35 days through S3 versioning, and items
   through DynamoDB PITR. Only run this once the new Lambda is working: a rollback needs them.

Prints the plan and changes nothing unless --apply is given. Every step is idempotent.

Pause the schedule first, so no run of either Lambda version lands between the backfill and
deploy (see the spec's Verification section for the pause command):
    uv run python scripts/migrate_story_keys.py            # review the plan
    uv run python scripts/migrate_story_keys.py --apply
    make deploy                                             # also re-enables the schedule

Credentials come from the usual boto3 chain (`aws login` profiles work through `boto3[crt]`).
Writes may need the MFA admin profile, which prompts for a code: AWS_PROFILE=<profile> ...
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from weather_story_bot.archive import archive_prefix
from weather_story_bot.models import Story, parse_time
from weather_story_bot.state import PostedStore, content_fingerprint, story_key

if TYPE_CHECKING:
    from types_boto3_dynamodb import DynamoDBClient
    from types_boto3_s3 import S3Client

DEFAULT_TABLE = "weather-story-bot-posted"
STORY_ITEM_PREFIX = "story#"
CONTENT_ITEM_PREFIX = "content#"
_OLD_REVISION_NAME = re.compile(r"^\d{8}T\d{6}Z$")


class MigrationError(Exception):
    """The old data doesn't look like the migration expects; nothing was written."""


@dataclass(frozen=True, slots=True)
class Revision:
    """One old archive pair and where it belongs in the new layout."""

    old_prefix: str
    new_prefix: str
    story: Story
    fingerprint: str
    last_modified: datetime


@dataclass(frozen=True, slots=True)
class Backfill:
    office_id: str
    key: str
    revision: Revision
    message_id: int
    posted_at: datetime
    earlier_message_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Plan:
    copies: tuple[Revision, ...]
    collapsed: tuple[Revision, ...]
    backfills: tuple[Backfill, ...]
    existing_story_keys: tuple[tuple[str, str], ...]
    old_objects: tuple[str, ...]
    legacy_items: tuple[dict[str, Any], ...]


def list_archive(s3: S3Client, bucket: str) -> dict[str, datetime]:
    """Every archive key and its LastModified time."""
    return {
        obj["Key"]: obj["LastModified"]
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="stories/")
        for obj in page.get("Contents", [])
    }


def load_old_revisions(s3: S3Client, bucket: str, objects: dict[str, datetime]) -> list[Revision]:
    revisions = []
    for key in sorted(objects):
        prefix, _, extension = key.rpartition(".")
        if extension != "json" or not _OLD_REVISION_NAME.match(prefix.rpartition("/")[2]):
            continue
        if f"{prefix}.png" not in objects:
            raise MigrationError(f"{key} has no matching PNG")
        story = Story.from_api(json.loads(_read(s3, bucket, key)))
        image = _read(s3, bucket, f"{prefix}.png")
        fingerprint = content_fingerprint(story, image)
        revisions.append(
            Revision(
                old_prefix=prefix,
                new_prefix=archive_prefix(story, fingerprint),
                story=story,
                fingerprint=fingerprint,
                last_modified=objects[key],
            )
        )
    return revisions


def plan_copies(
    revisions: list[Revision], existing_keys: set[str]
) -> tuple[list[Revision], list[Revision]]:
    """Pick one old pair per new prefix, the earliest, skipping prefixes already migrated."""
    copies: dict[str, Revision] = {}
    collapsed = []
    for revision in sorted(revisions, key=lambda r: (r.last_modified, r.old_prefix)):
        if revision.new_prefix in copies:
            collapsed.append(revision)
        elif f"{revision.new_prefix}.json" not in existing_keys:
            copies[revision.new_prefix] = revision
    return list(copies.values()), collapsed


def plan_backfills(
    items: list[dict[str, Any]], revisions: list[Revision]
) -> tuple[list[Backfill], list[tuple[str, str]]]:
    """One record per story from its latest post; stories that already have a record are skipped."""
    by_old_prefix = {revision.old_prefix: revision for revision in revisions}
    existing = {
        (item["office_id"]["S"], item["image_id"]["S"].removeprefix(STORY_ITEM_PREFIX))
        for item in items
        if item["image_id"]["S"].startswith(STORY_ITEM_PREFIX)
    }
    posts: dict[tuple[str, str], list[tuple[datetime, int, Revision]]] = {}
    for item in items:
        if _is_new_or_content_item(item) or "posted_at" not in item:
            continue  # `duplicate_of` markers never posted anything
        old_prefix = item["archive_prefix"]["S"]
        revision = by_old_prefix.get(old_prefix)
        if revision is None:
            raise MigrationError(f"Post {item['image_id']['S']} has no archive pair {old_prefix}")
        office_id = item["office_id"]["S"]
        post = (parse_time(item["posted_at"]["S"]), int(item["telegram_message_id"]["N"]), revision)
        posts.setdefault((office_id, story_key(revision.story)), []).append(post)

    backfills = []
    skipped = []
    for (office_id, key), story_posts in sorted(posts.items()):
        if (office_id, key) in existing:
            skipped.append((office_id, key))
            continue
        story_posts.sort(key=lambda post: post[0])
        posted_at, message_id, revision = story_posts[-1]
        backfills.append(
            Backfill(
                office_id=office_id,
                key=key,
                revision=revision,
                message_id=message_id,
                posted_at=posted_at,
                earlier_message_ids=tuple(post[1] for post in story_posts[:-1]),
            )
        )
    return backfills, skipped


def build_plan(s3: S3Client, dynamodb: DynamoDBClient, bucket: str, table: str) -> Plan:
    """Read everything and decide every change before writing anything."""
    objects = list_archive(s3, bucket)
    revisions = load_old_revisions(s3, bucket, objects)
    items = [
        item
        for page in dynamodb.get_paginator("scan").paginate(TableName=table, ConsistentRead=True)
        for item in page["Items"]
    ]
    copies, collapsed = plan_copies(revisions, set(objects))
    backfills, existing_story_keys = plan_backfills(items, revisions)
    old_objects = sorted(
        f"{revision.old_prefix}.{extension}"
        for revision in revisions
        for extension in ("png", "json")
    )
    legacy_items = [
        item for item in items if not item["image_id"]["S"].startswith(STORY_ITEM_PREFIX)
    ]
    return Plan(
        copies=tuple(copies),
        collapsed=tuple(collapsed),
        backfills=tuple(backfills),
        existing_story_keys=tuple(existing_story_keys),
        old_objects=tuple(old_objects),
        legacy_items=tuple(legacy_items),
    )


def migrate(
    s3: S3Client,
    dynamodb: DynamoDBClient,
    bucket: str,
    table: str,
    *,
    apply: bool,
    delete_old: bool,
    out: Callable[[str], None] = print,
) -> Plan:
    plan = build_plan(s3, dynamodb, bucket, table)
    mode = "Applying" if apply else "Dry run, nothing will change"
    out(f"{mode}: {bucket}, {table}")

    out(f"\nArchive: {len(plan.copies)} copies, {len(plan.collapsed)} identical re-issues")
    for revision in plan.copies:
        out(f"  copy     {revision.old_prefix}\n        -> {revision.new_prefix}")
    for revision in plan.collapsed:
        out(f"  collapse {revision.old_prefix}\n        =  {revision.new_prefix}")
    if apply:
        for revision in plan.copies:
            for extension in ("png", "json"):
                s3.copy_object(
                    Bucket=bucket,
                    Key=f"{revision.new_prefix}.{extension}",
                    CopySource={"Bucket": bucket, "Key": f"{revision.old_prefix}.{extension}"},
                )

    out(f"\nDynamoDB: {len(plan.backfills)} story# records to write")
    store = PostedStore(dynamodb, table)
    for backfill in plan.backfills:
        story = backfill.revision.story
        earlier = ", ".join(str(message_id) for message_id in backfill.earlier_message_ids)
        out(
            f"  record   {backfill.office_id} story#{backfill.key[:12]}… {story.title!r}"
            f" starting {story.start_time.isoformat()}: message {backfill.message_id}"
            + (f" (earlier posts, left in the channel: {earlier})" if earlier else "")
        )
        if apply:
            store.record_posted(
                story,
                backfill.message_id,
                backfill.revision.new_prefix,
                backfill.revision.fingerprint,
                posted_at=backfill.posted_at,
            )
    for office_id, key in plan.existing_story_keys:
        out(f"  keep     {office_id} story#{key[:12]}… already recorded")

    if not delete_old:
        out(f"\nOld data kept: {len(plan.old_objects)} objects, {len(plan.legacy_items)} items")
        return plan
    out(f"\nDelete old: {len(plan.old_objects)} objects, {len(plan.legacy_items)} items")
    if apply:
        for key in plan.old_objects:
            s3.delete_object(Bucket=bucket, Key=key)
        for item in plan.legacy_items:
            dynamodb.delete_item(
                TableName=table,
                Key={"office_id": item["office_id"], "image_id": item["image_id"]},
            )
    return plan


def _is_new_or_content_item(item: dict[str, Any]) -> bool:
    return item["image_id"]["S"].startswith((STORY_ITEM_PREFIX, CONTENT_ITEM_PREFIX))


def _read(s3: S3Client, bucket: str, key: str) -> bytes:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Migrate to story-keyed archive paths and records."
    )
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    parser.add_argument(
        "--delete-old", action="store_true", help="also delete old archive pairs and items"
    )
    parser.add_argument(
        "--bucket", help="archive bucket (default: weather-story-bot-archive-<account>)"
    )
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--region", default="us-east-2")
    args = parser.parse_args(argv)

    import boto3  # Dev-only dependency.

    session = boto3.Session(region_name=args.region)
    account = session.client("sts").get_caller_identity()["Account"]
    bucket = args.bucket or f"weather-story-bot-archive-{account}"
    migrate(
        session.client("s3"),
        session.client("dynamodb"),
        bucket,
        args.table,
        apply=args.apply,
        delete_old=args.delete_old,
    )


if __name__ == "__main__":
    main()
