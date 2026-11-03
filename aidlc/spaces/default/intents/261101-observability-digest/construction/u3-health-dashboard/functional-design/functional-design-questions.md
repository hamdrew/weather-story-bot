# Functional Design Questions: u3-health-dashboard

Sources: `unit-of-work.md` (U3), `requirements.md` (FR1.1, FR1.2, FR1.3, FR1.5 to FR1.8, NFR2, NFR3),
`decisions.md` (ADR-004, ADR-006), `infra/monitoring.tf` (the five alarms), `scripts/set_run_state.py`, and the
CloudWatch dashboard and composite alarm documentation.

Settled without asking, from the requirements and ADRs: the verdict is two composite alarms with no actions
(ADR-006); the dashboard and alarms live in `infra/` (ADR-004); the health signals are `missed-runs`,
`errors`, `quiet` and `repost-loop`, with today's thresholds unchanged (FR1.3, FR5.3); `nws-ambiguous` is not a
health signal and stays out of the verdict until U5's error-log alarm covers it; the page carries no
environment label (FR1.8).

## Q1. [Operations] How should the dashboard's charts show times in America/Chicago?

NFR3 asks for America/Chicago. A chart's `timezone` setting takes only a fixed offset from UTC (for example
`-0600`), not a named zone, so it cannot follow daylight saving time. The console can also show a dashboard in
the browser's local time zone, which does follow it.

A. Leave the charts without a fixed offset and read them in the browser's local time (the console's time zone
   switch set to local). Always right in Chicago, including daylight saving; wrong only if you open the page
   from another time zone.
B. Fix the charts at `-0600` (Central Standard Time). Same on every device, but an hour behind Chicago clocks
   from March to November, and changing it means a pull request twice a year.
X. Other (please specify)

[Answer]: A


## Q2. [Operations] Should an environment with its schedule switched off read UNKNOWN?

`mise run pause` switches off a schedule and its alarm actions, but the alarms keep running. With no runs,
`missed-runs` goes into ALARM, so the verdict reads `UNKNOWN` (FR1.1) for as long as that environment is paused.
That is staging's normal state between your tests.

A. Yes, leave it: the bot is not running, so `UNKNOWN` is true, and it clears itself within an hour of
   `mise run start`.
B. No: add a per-environment setting so an idle environment's verdict ignores `missed-runs` and can read
   `HEALTHY`. Costs a variable and a second rule to keep in step, and hides a stopped schedule on that
   environment's page.
X. Other (please specify)

[Answer]: A
