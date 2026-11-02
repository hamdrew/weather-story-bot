# Requirements Analysis — Questions

Inputs: the approved intent statement, scope document, initiative brief and wireframes; the code knowledge
base for `weather-story-bot`; and a read of the current logging and alarms.

What the bot records today, for context:

- **Warnings** (WARNING level): `NWS request failed, retrying`, `NWS server error, retrying`,
  `Telegram rate limited, retrying`, `Photo rejected, sending as document`,
  `Telegram delete failed, old message kept`, `Office lease release failed`, `History write failed`.
- **Errors** (ERROR level): `Ambiguous stories from NWS`, and caught failures logged with a stack trace
  (`Failed to take office lease`, `Failed to list stories`, `Failed to process office`,
  `Failed to download story image`, `Failed to read posted stories`, `Failed to process story`).
  These are caught exceptions: each adds to the run's `failed` count and the run carries on. At the end
  of the run `lambda_handler` raises `ProcessingError` when any `failed` count is above zero, so the run
  still fails and today's `errors` alarm emails the owner. `Ambiguous stories from NWS` counts as
  rejected, not failed, and has its own `nws-ambiguous` alarm. (Corrected after Q4: an earlier version
  of this line said caught errors did not trip the `errors` alarm.)
- **Alarms** (email through the alerts topic): `errors` (Lambda failures), `missed-runs` (no invocations),
  `quiet` and `repost-loop` (both count the exact message `Telegram message sent`), and `nws-ambiguous`
  (counts the exact message `Ambiguous stories from NWS`). Logs are kept 30 days.

## Q1. [Product owner] Which warning kinds does "none missed" cover?

The intent says a named list, fixed here.

A. Every warning the bot logs today (the seven above), and any new WARNING the code adds later
B. Only the warnings that mean something was lost or degraded (photo sent as document, delete failed, lease release failed, history write failed); retries that then succeed are left out
C. Option A, plus new "unusual" patterns nothing records today (for example a slow run, or NWS sending no stories)
D. Not yet defined
X. Other (please specify)

[Answer]: A

## Q2. [Product owner] Should the warning alarm email you for retries that then succeed?

"Any warning" today includes NWS and Telegram retries, which can happen on an ordinary day and usually heal themselves.

A. Yes, every warning emails me, retries included
B. No, retries that succeed don't email me; they still show on the dashboard
C. Email only when a warning repeats (for example more than a set number in a day)
D. Not yet defined
X. Other (please specify)

[Answer]: A

## Q3. [Product owner] Which error kinds does "none missed" cover?

A. Every ERROR the bot logs (ambiguous stories and every caught failure above), plus Lambda run failures
B. Option A, plus any new ERROR the code adds later
C. Not yet defined
X. Other (please specify)

[Answer]: B

## Q4. [Product owner] Caught errors don't trip today's `errors` alarm. Should they?

The scope left open whether errors no current alarm covers should alarm too.

A. Yes, any logged error emails me, the same way as the warning alarm
B. No, caught errors only show on the dashboard (and make the verdict not healthy)
C. Not yet defined
X. Other (please specify)

[Answer]: C (superseded by Q9: the question rested on a wrong premise, corrected in the context above)

## Q5. [Product owner] Which signals together mean "healthy"?

A. The four today's alarms watch: runs on schedule, no failed runs, a story posted recently, no repost loop
B. Option A, plus no errors in the window (already decided: an error makes the verdict not healthy) and NWS reachable
C. Option B, plus run duration staying under a limit
D. Not yet defined
X. Other (please specify)

[Answer]: A

## Q6. [Product owner] What window do the counts and the recent list cover?

Logs are kept 30 days, which is the longest anything can stay visible without keeping logs longer.

A. The last 24 hours
B. The last 7 days
C. The dashboard's own time range, which you can change (default 7 days)
D. Not yet defined
X. Other (please specify)

[Answer]: C

## Q7. [Operations] Is anything needed for a stale or broken dashboard beyond what exists?

The `missed-runs` alarm already emails you when the bot stops running, and the "unknown" verdict covers missing data on the page.

A. No; the `missed-runs` alarm and the "unknown" verdict are enough
B. Yes, also alarm if the dashboard's own data stops arriving while runs continue
C. Not yet defined
X. Other (please specify)

[Answer]: A

## Q8. [Product owner] What does the logging review deliver?

A. A written review in the repository (findings and decisions), plus the code changes that follow from it
B. Only the code changes, with the findings in the pull request descriptions
C. Not yet defined
X. Other (please specify)

[Answer]: A

## Q9. [Product owner] What should the error alarm watch? (follow-up to Q4)

Every error logged today already emails the owner, through the `errors` alarm (failed runs) or
`nws-ambiguous`. The `errors` alarm sees failed runs, not error logs, so a future ERROR that does not add
to the `failed` count would go unnoticed; Q3 covers future errors.

A. Any ERROR the bot logs, today's and future ones, emails the owner, alongside the existing failed-run alarm
B. Keep today's coverage (failed runs and `nws-ambiguous`); other errors show on the dashboard only
X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Warnings covered by "none missed": all seven the bot logs today, and any new WARNING added later (Q1).
- The warning alarm emails on every warning, retries that then succeed included (Q2).
- Errors covered by "none missed": every ERROR the bot logs, Lambda run failures, and any new ERROR added later (Q3).
- An alarm emails on any ERROR the bot logs, today's and future ones, alongside the existing failed-run alarm (Q9, replacing Q4).
- "Healthy" means the four signals today's alarms watch: runs on schedule, no failed runs, a story posted recently, no repost loop. Together with the earlier decision, any error in the window also makes the verdict not healthy (Q5).
- Counts and the recent list follow the dashboard's own time range, default 7 days, limited by the 30-day log retention (Q6).
- Nothing more is needed for a stale or broken dashboard: the `missed-runs` alarm and the "unknown" verdict are enough (Q7).
- The logging review delivers a written review in the repository plus the code changes that follow from it (Q8).

Does this all look correct before I generate the requirements artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
