# Domain Design — Questions

Inputs: `inception/requirements-analysis/requirements.md` (FR1 to FR6, NFR1 to NFR6) and the code knowledge
base (`architecture.md`, `component-inventory.md`). Today logging is set up in the Lambda Handler
(`JsonFormatter`, request context), each module logs with a fixed message and `extra`, and the Runtime Stack
(`infra/monitoring.tf`) owns two metric filters on exact message text and five alarms.

## Q1. [Architect] Where does each warning and error kind's stable identity (FR2.3) live?

A. A new Log Events component: one catalogue of event codes (for example `nws.retry`, `telegram.delete_failed`); every WARNING and ERROR call passes its code, and the formatter writes it as an `event` field
B. Each module keeps its own codes as constants next to its log calls; no shared catalogue
C. No codes: the kind is the logger name plus the level
X. Other (please specify)

[Answer]: A

## Q2. [Architect] What do the alarms and the dashboard read, instead of message text (FR5.1)?

A. Structured log fields: metric filters and dashboard queries match `$.event` and `$.level`, never `$.message`
B. Metrics the code emits directly in CloudWatch Embedded Metric Format (counts such as stories posted, warnings, errors), with the logs used only for the recent list
C. Both: emitted metrics for the counts that alarms need (stories posted, warnings, errors), and structured log fields for the kinds and the recent list
X. Other (please specify)

[Answer]: A

## Q3. [Architect] How is "an alarm still has its signal" (FR5.2) proven?

A. One shared file lists every event code and every signal (metric name, filter); the Python code and the Terraform both read it, and a test fails if either side drifts from it
B. A Python test reads the Terraform files and checks each metric filter's pattern against the codes the code can emit
C. A Terraform test checks the filters against a hard-coded list kept in the test
X. Other (please specify)

[Answer]: A

## Q4. [Architect] Who owns the dashboard and the new alarms?

A. The existing Runtime Stack (`infra/`), in a new monitoring file alongside today's alarms, so start/pause and both environments work the same way
B. A separate Terraform root just for monitoring
X. Other (please specify)

[Answer]: A

## Q5. [Architect] Full event catalogue, or a lighter design? (raised at the gate)

The owner asked whether a shared catalogue is standard practice. Stable event names in a structured field,
alerted on instead of message text, are; a shared file read by Python and Terraform with an enum and
cross-side drift tests is more than one small Lambda needs.

A. Lighter: each WARNING and ERROR call (and the "message sent" INFO call) passes a plain `event` string; Terraform matches `$.event` for the three signals that read a specific event and `$.level` for the warning and error alarms; a Python test and a Terraform test guard it; no catalogue file or enum
B. Keep the full catalogue (Q1 A, Q3 A)
X. Other (please specify)

[Answer]: A. This replaces Q1 A and Q3 A; Q2 A and Q4 A stand.

## Consolidated Summary Confirmation

- A new Log Events catalogue gives every warning and error kind a stable event code; each WARNING and ERROR call passes its code, and the formatter writes it as an `event` field (Q1). The catalogue also covers the INFO events a signal reads, such as a story being sent to Telegram, so `quiet` and `repost-loop` stop matching message text. A record with no code (for example from a third-party logger such as httpx) is still counted, with its logger name as its kind.
- Alarms and the dashboard read only structured log fields (`$.event`, `$.level`), never `$.message` (Q2).
- One shared signal file lists every event code and every signal; the Python code and the Terraform both read it, and an offline test fails if either side drifts from it (Q3).
- The dashboard and the new alarms live in the existing `infra/` root, in a new monitoring file beside today's alarms, so start/pause and both environments work the same way (Q4).

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
