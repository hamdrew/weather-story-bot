from __future__ import annotations

import json
from typing import Any

from tests.conftest import BUCKET_NAME, make_story
from weather_story_bot.archive import StoryArchive, archive_prefix
from weather_story_bot.state import content_fingerprint, story_key

FINGERPRINT = "0123456789abcdef" + "f" * 48


def test_prefix_is_story_folder_and_revision_file() -> None:
    story = make_story(
        title="Storms Monday Night",
        startTime="2026-09-12T21:05:00-05:00",  # 02:05 on 2026-09-13 in UTC
    )
    key = story_key(story)[:8]
    assert archive_prefix(story, FINGERPRINT) == (
        f"stories/MKX/2026/09/13/0205Z-storms-monday-night-{key}/0123456789abcdef"
    )


def test_prefix_ignores_image_id_update_time_and_end_time() -> None:
    story = make_story()
    reissue = make_story(
        download="https://api.weather.gov/offices/MKX/weatherstories/download/bbbb-2222",
        updateTime="1970-01-01T00:00:00+00:00",
        endTime="2026-09-14T00:00:00+00:00",
        altText="",
    )
    assert archive_prefix(reissue, FINGERPRINT) == archive_prefix(story, FINGERPRINT)


def test_prefix_separates_titles_with_the_same_slug() -> None:
    first = archive_prefix(make_story(title="Rain & Storms"), FINGERPRINT)
    second = archive_prefix(make_story(title="Rain / Storms"), FINGERPRINT)
    assert first.rsplit("-", 1)[0] == second.rsplit("-", 1)[0]
    assert first != second


def test_prefix_slug_is_ascii_and_bounded() -> None:
    folder = archive_prefix(make_story(title="Héat Índex — " + "x" * 80), FINGERPRINT).split("/")[5]
    slug = folder.removeprefix("1924Z-").rsplit("-", 1)[0]
    assert slug.startswith("heat-index-xxx")
    assert len(slug) == 48
    assert (
        archive_prefix(make_story(title="🌩️"), FINGERPRINT).split("/")[5].startswith("1924Z-story-")
    )


def _keys(s3: Any) -> list[str]:
    return sorted(obj["Key"] for obj in s3.list_objects_v2(Bucket=BUCKET_NAME).get("Contents", []))


def test_save_writes_png_and_raw_json(s3: Any) -> None:
    story = make_story()
    prefix = StoryArchive(s3, BUCKET_NAME).save(story, b"png-bytes", FINGERPRINT)

    assert prefix == archive_prefix(story, FINGERPRINT)
    assert _keys(s3) == [f"{prefix}.json", f"{prefix}.png"]
    png = s3.get_object(Bucket=BUCKET_NAME, Key=f"{prefix}.png")
    assert png["Body"].read() == b"png-bytes"
    assert png["ContentType"] == "image/png"
    body = json.loads(s3.get_object(Bucket=BUCKET_NAME, Key=f"{prefix}.json")["Body"].read())
    assert body == dict(story.raw)


def test_same_revision_rewrites_and_new_content_adds_a_pair(s3: Any) -> None:
    archive = StoryArchive(s3, BUCKET_NAME)
    story = make_story()
    reissue = make_story(updateTime="1970-01-01T00:00:00+00:00")
    revised = make_story(description="Storms arrive earlier.")

    first = archive.save(story, b"v1", content_fingerprint(story, b"v1"))
    assert archive.save(reissue, b"v1", content_fingerprint(reissue, b"v1")) == first
    second = archive.save(revised, b"v1", content_fingerprint(revised, b"v1"))

    assert second.rsplit("/", 1)[0] == first.rsplit("/", 1)[0]
    assert len(_keys(s3)) == 4
