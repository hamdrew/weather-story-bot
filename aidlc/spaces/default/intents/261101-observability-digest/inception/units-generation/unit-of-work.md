# Units of Work: observability for weather-story-bot

Sources: `inception/domain-design/components.md` and `decisions.md` (ADR-001 to ADR-006),
`inception/requirements-analysis/requirements.md`, and the answers in `units-generation-questions.md`
(Q1 A, Q2 A, summary confirmed). One unit is one pull request, deployed and watched before the next unit
builds on it. The change touches paths that already work, so there is no walking skeleton.

| Unit ID | Directory | Kind | Complexity | Components |
|---------|-----------|------|------------|------------|
| U1 | `u1-logging-review` | spec | S | none (a document) |
| U2 | `u2-log-events` | library | M | LogFormatter, NwsClient, TelegramClient, StoryHistory, LambdaHandler, SignalContractCheck (Python half) |
| U3 | `u3-health-dashboard` | service | M | Monitoring (VerdictAlarm, Dashboard: verdict, signal tiles, detail) |
| U4 | `u4-sturdy-alarms` | service | S | Monitoring (Signal, Alarm), SignalContractCheck (Terraform half) |
| U5 | `u5-warnings-and-errors` | service | M | Monitoring (Signal, Alarm, Dashboard: errors and warnings area) |

## U1 `u1-logging-review`

- **Description**: The written review of every log call in `src/weather_story_bot/` (FR6.1, FR6.2).
- **Boundaries**: A document in the repository; no code changes. Its decisions are carried out in U2.
- **Responsibilities**: For each log call: level, message, fields, consistency with the others. Decide the `event` name of every WARNING and ERROR call and the message-sent line; whether any "unusual" pattern (slow run, NWS listing no stories) becomes a new warning; field names to make consistent; that no line carries a secret or a full request body.
- **Deployment model**: Embedded (a Markdown file in the repository; nothing deploys).
- **Implementation notes**: The review's list of event names is the input U2 implements and U4 and U5 filter on.

## U2 `u2-log-events`

- **Description**: Every log line carries a stable `event` name where it matters, from a formatter that is its own module (FR2.1 to FR2.4, FR6.3, Python half of FR5.2).
- **Boundaries**: Python only. No Terraform change, so every existing alarm keeps working on message text until U4.
- **Responsibilities**: Move `JsonFormatter` and the request-context record factory out of `handler.py`, keeping today's fields; add `extra={"event": ...}` to every WARNING and ERROR call and the message-sent INFO line, as U1 decided; make the tidy-up U1 decided; add the Python test that every WARNING and ERROR call in `src/` passes an event and that the message-sent and ambiguous-stories paths emit their exact names.
- **Deployment model**: Embedded in the Lambda zip.
- **Implementation notes**: Message text stays the same in this unit, so today's three message-based filters keep matching while U4 is pending. The formatter never raises.

## U3 `u3-health-dashboard`

- **Description**: The dashboard per environment, with the verdict at the top, built on today's alarms (FR1.1, FR1.3, FR1.5, FR1.6 to FR1.8, NFR2, NFR3).
- **Boundaries**: Terraform in `infra/` only; reads today's five alarms and their metrics. Needs no event names.
- **Responsibilities**: Two composite alarms with no actions (`unknown`, `not-healthy` over `errors`, `quiet`, `repost-loop`); the alarm-status widget at the top; one signal tile per health alarm; detail charts with thresholds; empty and no-data states in words; layout that reads at 1440 x 900 and at 390 px.
- **Deployment model**: Standalone CloudWatch resources in each environment, deployed through the pipeline.
- **Implementation notes**: U5 later adds the error-log alarm to `not-healthy` and the errors-and-warnings area with its totals.

## U4 `u4-sturdy-alarms`

- **Description**: No alarm depends on message text (FR5.1, FR5.3, FR4.2, Terraform half of FR5.2).
- **Boundaries**: Terraform in `infra/` and `infra/tests/`.
- **Responsibilities**: Move the `stories_posted` filter (read by `quiet` and `repost-loop`) and the `nws_ambiguous` filter to `$.event`, keeping metric names, namespaces and thresholds, so the alarms' history carries on; add the Terraform test that every metric filter reads only `$.event`, `$.level` or `$.logger` and never `$.message`, that the three signal filters (`stories_posted`, `nws_ambiguous`) use U2's exact event names, and that `alarm_names` lists every metric alarm. Level-based filters such as U5's pass this rule, so U4 and U5 do not depend on each other.
- **Deployment model**: Changes to existing CloudWatch resources in each environment.
- **Implementation notes**: Deploy only after U2 is live in that environment, or the filters stop matching.

## U5 `u5-warnings-and-errors`

- **Description**: Every warning and error is counted, emailed and shown (FR1.2, FR1.4, FR3, FR4.1, FR5.4).
- **Boundaries**: Terraform in `infra/` and `infra/tests/`.
- **Responsibilities**: A warning filter and alarm on `$.level`, an error-log filter and alarm on `$.level` (ERROR or CRITICAL), both 15-minute period, threshold 1, emailing on ALARM and OK and joining `alarm_names`; add the error-log alarm to `not-healthy`; the errors-and-warnings area (counts by kind and the recent list from Logs Insights over `event`, `level` and `logger`, in the dashboard's time range) and the totals in the verdict area.
- **Deployment model**: Standalone CloudWatch resources in each environment.
- **Implementation notes**: Counting by level needs no event names, but the kinds on the dashboard come from U2's `event` field, and the area sits on U3's dashboard. U5's resources go in a new Terraform file beside `monitoring.tf`; its only edit to `monitoring.tf` is adding its alarms to the `alarm_names` list.
