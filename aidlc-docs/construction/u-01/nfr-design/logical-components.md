# U-01 Logical Components

| Component                    | Responsibility                                                                              | Constraint                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Protected Command Validator  | Validate caller, environment, office, and command.                                          | Reject scheduler, publication, and cross-environment commands before external work. |
| Office Refresh Coordinator   | Coordinate NWS profile, Telegram invite/message/pin, and conditional current-record commit. | No story attempt, snapshot, or unverified reference.                                |
| CloudWatch Alarm Validator   | Validate bounded SNS-delivered alarm transitions.                                           | Reject unknown, malformed, cross-environment, and non-actionable notifications.     |
| Alert Renderer               | Produce one bounded redacted private alert.                                                 | No raw payload, secret, private identifier, URL, or untrusted markup.               |
| Alert Dispatcher             | Make one Telegram attempt and conditional one fallback.                                     | No direct application trigger, custom alert state, resend on ambiguity, or loop.    |
| Sanitized Observation Mapper | Emit safe logs, metrics, and results.                                                       | Allowlisted schema only; production rejects DEBUG.                                  |

## Allowed Information Flow

1. Handler → Protected Command Validator → Office Refresh Coordinator → NWS/Telegram/state ports →
   Sanitized Observation Mapper.
2. CloudWatch/SNS boundary → CloudWatch Alarm Validator → Alert Renderer → Alert Dispatcher →
   Sanitized Observation Mapper.

## Prohibited Coupling

- No component constructs AWS clients, reads secrets, or handles raw/unbounded payloads.
- No component adds a queue, cache, fingerprint policy, cooldown, alert record, or deployable
  service.
- Dispatcher and fallback paths cannot publish to the trigger topic or public Weather Story channel.

## Infrastructure-Design Handoff

Infrastructure Design maps these ports to Lambda handlers, CloudWatch metrics/alarms/history, SNS
trigger/fallback topics, log groups, environment parameters, and least-privilege roles without
adding an application-level alert-state store.
