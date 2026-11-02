# Units Generation — Questions

Inputs: `inception/domain-design/components.md` and `decisions.md` (ADR-001 to ADR-006), and
`inception/requirements-analysis/requirements.md`. The team ships one revertible pull request per slice,
deployed and watched before the next builds on it; this change touches paths that already work, so the team
practice calls for no walking skeleton.

## Q1. [Architect] How fine should the units be?

A. Five units, each one pull request: (1) log events: formatter moved out and an `event` name on every warning, error and the message-sent line, with the Python test; (2) health dashboard: verdict composite alarms, signal tiles and detail charts on today's alarms; (3) sturdy alarms: move `quiet`, `repost-loop` and `nws-ambiguous` to `$.event`, with the Terraform test; (4) warnings and errors: the warning alarm, the error-log alarm and the errors-and-warnings area of the dashboard; (5) logging review: the written review and the tidy-up it decides on
B. Three coarser units: logging (1 + 5), dashboard (2 + 4), sturdy alarms (3)
C. One unit for everything
X. Other (please specify)

[Answer]: A

## Q2. [Architect] Where does the written logging review sit?

The scope said the review's findings feed the other work; the requirements also ask for a tidy-up beyond them.

A. First: the review is written before the log-events unit, so its decisions (levels, fields, event names, any new warnings) shape that unit; the tidy-up lands with or after it
B. Last: the other units go first, and the review and tidy-up follow, so the review sees the finished design
C. Alongside: no dependency either way
X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Five units, one pull request each (Q1). Because the review goes first (Q2), its tidy-up moves into the log-events unit, which touches the same log calls anyway; the review unit is the written review alone:
  - U1 `u1-logging-review` (spec): the written review of every log call, with its findings and decisions (event names, levels, fields, any new warnings, secrets check).
  - U2 `u2-log-events` (library): the formatter moved out of the handler, an `event` name on every warning, error and the message-sent line, the tidy-up U1 decides, and the Python test. Depends on U1.
  - U3 `u3-health-dashboard` (service): the verdict composite alarms, signal tiles and detail charts, built on today's alarms. No dependency.
  - U4 `u4-sturdy-alarms` (service): `quiet`, `repost-loop` and `nws-ambiguous` move to `$.event`, with the Terraform test. Depends on U2.
  - U5 `u5-warnings-and-errors` (service): the warning alarm, the error-log alarm (also added to the not-healthy verdict), and the errors-and-warnings area of the dashboard. Depends on U2 and U3.
- The review comes first so its decisions shape the log-events unit (Q2).

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
