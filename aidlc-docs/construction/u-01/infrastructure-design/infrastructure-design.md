# U-01 Infrastructure Design

| Logical component     | AWS mapping                                                                     | Required boundary                                                                      |
| --------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Office refresh        | Dedicated Python 3.13 arm64 SAM Lambda                                          | No schedule/public endpoint; authorized invocation only; dev Telegram is mock-only.    |
| Alert dispatch        | Dedicated Python 3.13 arm64 SAM Lambda subscribed only to the SNS trigger topic | Validate source/alarm/environment before one private Telegram attempt.                 |
| Current office record | Existing isolated DynamoDB table, `OFFICE#{office_id}/CURRENT` only             | Encryption/PITR; conditional exact-key access; no scans or alert-state keys.           |
| Alarm source/evidence | CloudWatch metrics, alarms/composites, dashboard, history, retained logs        | M-of-N and missing-data treatment explicit; only CloudWatch can trigger notifications. |
| Messaging             | Separate SNS trigger and fallback topics                                        | Trigger invokes alert Lambda; fallback publishes only after definitive failure.        |
| Secrets               | Environment-scoped Secrets Manager references                                   | Exact ARN/version-stage access; no secrets in logs, outputs, or evidence.              |

## IAM and Security Boundaries

- Distinct roles use explicit actions/resources and separate read/write statements.
- Office refresh accesses only its current office key, required secret version, and safe logs/metrics;
  it cannot enable schedules, publish stories, or publish SNS alerts directly.
- Alert dispatch receives only its trigger subscription, private alert secret, fallback publish grant,
  and safe logs/metrics. It cannot access public Telegram, alert state, or publish to its trigger.
- Log groups retain at least 90 days; runtime roles cannot delete audit logs.

## Networking

No API Gateway, load balancer, public endpoint, or customer-managed VPC exists. Approved AWS, NWS,
Telegram, and SNS traffic uses TLS 1.2+. SECURITY-02, SECURITY-04, and SECURITY-07 are N/A.
