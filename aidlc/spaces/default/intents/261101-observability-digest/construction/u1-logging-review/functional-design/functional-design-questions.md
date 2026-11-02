# Functional Design Questions: u1-logging-review

Sources: `unit-of-work.md` (U1), `requirements.md` (FR6.1, FR6.2, and the open question on "unusual" patterns),
`decisions.md` (ADR-001 to ADR-005), and a read of every log call in `src/weather_story_bot/` (19 calls in
`handler.py`, `telegram.py`, `nws.py` and `history.py`).

Settled without asking, from the requirements and ADRs: event names are plain strings at the call site
(ADR-001); alarms read only `event`, `level` and `logger` (ADR-002); levels of today's seven warnings and
seven errors stay as they are (FR2.1, FR2.2); no INFO line other than the message-sent line gets an event.

## Q1. [Operations] Should an NWS listing with no active stories become a WARNING?

Today an office whose listing comes back empty logs nothing; the run counts it and carries on. The `quiet`
alarm only fires after `quiet_alarm_days` days without a post. A new WARNING would email you (through the
warning alarm) on the first empty listing and show on the dashboard.

A. No new warning; the `quiet` alarm already covers a long silence, and an empty listing can be normal.
B. Yes: log a WARNING (`nws.no_stories`) for each office whose listing is empty.
C. Log it at INFO only (no email, no dashboard count), so it can be found in Logs Insights.
X. Other (please specify)

[Answer]: A


## Q2. [Operations] Should a slow run become a WARNING?

A run that times out is killed before it can log anything, and the Lambda `Errors` metric already counts it
(the `errors` alarm). A warning could only cover a run that finishes slowly but succeeds.

A. No; timeouts are already covered by the `errors` alarm.
B. Yes: log a WARNING (`run.slow`) when a run finishes after more than a threshold you pick (for example
   half the Lambda timeout).
X. Other (please specify)

[Answer]: B


## Q3. [Operations] Follow-up to Q2: what threshold makes a run slow?

The Lambda timeout is 300 s. The owner asked whether CloudWatch anomaly detection on the Lambda `Duration`
metric would do instead. It is possible (about $0.30 a month per environment), but run time depends mostly
on how many stories a run posts, so the learned band would be wide, and it would be a metric alarm that
needs its own place in the dashboard, `alarm_names` and the verdict: more scope than a logging review
decides. A fixed threshold is a one-line check in the handler.

A. A fixed 150 s (half the timeout): log `run.slow` at WARNING past it.
B. No slow-run signal (revises Q2 to A).
C. No log warning now; note an anomaly-detection alarm on `Duration` as a possible later intent.
X. Other (please specify)

[Answer]: A
