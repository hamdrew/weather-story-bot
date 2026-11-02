"""Keep docs/logging-review.md in step with the log calls in src/."""

import ast
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "docs" / "logging-review.md"
SRC = ROOT / "src" / "weather_story_bot"

_LEVELS = {"debug": "DEBUG", "info": "INFO", "warning": "WARNING", "error": "ERROR"}
_LEVELS |= {"exception": "ERROR", "critical": "CRITICAL"}
_AREAS = {"nws", "telegram", "office", "story", "store", "history", "run"}
_EVENT = re.compile(r"^[a-z]+(\.[a-z_]+)+$")
_NEW = " (new)"


def _inventory() -> list[dict[str, Any]]:
    """Rows of table 1: id, module, level, message and event, as written in the review."""
    rows = []
    for line in REVIEW.read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if re.fullmatch(r"L\d\d", cells[0]) and len(cells) == 7:
            event = re.match(r"`([^`]+)`", cells[6])
            rows.append(
                {
                    "id": cells[0],
                    "level": cells[2],
                    "message": cells[3].removesuffix(_NEW),
                    "new": cells[3].endswith(_NEW),
                    "event": event.group(1) if event else "",
                }
            )
    return rows


def _log_calls() -> dict[str, str]:
    """Message -> level for every `logger.<level>("message", ...)` call in src/."""
    calls = {}
    for path in sorted(SRC.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "logger"
                and node.func.attr in _LEVELS
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                calls[node.args[0].value] = _LEVELS[node.func.attr]
    return calls


def test_every_log_message_in_src_is_in_the_review():
    reviewed = {row["message"] for row in _inventory()}
    missing = sorted(set(_log_calls()) - reviewed)
    assert not missing, f"log calls missing from docs/logging-review.md table 1: {missing}"
    # A row without the "(new)" mark must still match a call; one marked "(new)" is a call
    # the review adds, so remove the mark when the code gains it.
    in_code = _log_calls()
    stale = sorted(
        row["message"] for row in _inventory() if not row["new"] and row["message"] not in in_code
    )
    assert not stale, f"table 1 rows with no matching log call in src/: {stale}"


def test_event_names_are_well_formed_and_unique():
    events = [row["event"] for row in _inventory() if row["event"]]
    assert events, "no event names found in table 1"
    for event in events:
        assert _EVENT.match(event), f"malformed event name: {event}"
        assert event.split(".")[0] in _AREAS, f"unknown area in event name: {event}"
    assert len(events) == len(set(events)), "an event name is used by more than one call"


def test_warnings_and_errors_have_events_and_only_the_sent_line_among_info_does():
    for row in _inventory():
        if row["level"] in {"WARNING", "ERROR", "CRITICAL"}:
            assert row["event"], f"{row['id']} ({row['level']}) has no event"
        elif row["message"] == "Telegram message sent":
            assert row["event"] == "telegram.message_sent"
        else:
            assert not row["event"], f"{row['id']} ({row['level']}) should have no event"


def test_review_levels_match_the_code():
    in_code = _log_calls()
    mismatched = {
        row["message"]: (row["level"], in_code[row["message"]])
        for row in _inventory()
        if row["message"] in in_code and row["level"] != in_code[row["message"]]
    }
    assert not mismatched, f"level in the review differs from the code: {mismatched}"
