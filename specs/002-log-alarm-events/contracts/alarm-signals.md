# Contract: alarm signals

This replaces message text as the contract between the bot's log lines and its alarms. See
[the U2 log-line contract](../../001-u2-log-events/contracts/log-line.md) for the line's other keys.

## Signals

| Event | Filter pattern | Metric | Alarms |
|-------|----------------|--------|--------|
| `telegram.message_sent` | `{ $.event = "telegram.message_sent" }` | `StoriesPosted` | `quiet`, `repost-loop` |
| `nws.ambiguous_stories` | `{ $.event = "nws.ambiguous_stories" }` | `AmbiguousStories` | `nws-ambiguous` |

## Rules

- A filter matches on `$.event` alone, never on `message`, `level` or `logger`.
- Message text may change freely without affecting an alarm.
- Renaming a signal event requires the same change in `src/`, `infra/monitoring.tf`, `docs/logging-review.md` table 1
  and the pinned tests. The offline checks fail if any side is left behind.
- Rolling back to code from before U2 also requires reverting this change, because those lines have no `event`.

## Required filter results

| Sample line | Stories posted | NWS ambiguous |
|-------------|----------------|---------------|
| `event` = `telegram.message_sent`, reworded message | match | no match |
| `event` = `nws.ambiguous_stories`, reworded message | no match | match |
| message "Telegram message sent", no event | no match | no match |
| message "Ambiguous stories from NWS", no event | no match | no match |
| another event | no match | no match |
| runtime line with no event | no match | no match |
| non-JSON line | no match | no match |

## Slow-run signal

The slow-run alarm reads Lambda's `Duration` metric, not a log line, so it adds no log contract. To read an individual
run's duration, use the `platform.report` line's `record.metrics.durationMs`.
