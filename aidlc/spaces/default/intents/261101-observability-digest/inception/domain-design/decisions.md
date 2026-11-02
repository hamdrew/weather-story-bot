# Architecture Decisions: observability for weather-story-bot

Sources: `inception/requirements-analysis/requirements.md` and `domain-design-questions.md` (Q2, Q4, Q5).

## ADR-001: Stable event names as plain strings at the call site

- **Context**: Three alarms match exact log message text, so rewording a message silently breaks them (FR5.1). Every warning and error, today's and future, needs a kind that survives rewording (FR2.3). Stable event names in a structured field are common practice (Elastic Common Schema `event.action`, OpenTelemetry `event.name`).
- **Decision**: Each WARNING and ERROR call, and the message-sent INFO call, passes `extra={"event": "<name>"}` (for example `nws.retry`). There is no shared catalogue file or enum (Q5 A, replacing Q1 A).
- **Consequences**: Positive: smallest change to each call; no new module for callers to import; ordinary Python strings pass `ty check`. Negative: the three signal names appear in both the code and the Terraform, held together by tests (ADR-003) rather than one file; nothing but a test stops a typo in a non-signal event name.
- **Alternatives Rejected**: A shared JSON catalogue read by Python and Terraform with an `EventCode` enum (Q1 A, Q3 A): sound for many services and teams, but more machinery than about 14 log calls in one Lambda need, and a JSON file cannot give typed codes without a mirrored enum. Per-module constants (Q1 B): adds indirection without a single list. Logger name plus level (Q1 C): two different warnings in one module would be one kind.

## ADR-002: Alarms and the dashboard read structured log fields only

- **Context**: The signals need a source that survives rewording, within about $5 a month (NFR1), with httpx as the only runtime dependency.
- **Decision**: Metric filters and dashboard queries match `$.event`, `$.level` and `$.logger`, never `$.message` (Q2 A). The warning and error-log alarms count by `$.level` alone, so they need no event names at all.
- **Consequences**: Positive: one mechanism, no new runtime code paths or dependencies; uses the JSON lines the bot already writes; metric filters are free. Negative: the formatter's field names become a contract (covered by ADR-003); dashboard queries are billed by bytes scanned.
- **Alternatives Rejected**: Emitted metrics in Embedded Metric Format (Q2 B): a second way to publish signals and per-metric cost. Both (Q2 C): two mechanisms to keep in step.

## ADR-003: Two small drift tests instead of a shared file

- **Context**: FR5.2 needs an automated, offline test that fails when a change would leave an alarm or widget without its signal.
- **Decision**: A Python test checks every WARNING and ERROR call in `src/` passes an event, that the formatter writes it, and that the message-sent and ambiguous-stories code paths emit their exact names. A Terraform test (mock provider) checks no filter reads `$.message`, the signal filters use those exact names, and `alarm_names` lists every metric alarm. The errors and missed-runs alarms read Lambda metrics and are exempt from the event check (Q5 A, replacing Q3 A).
- **Consequences**: Positive: each test stays in its own toolchain; nothing has to be shipped in the zip or read across folders. Negative: the three names are written in both tests; renaming one means changing code, Terraform and both tests together, which the tests make loud rather than silent.
- **Alternatives Rejected**: One shared file read by both sides (Q3 A): needs the file in the zip and a cross-folder Terraform read. A Python test that parses `.tf` files (Q3 B): brittle HCL parsing.

## ADR-004: Monitoring stays in the existing Terraform root

- **Context**: The new alarms must join start/pause (FR5.4) and both environments; production deploys are pipeline-only.
- **Decision**: The dashboard and the new alarms live in `infra/`, in a new monitoring file beside today's alarms (Q4 A).
- **Consequences**: Positive: one plan and deploy; `alarm_names`, the alerts topic and per-environment naming are reused. Negative: `infra/` grows; monitoring changes ride the same plan as Lambda changes.
- **Alternatives Rejected**: A separate monitoring root (Q4 B): a second state, backend and pipeline step, and a cross-root dependency on the log group and topic.

## ADR-005: The formatter moves out of the Lambda Handler and never raises

- **Context**: The line shape is now a contract that alarms depend on (ADR-002). A formatter that raises loses the record.
- **Decision**: Today's `JsonFormatter` and request-context factory move into a LogFormatter component, keeping today's fields (`time`, not `timestamp`). It only writes; it never validates an event name and never raises.
- **Consequences**: Positive: the shape can be tested on its own; the handler shrinks; no record is ever lost to the formatter. Negative: one more module; a wrong event name is caught only by tests, not at run time.
- **Alternatives Rejected**: Leaving it in `handler.py`: mixes the contract with orchestration. Validating names in the formatter: an exception in a formatter drops the record.

## ADR-006: The verdict comes from two composite alarms

- **Context**: FR1.1 needs a HEALTHY / NOT HEALTHY / UNKNOWN verdict that mirrors alarm state. A CloudWatch dashboard cannot compute a value from alarm state on its own.
- **Decision**: Two composite alarms with no actions: `unknown` (the `missed-runs` alarm in ALARM, or any health alarm in INSUFFICIENT_DATA) and `not-healthy` (`errors`, `quiet`, `repost-loop` or the error-log alarm in ALARM). An alarm-status widget shows both at the top; both OK reads as healthy, and `unknown` is placed first so it wins.
- **Consequences**: Positive: the verdict uses alarm state directly, with no extra code; no extra emails, since the composites have no actions. Negative: about $0.50 a month each per environment (about $2 for both environments together), within NFR1; the widget shows two alarm states rather than one word, so the wording comes from the alarm names and descriptions.
- **Alternatives Rejected**: A custom widget backed by a Lambda: more code and cost. Showing only the individual alarms: the owner would have to combine them in their head, against NFR2.
