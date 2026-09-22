"""Pure decision logic: what to do with each story, and why.

No logging, no I/O, no clock of its own — the handler and the CLI both call this to decide,
then only the handler acts. See `agent-os/standards/global/principles.md`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from weather_story_bot.models import Story
from weather_story_bot.state import PostedRecord, content_fingerprint, image_sha256, story_key


class Outcome(StrEnum):
    POST = "post"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    EXPIRED = "expired"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Decision:
    """What to do with one story, and why."""

    story: Story
    outcome: Outcome
    image: bytes | None = None
    reasons: tuple[str, ...] = ()
    record: PostedRecord | None = None


def select_active(stories: list[Story], now: datetime) -> tuple[list[Story], list[Decision]]:
    """Split a listing into stories worth downloading and `expired` decisions for the rest.

    Expired stories get no action at all: no download, no checks, no post or delete.
    """
    active = [story for story in stories if story.end_time > now]
    expired = [Decision(story, Outcome.EXPIRED) for story in stories if story.end_time <= now]
    return active, expired


_AMBIGUITY_CHECKS: tuple[tuple[str, Callable[[Story, bytes], str]], ...] = (
    ("duplicate_image_id", lambda story, _: story.image_id),
    ("duplicate_title_and_start", lambda story, _: story_key(story)),
    ("duplicate_image", lambda _, image: image_sha256(image)),
)


def decide(
    office_id: str,
    downloaded: list[tuple[Story, bytes]],
    records: Mapping[str, PostedRecord],
    now: datetime,
) -> list[Decision]:
    """Decide `rejected` / `post` / `update` / `unchanged` for every downloaded story.

    `records` maps `story_key` to the office's current `PostedRecord`, already read by the
    caller. `office_id` and `now` are unused today; kept so the handler's per-office, per-run
    loop can call this the same way at every step.
    """
    del office_id, now
    reasons_by_index = _find_ambiguous(downloaded)
    decisions: list[Decision] = []
    for index, (story, image) in enumerate(downloaded):
        if index in reasons_by_index:
            reasons = tuple(reasons_by_index[index])
            decisions.append(Decision(story, Outcome.REJECTED, image, reasons))
            continue
        current = records.get(story_key(story))
        fingerprint = content_fingerprint(story, image)
        if current is not None and current.fingerprint == fingerprint:
            decisions.append(Decision(story, Outcome.UNCHANGED, image, record=current))
        else:
            outcome = Outcome.POST if current is None else Outcome.UPDATE
            decisions.append(Decision(story, outcome, image, record=current))
    return decisions


def _find_ambiguous(downloaded: list[tuple[Story, bytes]]) -> dict[int, list[str]]:
    """Find every story sharing an image ID, title and start time, or image with another.

    NWS data is untrusted: when listed stories collide, there's no telling which is right.
    """
    reasons: dict[int, list[str]] = {}
    for reason, key in _AMBIGUITY_CHECKS:
        values = [key(story, image) for story, image in downloaded]
        occurrences = Counter(values)
        for index, value in enumerate(values):
            if occurrences[value] > 1:
                reasons.setdefault(index, []).append(reason)
    return reasons
