"""S3 archive of every posted story revision: the image and its raw metadata."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC
from typing import TYPE_CHECKING

from weather_story_bot.models import Story
from weather_story_bot.state import story_key

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

SLUG_MAX_CHARS = 48
STORY_KEY_CHARS = 8
FINGERPRINT_CHARS = 16


def _slug(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    return slug[:SLUG_MAX_CHARS].rstrip("-") or "story"


def archive_prefix(story: Story, fingerprint: str) -> str:
    """`stories/{office}/{YYYY}/{MM}/{DD}/{HHMM}Z-{title-slug}-{story_key}/{fingerprint}`.

    The date and time are the story's start in UTC. The folder is one story (title + start time,
    made unique by the `story_key` prefix, since titles can share a slug) and each file pair is
    one revision of its content, so a re-issue under a new image UUID lands on the same pair.
    """
    start = story.start_time.astimezone(UTC)
    folder = f"{start:%H%M}Z-{_slug(story.title)}-{story_key(story)[:STORY_KEY_CHARS]}"
    revision = fingerprint[:FINGERPRINT_CHARS]
    return f"stories/{story.office_id}/{start:%Y/%m/%d}/{folder}/{revision}"


class StoryArchive:
    def __init__(self, s3_client: S3Client, bucket: str) -> None:
        self._s3 = s3_client
        self._bucket = bucket

    def save(self, story: Story, image_bytes: bytes, fingerprint: str) -> str:
        """Write `<prefix>.png` and `<prefix>.json`; rewriting the same revision is harmless."""
        prefix = archive_prefix(story, fingerprint)
        self._s3.put_object(
            Bucket=self._bucket,
            Key=f"{prefix}.png",
            Body=image_bytes,
            ContentType="image/png",
        )
        self._s3.put_object(
            Bucket=self._bucket,
            Key=f"{prefix}.json",
            Body=json.dumps(story.raw, indent=2, ensure_ascii=False).encode(),
            ContentType="application/json",
        )
        return prefix
