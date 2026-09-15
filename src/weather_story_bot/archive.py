"""S3 archive of every posted story image and its raw metadata."""

from __future__ import annotations

import json
from datetime import UTC
from typing import TYPE_CHECKING

from weather_story_bot.models import Story

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client


def archive_prefix(story: Story) -> str:
    """`stories/{office}/{YYYY}/{MM}/{DD}/{image_id}/{updateTime}` (dates in UTC)."""
    start = story.start_time.astimezone(UTC)
    updated = story.update_time.astimezone(UTC)
    return f"stories/{story.office_id}/{start:%Y/%m/%d}/{story.image_id}/{updated:%Y%m%dT%H%M%SZ}"


class StoryArchive:
    def __init__(self, s3_client: S3Client, bucket: str) -> None:
        self._s3 = s3_client
        self._bucket = bucket

    def save(self, story: Story, image_bytes: bytes) -> str:
        """Write `<prefix>.png` and `<prefix>.json`; rewriting the same revision is harmless."""
        prefix = archive_prefix(story)
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
