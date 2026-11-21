"""Keep docs/logging-review.md and the log calls in src/ in step.

The review's table 1 is the contract: each log call's level and message, and the event it
carries. This file parses `src/` with `ast` and fails when a call and the table disagree, or when a
field name is one the Lambda runtime's JSON line or Python's logging owns. It is a guardrail,
not a proof: it reads `logger.<level>("constant message", extra={...})` calls and does not try to
catch a call written in some other form; a reviewer reads those.
"""

import ast
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "docs" / "logging-review.md"
SRC = ROOT / "src" / "weather_story_bot"

_LEVELS = {"debug": "DEBUG", "info": "INFO", "warning": "WARNING", "error": "ERROR"}
_LEVELS |= {"exception": "ERROR", "critical": "CRITICAL"}
_EVENT = re.compile(r"^(nws|telegram|office|story|store|history|run)\.[a-z_]+$")
_FIELD = re.compile(r"^[a-z][a-z0-9_]*$")
_SENT = "Telegram message sent"
_MUST_HAVE_EVENT = {"WARNING", "ERROR", "CRITICAL"}
# Names the runtime's line or Python's logging owns (FR-009): every LogRecord attribute, plus
# the keys the runtime adds (it drops an extra named `location`) and `office`, which the bot's
# record factory stamps.
_FORBIDDEN_KEYS = set(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "timestamp",
    "level",
    "logger",
    "requestId",
    "location",
    "office",
}


@dataclass(frozen=True)
class LogCall:
    """One `logger.<level>("message", ...)` call whose message is a str constant."""

    module: str
    line: int
    level: str
    message: str
    # The constant str keys of the `extra` dict literal; empty when `extra` is anything else.
    keys: tuple[str, ...]
    has_event: bool
    # The event's value when it is a str constant; None for a name, an f-string and so on.
    event: str | None

    @property
    def where(self) -> str:
        return f"{self.module}:{self.line} {self.level} {self.message!r}"


def _log_calls_in(source: str, module: str) -> list[LogCall]:
    """The `logger.<level>("constant", ...)` calls in `source`."""
    calls: list[LogCall] = []
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _LEVELS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            continue
        calls.append(_read_call(node, module, _LEVELS[node.func.attr], node.args[0].value))
    return calls


def _read_call(node: ast.Call, module: str, level: str, message: str) -> LogCall:
    extra = next((kw.value for kw in node.keywords if kw.arg == "extra"), None)
    keys: list[str] = []
    has_event, event = False, None
    if isinstance(extra, ast.Dict):
        for key, value in zip(extra.keys, extra.values, strict=True):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                continue  # a `**` spread or a computed key: not read
            keys.append(key.value)
            if key.value == "event":
                has_event = True
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    event = value.value
    return LogCall(module, node.lineno, level, message, tuple(keys), has_event, event)


def _src_calls() -> list[LogCall]:
    return [
        call
        for path in sorted(SRC.glob("*.py"))
        for call in _log_calls_in(path.read_text(), path.name)
    ]


def _problems(calls: list[LogCall]) -> list[str]:
    """One message per broken rule, each naming the module, line and message."""
    problems = []
    for call in calls:
        needs_event = call.level in _MUST_HAVE_EVENT or call.message == _SENT
        if needs_event and call.event is None:
            reason = "event is not a str constant" if call.has_event else "has no event"
            problems.append(f"{call.where}: {reason}")
        if not needs_event and call.has_event:
            problems.append(f"{call.where}: an event on a call that should have none")
        for key in call.keys:
            if key in _FORBIDDEN_KEYS:
                problems.append(f"{call.where}: forbidden extra key {key!r}")
            elif not _FIELD.match(key):
                problems.append(f"{call.where}: extra key {key!r} is not lowercase snake_case")
    return problems


def _event_set_diff(code: set[str], table: set[str]) -> str:
    """An empty string when the sets are equal; otherwise the events each side lacks."""
    if code == table:
        return ""
    return (
        f"events in src/ but not in table 1: {sorted(code - table)}; "
        f"events in table 1 but not in src/: {sorted(table - code)}"
    )


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
                    "message": cells[3],
                    "event": event.group(1) if event else "",
                }
            )
    return rows


def _levels_by_message(calls: list[LogCall]) -> dict[str, str]:
    return {call.message: call.level for call in calls}


def test_every_log_message_in_src_is_in_the_review():
    calls = _src_calls()
    reviewed = {row["message"] for row in _inventory()}
    missing = sorted({call.message for call in calls} - reviewed)
    assert not missing, f"log calls missing from docs/logging-review.md table 1: {missing}"
    # Every row must match a call: a row for a call that is gone, or not yet written, fails.
    in_code = {call.message for call in calls}
    stale = sorted(row["message"] for row in _inventory() if row["message"] not in in_code)
    assert not stale, f"table 1 rows with no matching log call in src/: {stale}"


