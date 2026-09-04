# U-01 NFR Design Plan

## Scope

Translate U-01's approved non-functional requirements into logical patterns and components for
protected office-information management, private alert dispatch, fingerprint state, and safe
observability. Concrete AWS resources and IAM remain deferred to Infrastructure Design.

## Design Checklist

- [x] Define U-01 resilience, scalability, performance, and security patterns.
- [x] Define logical components, their narrow interfaces, and permitted information flow.
- [x] Define pattern-level acceptance evidence and PBT carry-forward.
- [x] Validate Security Baseline applicability and N/A determinations.

## NFR Design Questions

### Question 1: Resilience Patterns

Which failure-handling pattern should U-01 use for outbound alert delivery?

**Recommendation: A.** A classified-outcome policy with one conditional fallback preserves
objective state and avoids notification loops or duplicate private alerts.

A) **Recommended** — Classify acknowledgement, definitive failure, and ambiguity; allow one
fallback only for definitive failure and terminate all fallback/dispatcher failures locally

B) Use an unbounded retry loop around Telegram and fallback delivery

C) Treat every non-acknowledged result as confirmation of non-delivery

X) Other (please describe after the `[Answer]:` tag below)

### Question 2: Scalability Patterns

Which concurrency pattern should protect four-hour alert cooldown decisions?

**Recommendation: A.** CloudWatch alarm state transitions suppress repeated actions for persistent
CloudWatch-originated conditions, while an atomic per-fingerprint compare-and-update pattern covers
application-originated and cross-source events that require the approved four-hour policy.

A) **Recommended** — Use CloudWatch state-transition actions for CloudWatch-originated suppression;
use atomic per-fingerprint state with bounded counters for application/cross-source cooldown,
aggregation, and deterministic policy decisions

B) Use one process-local in-memory cooldown cache

C) Serialize all alert types through one global mutable lock

X) Other (please describe after the `[Answer]:` tag below)

### Question 3: Performance Patterns

How should U-01 allocate time across its external interactions?

**Recommendation: A.** A deadline-propagation pattern preserves the invoking Lambda budget and
makes timeout outcomes safe and testable rather than permitting one dependency to consume all time.

A) **Recommended** — Propagate a remaining deadline to each boundary and refuse a new operation
when insufficient time remains for its bounded attempt

B) Give every boundary the full Lambda timeout independently

C) Allow external adapters to use their own unlimited default timeouts

X) Other (please describe after the `[Answer]:` tag below)

### Question 4: Security Patterns

Where should U-01 enforce data minimization and protected-operation authorization?

**Recommendation: A.** Validate at each trust boundary, normalize to safe domain values before
persistence/rendering, and sanitize once at the observation boundary; this fails closed and avoids
duplicated redaction logic.

A) **Recommended** — Use boundary validation, canonical safe-domain models, opaque protected
references, and a single allowlisted sanitizer/schema before logs, metrics, or results

B) Let each downstream adapter decide which fields to redact

C) Permit raw payloads internally and sanitize only before external publication

X) Other (please describe after the `[Answer]:` tag below)

### Question 5: Logical Components

Which logical component split should implement the U-01 patterns?

**Recommendation: A.** Separate pure policy/transform components from state and external ports,
which keeps behavior deterministic for property tests and preserves the existing composition boundary.

A) **Recommended** — Use a command validator, office-refresh coordinator, event normalizer,
fingerprint policy, alert renderer, sanitized observation mapper, and narrow state/Telegram/SNS/NWS
ports

B) Put validation, persistence, rendering, and external calls in one Lambda handler

C) Add a queue, cache, and independently deployed dispatcher service now

X) Other (please describe after the `[Answer]:` tag below)

## Extension Constraints

- SECURITY-01 through SECURITY-15 remain enforced where applicable; SECURITY-02, SECURITY-04, and
  SECURITY-07 remain N/A under the approved architecture.
- PBT-01 and PBT-09 decisions remain binding; NFR Design must preserve the identified stateful and
  deterministic properties for Code Generation. PBT-02 through PBT-08 and PBT-10 are deferred by
  stage matrix.
- Resiliency Baseline is disabled; the patterns here implement approved product requirements, not
  the disabled extension.
