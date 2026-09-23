"""Local dry run: fetch live stories and print each one's decision and caption.

Uses only the public NWS API; no AWS resources, and never Telegram. Local tools are read-only
(`global/principles.md`) — a write mode needs a new, deliberate flag and a spec change.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime

import httpx

from weather_story_bot.config import is_valid_office_id
from weather_story_bot.models import Story
from weather_story_bot.nws import NwsClient, NwsError
from weather_story_bot.planner import Decision, Outcome, decide, select_active
from weather_story_bot.state import story_key
from weather_story_bot.telegram import build_caption

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is a dev dependency; without it, use the shell env only.

    def load_dotenv() -> bool:
        return False


DEFAULT_USER_AGENT = "weather-story-bot/0.1.0 (local dry run)"


def _office_id(value: str) -> str:
    upper = value.upper()
    if not is_valid_office_id(upper):
        raise argparse.ArgumentTypeError(f"invalid office id {value!r}: expected e.g. 'MKX'")
    return upper


def main(argv: list[str] | None = None, *, now: datetime | None = None) -> int:
    # Load variables from a local .env file (if present) without overriding
    # anything already set in the shell environment.
    load_dotenv()
    now = now or datetime.now(UTC)

    parser = argparse.ArgumentParser(prog="weather-story-bot", description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="print each active story's decision and caption without posting (required)",
    )
    parser.add_argument("--office", default="MKX", type=_office_id, help="NWS office id")
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("NWS_USER_AGENT", DEFAULT_USER_AGENT),
        help="User-Agent sent to api.weather.gov (defaults to $NWS_USER_AGENT)",
    )
    args = parser.parse_args(argv)

    with httpx.Client() as http:
        nws = NwsClient(http, args.user_agent)
        try:
            stories = nws.list_stories(args.office)
        except NwsError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if not stories:
            print(f"No active weather stories for {args.office}.")
            return 0

        active, expired = select_active(stories, now)
        failed = False
        downloaded: list[tuple[Story, bytes]] = []
        for story in active:
            try:
                downloaded.append((story, nws.download_image(story)))
            except NwsError as exc:
                print(f"error: {exc}", file=sys.stderr)
                failed = True

        # No DynamoDB locally, so every accepted story looks like a first post.
        decisions = decide(args.office, downloaded, {}, now)

    for decision in [*expired, *decisions]:
        _print_decision(decision, args.office)

    return 1 if failed else 0


def _print_decision(decision: Decision, office_id: str) -> None:
    story = decision.story
    # story_key, not image_id: it's stable across revisions and matches the DynamoDB sort key
    # (`story#<story_key>`), unlike image_id, which NWS reissues under a new UUID each revision.
    print(f"--- #{story.order} {story_key(story)} [{_label(decision)}]")
    print(f"image: {story.download}")
    print(build_caption(story, office_id, updated=False))
    print()


def _label(decision: Decision) -> str:
    match decision.outcome:
        case Outcome.EXPIRED:
            return "expired"
        case Outcome.REJECTED:
            return f"rejected ({', '.join(decision.reasons)})"
        case Outcome.POST:
            return "new-or-updated (state not read)"
        case Outcome.UPDATE | Outcome.UNCHANGED:
            # decide() is given no records locally, so it never returns these outcomes.
            raise AssertionError("unreachable")


if __name__ == "__main__":
    sys.exit(main())
