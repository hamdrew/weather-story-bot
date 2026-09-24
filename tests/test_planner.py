from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.conftest import make_story
from weather_story_bot.models import Story
from weather_story_bot.planner import Decision, Outcome, decide, select_active
from weather_story_bot.state import (
    PostedRecord,
    content_fingerprint,
    description_sha256,
    image_sha256,
    story_key,
)

NOW = datetime(2026, 9, 13, 0, 0, tzinfo=UTC)
REISSUED_DOWNLOAD = "https://api.weather.gov/offices/MKX/weatherstories/download/bbbb-2222"


def record_for(story: Story, image: bytes = b"PNG") -> PostedRecord:
    return PostedRecord(
        image_id=story.image_id,
        telegram_message_id=101,
        archive_prefix="MKX/old-prefix",
        fingerprint=content_fingerprint(story, image),
        image_sha256=image_sha256(image),
        description_sha256=description_sha256(story),
    )


def test_select_active_splits_stories_at_the_end_time() -> None:
    active_story = make_story(endTime="2026-09-13T19:24:00+00:00")
    expired_story = make_story(
        title="Expired Story", startTime="2026-09-12T18:00:00+00:00", endTime=NOW.isoformat()
    )

    active, expired = select_active([active_story, expired_story], NOW)

    assert active == [active_story]
    assert expired == [Decision(expired_story, Outcome.EXPIRED)]


def test_select_active_treats_end_time_equal_to_now_as_expired() -> None:
    story = make_story(endTime=NOW.isoformat())

    active, expired = select_active([story], NOW)

    assert active == []
    assert expired == [Decision(story, Outcome.EXPIRED)]


def test_decide_new_story_with_no_record_is_a_post() -> None:
    story = make_story()

    [decision] = decide("MKX", [(story, b"PNG")], {}, NOW)

    assert decision == Decision(story, Outcome.POST, b"PNG", record=None)


def test_decide_unchanged_fingerprint_is_unchanged() -> None:
    story = make_story()
    record = record_for(story)

    [decision] = decide("MKX", [(story, b"PNG")], {story_key(story): record}, NOW)

    assert decision == Decision(story, Outcome.UNCHANGED, b"PNG", record=record)


def test_decide_changed_fingerprint_is_an_update() -> None:
    story = make_story()
    record = record_for(story, b"PNG-old")

    [decision] = decide("MKX", [(story, b"PNG-new")], {story_key(story): record}, NOW)

    assert decision == Decision(
        story, Outcome.UPDATE, b"PNG-new", record=record, changes=("image",)
    )


@pytest.mark.parametrize(
    ("image", "overrides", "changes"),
    [
        (b"PNG", {"description": "Storm timing has shifted."}, ("description",)),
        (b"PNG-new", {"description": "Storm timing has shifted."}, ("image", "description")),
        # "Cool Into This Weekend" on 2026-09-24: new UUID, new image and a trimmed description.
        (
            b"PNG-new",
            {"download": REISSUED_DOWNLOAD, "description": "Storm timing has shifted."},
            ("image_id", "image", "description"),
        ),
    ],
)
def test_decide_update_names_what_changed(
    image: bytes, overrides: dict[str, object], changes: tuple[str, ...]
) -> None:
    posted = make_story()
    revised = make_story(**overrides)
    record = record_for(posted)

    [decision] = decide("MKX", [(revised, image)], {story_key(revised): record}, NOW)

    assert decision.outcome is Outcome.UPDATE
    assert decision.changes == changes


def test_decide_update_from_a_record_without_content_hashes_says_content() -> None:
    # Records written before 2026-09-24 keep only the combined fingerprint.
    story = make_story(download=REISSUED_DOWNLOAD)
    record = PostedRecord(
        image_id="old-image-id",
        telegram_message_id=101,
        archive_prefix="MKX/old-prefix",
        fingerprint="fp-old",
    )

    [decision] = decide("MKX", [(story, b"PNG")], {story_key(story): record}, NOW)

    assert decision.changes == ("image_id", "content")


def test_decide_ignores_records_for_other_stories() -> None:
    story = make_story()
    other = make_story(title="Different Story", startTime="2026-09-11T19:24:00+00:00")
    record = record_for(other)

    [decision] = decide("MKX", [(story, b"PNG")], {story_key(other): record}, NOW)

    assert decision.outcome is Outcome.POST


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        # Same download URL, different title and start: shared image_id.
        (
            {"title": "Different Story", "startTime": "2026-09-11T19:24:00+00:00"},
            "duplicate_image_id",
        ),
        # Same title and start, different download URL: shared identity.
        ({"download": REISSUED_DOWNLOAD}, "duplicate_title_and_start"),
    ],
)
def test_decide_rejects_stories_sharing_an_image_id_or_identity(
    extra: dict[str, object], reason: str
) -> None:
    listed = make_story()
    sibling = make_story(order=3, **extra)

    decisions = decide("MKX", [(listed, b"PNG"), (sibling, b"PNG-sibling")], {}, NOW)

    assert [d.outcome for d in decisions] == [Outcome.REJECTED, Outcome.REJECTED]
    assert all(reason in d.reasons for d in decisions)


def test_decide_rejects_stories_sharing_an_image_regardless_of_identity() -> None:
    listed = make_story()
    sibling = make_story(
        order=3,
        title="Different Story",
        startTime="2026-09-11T19:24:00+00:00",
        download=REISSUED_DOWNLOAD,
    )

    decisions = decide("MKX", [(listed, b"PNG"), (sibling, b"PNG")], {}, NOW)

    assert [d.outcome for d in decisions] == [Outcome.REJECTED, Outcome.REJECTED]
    assert all("duplicate_image" in d.reasons for d in decisions)


def test_decide_rejection_carries_every_matching_reason() -> None:
    listed = make_story()
    sibling = make_story(order=3)  # Same title, start time and download as `listed`.

    decisions = decide("MKX", [(listed, b"PNG"), (sibling, b"PNG")], {}, NOW)

    assert set(decisions[0].reasons) == {
        "duplicate_image_id",
        "duplicate_title_and_start",
        "duplicate_image",
    }


def test_decide_leaves_non_colliding_stories_alone() -> None:
    listed = make_story()
    other = make_story(
        order=3,
        title="Different Story",
        startTime="2026-09-11T19:24:00+00:00",
        download=REISSUED_DOWNLOAD,
    )

    decisions = decide("MKX", [(listed, b"PNG"), (other, b"PNG-other")], {}, NOW)

    assert [d.outcome for d in decisions] == [Outcome.POST, Outcome.POST]
    assert all(d.reasons == () for d in decisions)


def test_decide_returns_decisions_in_listing_order() -> None:
    first = make_story()
    second = make_story(order=2, title="Second Story", startTime="2026-09-12T20:00:00+00:00")

    decisions = decide("MKX", [(first, b"PNG-1"), (second, b"PNG-2")], {}, NOW)

    assert [d.story for d in decisions] == [first, second]