def test_event_names_are_well_formed_and_unique():
    events = [row["event"] for row in _inventory() if row["event"]]
    assert events, "no event names found in table 1"
    for event in events:
        assert _EVENT.match(event), f"malformed event name: {event}"
    assert len(events) == len(set(events)), "an event name is used by more than one call"


def test_warnings_and_errors_have_events_and_only_the_sent_line_among_info_does():
    for row in _inventory():
        if row["level"] in _MUST_HAVE_EVENT:
            assert row["event"], f"{row['id']} ({row['level']}) has no event"
        elif row["message"] == _SENT:
            assert row["event"] == "telegram.message_sent"
        else:
            assert not row["event"], f"{row['id']} ({row['level']}) should have no event"


def test_review_levels_match_the_code():
    calls = _src_calls()
    in_code = _levels_by_message(calls)
    mismatched = {
        row["message"]: (row["level"], in_code[row["message"]])
        for row in _inventory()
        if row["message"] in in_code and row["level"] != in_code[row["message"]]
    }
    assert not mismatched, f"level in the review differs from the code: {mismatched}"


def test_src_log_calls_follow_the_rules():
    problems = _problems(_src_calls())
    assert not problems, "log calls break the contract:\n" + "\n".join(problems)


def test_event_constants_in_src_match_table_1():
    calls = _src_calls()
    code = {call.event for call in calls if call.event}
    table = {row["event"] for row in _inventory() if row["event"]}
    assert code, "no event constants found in src/"
    assert _event_set_diff(code, table) == ""


# One bad sample per rule, so each rule is shown to fail and to name its call.

_GOOD_EVENT = '"event": "nws.boom"'


def _problems_in(source: str) -> list[str]:
    return _problems(_log_calls_in(source, "sample.py"))


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            'logger.warning("Boom", extra={"error": "x"})',
            "sample.py:1 WARNING 'Boom': has no event",
        ),
        ('logger.warning("Boom")', "sample.py:1 WARNING 'Boom': has no event"),
        (
            f'logger.info("{_SENT}", extra={{"chat_id": "1"}})',
            f"sample.py:1 INFO '{_SENT}': has no event",
        ),
        (
            f'logger.info("Fine", extra={{{_GOOD_EVENT}}})',
            "sample.py:1 INFO 'Fine': an event on a call that should have none",
        ),
        (
            'logger.warning("Boom", extra={"event": name})',
            "sample.py:1 WARNING 'Boom': event is not a str constant",
        ),
        (
            'logger.warning("Boom", extra={"event": f"nws.{kind}"})',
            "sample.py:1 WARNING 'Boom': event is not a str constant",
        ),
        ('logger.exception("Boom")', "sample.py:1 ERROR 'Boom': has no event"),
        (
            f'logger.warning("Boom", extra={{{_GOOD_EVENT}, "office": "MKX"}})',
            "forbidden extra key 'office'",
        ),
        (
            f'logger.warning("Boom", extra={{{_GOOD_EVENT}, "filename": "a"}})',
            "forbidden extra key 'filename'",
        ),
        (
            f'logger.warning("Boom", extra={{{_GOOD_EVENT}, "location": "MKX"}})',
            "forbidden extra key 'location'",
        ),
        (
            f'logger.warning("Boom", extra={{{_GOOD_EVENT}, "retryAfter": 1}})',
            "extra key 'retryAfter' is not lowercase snake_case",
        ),
        (
            "logger.warning('Boom', extra=some_dict)",
            "sample.py:1 WARNING 'Boom': has no event",
        ),
        (
            f'logger.info("{_SENT}", extra=some_dict)',
            f"sample.py:1 INFO '{_SENT}': has no event",
        ),
    ],
)
def test_a_broken_rule_is_reported_with_its_call(source: str, expected: str):
    assert any(expected in problem for problem in _problems_in(source)), _problems_in(source)


def test_a_well_formed_call_reports_nothing():
    source = (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        f'logger.warning("Boom", extra={{{_GOOD_EVENT}, "error": repr(exc)}})\n'
        'logger.info("Fine")\n'
        "build = logging.getLogRecordFactory()\n"
    )
    assert _problems_in(source) == []


def test_an_info_call_may_pass_a_built_dict_without_an_event():
    assert _problems_in('logger.info("Fine", extra=built)') == []


def test_calls_the_check_does_not_read_are_left_alone():
    source = (
        'logger.warning(f"Boom {x}")\n'
        'logging.warning("Boom")\n'
        'parser.error("bad office")\n'
        'warnings.warn("careful")\n'
    )
    assert _problems_in(source) == []


def test_the_event_set_diff_is_empty_for_equal_sets_and_names_the_difference():
    assert _event_set_diff({"nws.a", "nws.b"}, {"nws.b", "nws.a"}) == ""
    only_code = _event_set_diff({"nws.a", "nws.b"}, {"nws.a"})
    assert "nws.b" in only_code
    only_table = _event_set_diff({"nws.a"}, {"nws.a", "nws.c"})
    assert "nws.c" in only_table
