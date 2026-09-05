# U-03 NFR Requirements

## Capacity and Performance

1. The publisher shall admit one configured active office per invocation, process at most 25 changed
   or new revisions, enforce a 14-minute application deadline, and retain 60 seconds for final
   persistence and safe observation.
2. Each NWS, AWS, Telegram, media, secret, and fallback operation shall receive an explicit bounded
   timeout within the remaining invocation budget. An operation lacking its required allowance shall
   not start.
3. The staging service shall begin with the approved Python 3.13 arm64 configuration and record
   duration, latency, and memory signals for later tuning. U-03 does not claim a production-scale
   throughput target or multi-office operational readiness.

## Reliability and Recovery

1. Current office/story projections and their current media references shall retain conditional or
   transactional integrity. A failed validation, retention, or commit preserves the prior current
   projection.
2. Telegram ambiguity remains terminal until authorized reconciliation; it is not automatically
   retried. U-01 alerting remains one private attempt plus one independent fallback only after a
   definitive failure.
3. Schedules are created disabled and stay disabled until the separately authorized staging smoke
   and owner enablement conditions succeed. Protected office-information operations cannot enable a
   schedule.
4. Personal MVP recovery preparation shall restore PITR into an isolated target, validate it, and
   document cutover and rollback decisions. It shall not overwrite retained source state or claim to
   reverse accepted Telegram effects. Formal recovery exercises are deferred.

## Security, Privacy, and Observability

1. Staging is isolated in `us-east-2`; dev binds mock Telegram ports only; staging and production
   live destinations remain distinct. Production is a validated but undeployed contract.
2. Persistent data and backup resources require encryption at rest; all AWS, NWS, Telegram,
   package-registry, and source-control traffic requires TLS 1.2 or newer.
3. Resource and secret access is exact, environment-scoped, least-privilege, and deny-by-default.
   Event data cannot override configured resource bindings. No public endpoint, network
   intermediary, or customer-managed network is in scope.
4. Every Lambda emits centralized structured observations containing only bounded allowlisted fields
   and safe correlation IDs. No token, private identifier, raw body, token-bearing URL, raw response,
   or unbounded exception may enter output, logs, fixtures, or evidence.
5. CloudWatch alarms—not direct application events—initiate private alert delivery. Metrics use only
   `Environment` and `OfficeId` dimensions; routine warnings and deferrals remain dashboard/log
   signals.

## Maintainability and Evidence

1. U-03 code shall remain compatible with Python 3.13, uv-locked dependencies, Ruff, strict mypy,
   existing typed ports, Pydantic validation, and deterministic injected effects.
2. Reproducible package evidence shall identify the reviewed source revision, lockfile, artifact and
   template digests, validation, SBOM, and scan results without exposing sensitive content.
3. Evidence does not authorize a deployment. U-04 must produce the exact change set and obtain the
   owner's cloud-native approval for every staging mutation.
4. Build/runbook outputs shall be concise and actionable for the single owner. No frontend,
   analytics UI, or additional operator persona is introduced.

## Acceptance Evidence

| Requirement area          | Evidence                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Runtime bounds            | Deterministic tests reject malformed/unconfigured offices and prevent operations without remaining budget.                |
| State/media integrity     | Focused and stateful tests preserve current references across commit, replacement, and rejection sequences.               |
| Isolation/security        | Parsed-template and runtime tests prove exact scope, mock-only dev, secret exclusion, TLS/encryption, and no scans.       |
| Observability             | Tests assert bounded safe observations and CloudWatch-only alert initiation.                                              |
| Package/recovery evidence | Local reproducible-build and document checks prove bounded identity/validation evidence and isolated restore preparation. |

## PBT and Security Compliance

PBT-09 is compliant: Hypothesis is declared, locked, pytest-integrated, shrinking-enabled, and
seed-reproducible. U-03 Functional Design PBT-01 properties are mandatory for Code Generation;
PBT-02 through PBT-08 and PBT-10 apply at their later stages.

SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, and SECURITY-08 through SECURITY-15 are
incorporated. SECURITY-02, SECURITY-04, and SECURITY-07 are N/A because there is no network
intermediary, HTML-serving endpoint, or customer-managed network. No blocking finding remains.
Resiliency Baseline is disabled.
