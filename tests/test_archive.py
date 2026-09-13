from __future__ import annotations

import json
from typing import Any

from tests.conftest import BUCKET_NAME, make_story
from weather_story_bot.archive import StoryArchive, archive_prefix


def test_prefix_uses_utc_start_date_and_update_time() -> None:
    story = make_story(
        startTime="2026-09-12T21:00:00-05:00",  # 2026-09-13 in UTC
        updateTime="2026-09-12T19:30:25+00:00",
    )
    assert archive_prefix(story) == "stories/MKX/2026/09/13/aaaa-1111/20260912T193025Z"


def _keys(s3: Any) -> list[str]:
    return sorted(obj["Key"] for obj in s3.list_objects_v2(Bucket=BUCKET_NAME).get("Contents", []))


def test_save_writes_png_and_raw_json(s3: Any) -> None:
    story = make_story()
    prefix = StoryArchive(s3, BUCKET_NAME).save(story, b"png-bytes")

    assert _keys(s3) == [f"{prefix}.json", f"{prefix}.png"]
    png = s3.get_object(Bucket=BUCKET_NAME, Key=f"{prefix}.png")
    assert png["Body"].read() == b"png-bytes"
    assert png["ContentType"] == "image/png"
    body = json.loads(s3.get_object(Bucket=BUCKET_NAME, Key=f"{prefix}.json")["Body"].read())
    assert body == dict(story.raw)


def test_save_is_idempotent_and_updates_add_new_pair(s3: Any) -> None:
    archive = StoryArchive(s3, BUCKET_NAME)
    archive.save(make_story(), b"v1")
    archive.save(make_story(), b"v1")
    archive.save(make_story(updateTime="2026-09-12T23:00:00+00:00"), b"v2")

    assert len(_keys(s3)) == 4
