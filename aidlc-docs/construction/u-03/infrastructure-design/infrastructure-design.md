# U-03 Infrastructure Design

## Staging Resource Map

| Logical boundary       | Staging SAM/CloudFormation mapping                                                          | Required controls                                                                                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Publisher runtime      | Dedicated Python 3.13 arm64 Lambda                                                          | 1024 MB, 900-second timeout, explicit environment bindings, bounded logging, no public URL, and a role distinct from protected operations.                                  |
| Reconciliation runtime | Dedicated protected Lambda or explicit protected handler binding                            | Trusted IAM invocation only; exact current-state key family; no event-supplied authority.                                                                                   |
| U-01 operations        | Existing dedicated office and alert Lambdas                                                 | Preserve 120/30-second bounds, reserved office concurrency of one, SNS-only alert subscription, and zero async retries for alert dispatch.                                  |
| Durable state          | One encrypted DynamoDB table                                                                | TTL, 35-day PITR, retain/update-replace protections, exact partition/key-family conditions, and no scan grants.                                                             |
| Current media          | One S3 bucket                                                                               | Block Public Access, bucket-owner enforced ownership, TLS-only policy, SSE-S3, versioning, retain protections, seven-day staging expiry, and 30-day noncurrent expiry.      |
| Scheduled entry        | One Scheduler `ScheduleV2` per configured active office                                     | Disabled initially, UTC `rate(15 minutes)`, flexible window off, no retry, 60-second maximum event age, explicit schedule role, and input containing exactly the office ID. |
| Secrets                | Environment-scoped Secrets Manager references                                               | Exact resource ARN and `AWSCURRENT` version-stage access; values never become parameters, outputs, logs, or evidence.                                                       |
| Alerts and evidence    | Existing encrypted trigger/fallback SNS topics; CloudWatch logs, metrics, alarms, dashboard | CloudWatch-only trigger publishing, independent fallback, retained logs, no self-notification action on dispatcher failure, and bounded dimensions.                         |
| Recovery preparation   | DynamoDB PITR and documented isolated restore contract                                      | Restore target is separate; retained source is not overwritten; validation/cutover/rollback requires owner-controlled procedure.                                            |
| Package boundary       | SAM source/package inputs and immutable build evidence outputs                              | Locked dependencies, pinned arm64 inputs, SBOM/scan/validation summaries; no deployment role or approval capability in U-03.                                                |

## IAM and Trust Boundaries

- Each Lambda has a distinct execution role. Publisher access is restricted to its state key family,
  media prefix, exact public Telegram secret version, safe logs/metrics, and necessary service calls.
- Reconciliation and office-information roles receive only protected current-state and exact secret
  permissions appropriate to their handler. Alert dispatch receives only its private alert secret,
  fallback publish, trigger subscription, and safe observations.
- Scheduler assumes only its execution role, which may invoke only the publisher. The scheduler event
  cannot choose a function, secret, destination, or resource.
- Roles are tagged with `Application`, `Environment`, and `Owner`; runtime roles lack CloudFormation,
  IAM pass-role, schedule enablement, source-repository write, and approval permissions.
- CloudWatch and SNS resource policies use exact source account and source ARN conditions. S3 and SNS
  policies deny non-TLS transport. No table role receives `Scan`.

## Observability and Alarm Design

Publisher log groups are retained at least 90 days and receive only structured safe records. Metric
filters or emitted metrics cover failed runs, unresolved ambiguity, image/media failures, schedule
or invocation rejection, runtime construction failure, duration, and memory. Actionable failure
alarms use explicit missing-data treatment and publish only to the encrypted trigger topic.

The existing office-failure alarm remains an M-of-N alarm. The alert-dispatch failure alarm records
failure/ambiguity/rejection but has no notification action, preventing a loop. Routine deferrals and
malformed-item quarantine remain log/dashboard signals. A concise dashboard contains run,
publication, ambiguity, image, alert, latency, duration, and memory views using only `Environment`
and `OfficeId` dimensions.

## Environment and Networking

The stack is restricted to `us-east-2` and uniquely named/tagged for staging. Dev has no persistent
stack and remains mock-only. Production parameter/configuration contracts are isolated and valid but
are not deployed or activated. No API Gateway, load balancer, Function URL, CDN, public bucket,
customer-managed VPC, SQS, or public inbound path is created. AWS, NWS, Telegram, and package
traffic uses TLS 1.2 or newer.

## Security and Extension Compliance

SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, and SECURITY-08 through SECURITY-15 are
implemented by the resource and IAM design. SECURITY-02, SECURITY-04, and SECURITY-07 are N/A: no
network intermediary, HTML-serving endpoint, or customer-managed network exists. PBT-01 properties
remain code-generation obligations and PBT-09 remains compliant. Resiliency Baseline is disabled.
No blocking security finding remains.
