# Smoke Test Results: agent-os to AI-DLC

All checks were read-only, made with the `readonly` AWS profile. Times are America/Chicago.

## Production

| Check | Expected | Actual | Verdict |
|---|---|---|---|
| Lambda `weather-story-bot` code hash | `JTT76d6Mc3gq55aU2JbfqO5qJUxg3kHN5zAVtphbp/Y=` | Same, updated 1:38 PM | Pass |
| First scheduled run after the deploy (1:45 PM) | Completes with no failure | Duration 7.9 s, 111 MB of 256 MB; `Run complete` with `posted: 1, updated: 0, skipped: 1, rejected: 0, failed: 0` | Pass |
| Alarm string `Telegram message sent` | Still logged on a successful post | Logged once for office MKX, then `Story posted` with `status: new` | Pass |
| Alarm string `Ambiguous stories from NWS` | Unchanged | No diff to the string or `infra/monitoring.tf` (Build and Test); not emitted in this run, since no story was ambiguous | Pass (code), not exercised live |
| A story is recorded as posted only after Telegram accepts it | `Story posted` follows `Telegram message sent` | In that order | Pass |

## Staging

| Check | Expected | Actual | Verdict |
|---|---|---|---|
| Lambda `weather-story-bot-staging` code hash | `JTT76d6Mc3gq55aU2JbfqO5qJUxg3kHN5zAVtphbp/Y=` | Same, updated 1:35 PM | Pass |
| A run on the new code | Not required | Not done: staging is paused (its schedule is `DISABLED`), so it has no invocations | Not exercised |

I did not start staging to force a run: `start` changes a live environment and is the owner's to run, and the
production run above already exercised the new code.

## Limits

These checks show the new zip runs and posts. They do not show anything about the pipeline's own behaviour
beyond the run summary, because no behaviour changed.
