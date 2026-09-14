"""Local dry run: fetch live stories and print the captions that would be posted.

Uses only the public NWS API; no AWS resources. Telegram is called only with --send-telegram,
which posts each story to $TELEGRAM_CHAT_ID using the same code path as the Lambda handler.
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

from weather_story_bot.handler import post_story
from weather_story_bot.nws import NwsClient, NwsError
from weather_story_bot.telegram import TelegramClient, TelegramError, build_caption

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is a dev dependency; without it, use the shell env only.

    def load_dotenv() -> bool:
        return False


DEFAULT_USER_AGENT = "weather-story-bot/0.1.0 (local dry run)"


def main(argv: list[str] | None = None) -> int:
    # Load variables from a local .env file (if present) without overriding
    # anything already set in the shell environment.
    load_dotenv()

    parser = argparse.ArgumentParser(prog="weather-story-bot", description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="print captions for the office's active stories without posting (required)",
    )
    parser.add_argument("--office", default="MKX", type=str.upper, help="NWS office id")
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("NWS_USER_AGENT", DEFAULT_USER_AGENT),
        help="User-Agent sent to api.weather.gov (defaults to $NWS_USER_AGENT)",
    )
    parser.add_argument(
        "--send-telegram",
        action="store_true",
        help="also post each story to $TELEGRAM_CHAT_ID using $TELEGRAM_BOT_TOKEN",
    )
    args = parser.parse_args(argv)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if args.send_telegram and not (token and chat_id):
        print(
            "error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required with --send-telegram",
            file=sys.stderr,
        )
        return 2

    failed = False
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
        telegram = TelegramClient(http, token) if args.send_telegram else None
        for story in stories:
            print(f"--- #{story.order} {story.image_id} (updated {story.update_time.isoformat()})")
            print(f"image: {story.download}")
            print(build_caption(story, args.office, updated=False))
            if telegram is not None:
                try:
                    image = nws.download_image(story)
                    message_id = post_story(
                        telegram, chat_id, args.office, story, image, updated=False
                    )
                except (NwsError, TelegramError) as exc:
                    print(f"error: {exc}", file=sys.stderr)
                    failed = True
                else:
                    print(f"sent: message_id={message_id}")
            print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
