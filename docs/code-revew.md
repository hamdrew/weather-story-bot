# Code Review Checklist

Use this checklist when reviewing changes to Weather Story Bot. Treat the
active OpenSpec proposal, design, specifications, and task list as the source
of truth. Review only the changed scope and its directly affected behavior.

## Review process

- [ ] Identify the active OpenSpec change and read its relevant proposal,
      design, specifications, and tasks before judging implementation.
- [ ] Confirm every changed behavior is covered by an OpenSpec requirement or
      is a necessary, narrowly scoped implementation detail.
- [ ] Inspect the complete diff, including tests, configuration, workflows,
      generated artifacts, and deleted or renamed files.
- [ ] Run the repository checks required by `AGENTS.md` when the environment
      permits; distinguish tool failures from product defects.
- [ ] Report only actionable findings, ordered by severity. For each finding,
      include severity, explanation, concrete impact, and file/line reference.
- [ ] If no issues are found, say so explicitly and list residual risks or
      untested assumptions.

## Correctness and contracts

- [ ] Verify NWS request URLs, headers, content negotiation, response-envelope
      validation, item validation, pagination handling, and canonical identity.
- [ ] Verify Telegram request types, caption/entity construction, Unicode and
      grapheme handling, message limits, edit behavior, and one-call-per-
      reservation behavior.
- [ ] Verify AWS resource names, parameters, regions, tags, environment
      boundaries, IAM actions, trust policies, and CloudFormation/SAM syntax.
- [ ] Check state transitions, leases, conditional writes, immutable history,
      run-result classification, retries, deferrals, idempotency, and duplicate
      publication protection.
- [ ] Check expiration, omission, revision hashing, image retention, staging
      cleanup, checksum verification, and recovery behavior.

## Security and privacy

- [ ] Confirm no tokens, credentials, secrets, private chat/message IDs,
      token-bearing URLs, raw request/response bodies, headers, stack traces,
      story content, image metadata, or sensitive operational identifiers are
      exposed in source, logs, tests, fixtures, docs, artifacts, comments, or
      command output.
- [ ] Verify secret retrieval uses the intended secret version and exact ARN,
      with bounded caching and safe rotation/rollback behavior.
- [ ] Verify dev Telegram operations are mock-only and staging/prod channels,
      alert recipients, buckets, tables, secrets, and roles are isolated.
- [ ] Verify IAM is least privilege, runtime roles cannot assume one another,
      committed history cannot be runtime-deleted, and S3 access is TLS-only
      with the required public-access controls.
- [ ] Verify GitHub workflows use minimal permissions, safe concurrency, and
      full commit-hash action pins with inline release-tag comments.

## Resilience and operational behavior

- [ ] Check bounded timeouts, retry budgets, `Retry-After` handling, shutdown
      reserve, story caps, run-budget deferrals, and normal failed-run return
      behavior after durable persistence.
- [ ] Check handling of connection failures, timeouts, HTTP 4xx/429/5xx,
      malformed siblings, partial downloads/uploads, checksum failures,
      Telegram ambiguity, persistence failures, and stale reservations.
- [ ] Verify alerts are sanitized, fingerprinted, deduplicated, cooldown-
      aware, severity-correct, and routed through the intended SNS/fallback
      path without loops or public-channel leakage.
- [ ] Verify metrics use only approved low-cardinality dimensions and that
      dashboards and alarms distinguish a healthy empty run from no run.

## Tests and coverage

- [ ] Confirm tests cover normal behavior and failure paths, including security
      boundaries, validation failures, retries, partial or ambiguous external
      outcomes, persistence failures, and recovery paths.
- [ ] Review generated reports under `coverage/`: HTML, LCOV, Cobertura XML,
      and JSON. Assess missing lines and branches by risk and behavior; do not
      demand 100% coverage for low-value defensive or unreachable code.
- [ ] Check fixtures are sanitized, versioned, representative, and free of
      credentials or sensitive operational identifiers.
