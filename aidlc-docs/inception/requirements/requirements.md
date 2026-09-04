# Weather Story Bot Requirements

> **Status:** AI-DLC sovereignty amendment approved on 2026-09-04. The Personal-Project and
> staging-approval simplification amendments remain active. OpenSpec and the legacy `docs/` tree,
> including their migration mapping, are retired; AI-DLC is the sole active governance framework.

## Intent Analysis

- **User request**: Complete a safe personal-project MVP through AI-DLC, retain selected AWS
  learning goals, and defer production-maturity controls until broader channel publication makes
  them valuable.
- **Request type**: System-wide completion and enhancement of an existing service.
- **Scope estimate**: MVP publication and staging operations, with explicit public-readiness and
  production-maturity deferrals for advanced delivery, cost, recovery, and release controls.
- **Complexity estimate**: Moderate-to-complex because publication safety, secrets, durable state,
  and AWS deployment remain material, while multi-operator and mature-production controls are
  deferred.
- **Requirements depth**: Comprehensive.

## Governing Decisions

1. AI-DLC owns requirements reconciliation, design, construction planning, implementation, and
   verification for the selected scope.
2. Approved AI-DLC artifacts are the repository's sole active specification and SDLC authority.
   Retired OpenSpec artifacts are historical Git provenance only and require no active mapping,
   successor label, inventory, or traceability obligation.
3. Current code is the implementation baseline and approved AI-DLC requirements are the target
   contract. Behavior changes are approved through AI-DLC.
4. GitHub shall remain the only source-code repository and source of truth. AWS CodeConnections
   shall provide the exact selected GitHub revision to CodePipeline as a read-only source artifact;
   CodeBuild shall not receive GitHub write permission or require a mirrored repository.
5. Full Security Baseline and Property-Based Testing extension enforcement is enabled. Resiliency
   Baseline enforcement is disabled. Enabled blocking requirements must be incorporated and
   verified at every applicable stage.
6. Current repository contributor instructions remain mandatory, including feature-branch work,
   focused tests, `make format` after Python edits, `make check`, redaction, and the requirement for
   separate human authorization before external changes outside the approved deployment policy.
7. AWS CodePipeline and CodeBuild shall provide one instructive, reproducible staging delivery path.
   Local development remains mock-only, and every staging mutation requires the owner's explicit
   cloud-native approval. Production remains represented in configuration/template contracts but is
   not deployed or activated until a separately approved public-readiness stage.
8. AI-DLC requirements, stories, application design, units, construction artifacts, tests, and
   audit history provide the required traceability. Personal MVP scope changes are explicitly
   simplified or deferred to a named maturity stage without inherited external task labels.

## Product Context

Weather Story Bot retrieves visual Weather Stories from the National Weather Service, retains the
current trusted story and image state, and publishes eligible new or changed stories as Telegram
photo messages. It is not an emergency-alerting service. The implementation is multi-office-ready,
but only the Milwaukee/Sullivan office (`MKX`) is active for the MVP.

The repository already contains validated configuration models, NWS ingestion, DynamoDB state
contracts, two-phase image retention, Telegram publication logic, scheduled processing, Lambda
entry points, and extensive network-independent tests. Deployable runtime composition, alerting,
office-information management, AWS SAM infrastructure, Infracost visibility, deployment/release
automation, and deployed verification remain incomplete.

## Goals

- Publish each eligible current MKX Weather Story promptly without avoidable duplicates.
- Preserve current story/image facts and bounded operational history for reconciliation and review.
- Treat ambiguous Telegram outcomes conservatively rather than claiming exactly-once delivery.
- Deploy an isolated, observable, recoverable AWS workload using SAM and CloudFormation.
- Exercise core AWS concepts through SAM, Lambda, DynamoDB, S3, Scheduler, CloudWatch, SNS,
  Secrets Manager, CodeConnections, CodePipeline, CodeBuild, and CloudFormation change sets.
- Provide reproducible staging delivery with proportionate test, security, cost-visibility, and
  environment controls while preserving an explicit human/agent authority boundary.

## Non-Goals

- Enabling an office other than MKX for the MVP.
- Backfilling historical NWS stories or retaining a source-revision archive.
- Providing an end-user analytics interface.
- Guaranteeing exactly-once external Telegram delivery.
- Introducing SQS, Terraform, a public image bucket, or cross-Region replication.
- Mirroring or duplicating the GitHub source repository into an AWS-hosted Git repository.
- Allowing CodeBuild or the deployment pipeline to write source changes back to GitHub.
- Applying any production change without a human approval recorded by the cloud control plane.
- Treating Infracost estimates as actual billing data or as a replacement for AWS Budgets.
- Deploying or activating production during the personal MVP stage.
- Requiring enterprise-style release provenance, formal recurring recovery exercises, exhaustive
  cloud-test matrices, or custom cost-policy infrastructure before public-channel readiness.

## Phased Operational Maturity

1. **Personal MVP (current selected scope):** one owner and initial consumer; local mock-only
   development; one real isolated staging environment; actionable private Telegram alerts with
   SNS/email fallback; a lean staging pipeline; cost visibility; focused verification; PITR and a
   documented manual restore procedure.
2. **Public-channel readiness (deferred):** first production deployment/activation, production human
   approval and non-publishing checks, richer release provenance, and a completed recovery exercise.
   This stage requires a separate AI-DLC approval before any production mutation or Telegram effect.
3. **Production maturity (deferred):** recurring backups/recovery exercises, broader evidence and
   release automation, multi-office operational readiness, and additional controls justified by
   audience size, operator count, release frequency, or observed risk.

Only Personal MVP requirements block completion of the current scope. Deferred requirements remain
visible and traceable but do not block the MVP.

## Functional Requirements

### FR-01: Configuration and Office Registry

1. The service shall use versioned, non-secret configuration validated through the existing
   Pydantic models.
2. The office registry shall contain the versioned NWS office seed set and support NWS metadata,
   coordinates, derived IANA timezones, active state, and environment-specific destinations.
3. Only MKX shall be active for the MVP. Inactive offices shall not require destinations.
4. Dev Telegram publication and alert operations shall remain mock-only. Staging and production
   configuration shall remain isolated and non-overlapping.
5. Telegram secrets shall conform to the versioned secret schema and reside only in Secrets
   Manager values, never repository configuration.

### FR-02: NWS Retrieval and Normalization

1. Each publisher run shall process exactly one configured active office.
2. NWS requests shall use identifying headers, bounded deadlines, and the existing classified retry
   policy for `404`, `429`, `5xx`, connection, and timeout outcomes.
3. The collection envelope shall be complete and unpaginated. An empty valid collection shall be a
   successful zero-story result.
4. Items shall be independently validated so malformed siblings are quarantined with bounded safe
   metadata while valid siblings continue.
5. Story identity shall remain office-scoped using the UUID derived from the canonical source
   download URL. Cross-office UUID reuse shall not merge identities.
6. Material revision detection shall use normalized story fields and the verified image digest.

### FR-03: Durable Story and Operational State

1. DynamoDB shall maintain current office and current story projections plus immutable,
   TTL-bounded operational records for runs, quarantines, deferrals, attempts, and transitions.
   Alert fingerprint, cooldown, aggregation, and delivery state shall not be stored in DynamoDB.
2. Current story records and their current image references shall remain after story expiration.
   Superseded source revisions shall not be archived as current records.
3. Publication reservations, leases, legal transitions, revision ownership, reconciliation, and
   retry eligibility shall be enforced with conditional or transactional writes.
4. One reservation shall authorize at most one Telegram API call. Ambiguous attempts shall not be
   retried until an authorized reconciliation records `confirmed_not_received`.
5. Stored metadata and failure reasons shall remain bounded and sanitizer-produced; raw upstream
   or Telegram bodies shall not be retained.
6. Office and story access paths shall use keys and queries, not DynamoDB scans.

### FR-04: Image Retention and Validation

1. Only allowlisted HTTPS NWS image URLs and bounded redirect chains shall be accepted.
2. Downloads shall enforce the streaming byte limit and reject partial, oversized, animated,
   decompression-bomb, unsupported, MIME-mismatched, or invalid-dimension media.
3. Accepted JPEG/PNG images shall be decoded and verified, hashed with SHA-256, staged in S3,
   verified after storage, promoted to a deterministic current key, and conditionally committed to
   current story state.
4. Telegram publication shall revalidate the retained object and digest before making an external
   call.
5. Replaced current images shall be removed by the application; story expiration shall not delete
   current images. Staging orphans and noncurrent versions shall follow configured lifecycle rules.

### FR-05: Telegram Story Publishing

1. Each eligible story shall be represented by one Telegram photo message; revisions shall edit the
   existing photo and caption in place when a prior acknowledged message exists.
2. Captions shall contain the title, story text, and an optional fitting image description. They
   shall not add a source link, office name, timestamp, or companion message.
3. Caption construction shall honor Telegram's post-entity-parsing limit, use explicit entities,
   preserve literal formatting-like characters, truncate on grapheme boundaries, and use a Unicode
   ellipsis when truncated.
4. Telegram outcomes shall be classified as acknowledged, definitively rejected, retryable under
   the bounded policy, or ambiguous. Only definitive eligible failures may receive a new
   reservation.
5. No token, token-bearing URL, chat/message identifier, raw response, or unbounded exception text
   shall be logged or persisted.

### FR-06: Scheduled Processing and Runtime Composition

1. A deployable runtime factory shall load validated packaged configuration and exact
   environment-scoped resource references, then construct NWS, image, DynamoDB, S3, metrics,
   alerting, and Telegram dependencies for `publisher_handler`.
2. Each run shall expire due projections, retrieve one collection, prioritize and order eligible
   work, enforce the 14-minute application deadline and 25-revision cap, persist controlled
   deferrals, and finalize objective counts and status.
3. Item quarantine may yield `success_with_quarantined_items`; capacity or time deferral may yield
   `success_with_deferred`. Unresolved required publication/image work shall make the persisted run
   failed even when the handler returns normally after successful persistence.
4. Collection or persistence failures shall follow their defined handler failure boundary and emit
   bounded CloudWatch metrics. CloudWatch alarm state transitions, not direct application alert
   events, shall initiate operator notifications.

### FR-07: Operations Alerting

1. Application components shall emit bounded metrics and structured logs. CloudWatch alarms and
   optional composite alarms shall be the only trigger for operator notifications; no direct
   application alert-event path or SQS shall be introduced.
2. CloudWatch alarm state transitions, M-of-N evaluation, explicit missing-data treatment, and
   optional composite suppression shall provide alert noise reduction. No custom four-hour
   fingerprint/cooldown/aggregation service is required.
3. A dedicated SNS trigger topic shall invoke a small alert-notification Lambda that renders a
   bounded, redacted message to the dedicated private Telegram alert channel.
4. A definitive Telegram alert-delivery failure shall invoke one separate SNS/email fallback.
   Ambiguous delivery shall be logged and measured without an automatic resend or fallback.
5. Trigger, dispatcher, and fallback failures shall not return to the trigger topic or create a
   notification loop. Alert history/evidence shall use bounded CloudWatch alarm history, logs,
   metrics, SNS evidence, and existing safe run/reconciliation facts rather than DynamoDB alert
   records.
6. Private alerts shall cover actionable failed runs, unresolved ambiguous publication, repeated
   publisher or office-information failures, alert-dispatch/fallback failure, and deployment or
   security-control failure. Routine deferrals, warnings, and individual malformed items shall
   remain dashboard/log signals.

### FR-08: Office Information Management

1. A separate protected, on-demand Lambda shall retrieve current NWS office/region data, create or
   reuse the configured channel invite, create or edit one formatted office-information message,
   pin it, verify the pin, and conditionally update the office current record.
2. It shall have no schedule and no authority to publish stories, create publication attempts, or
   create office audit/snapshot records.
3. Dev shall mock all Telegram management operations. Staging shall use its dedicated channel.
4. Invite links, tokens, and private identifiers shall never enter logs, outputs, fixtures, or
   documentation.

### FR-09: AWS SAM Infrastructure

1. AWS SAM/CloudFormation shall define the Lambda functions, EventBridge Scheduler schedules,
   DynamoDB table, S3 bucket, Secrets Manager references, SNS topics/subscriptions, CloudWatch log
   groups, metrics, alarms, dashboards, AWS Budget, backup controls, and least-privilege IAM roles.
2. Every Python Lambda shall use Python 3.13 on arm64. The publisher shall have a 900-second timeout
   and 1024 MB initial memory allocation.
3. Exactly one disabled `ScheduleV2` schedule shall be created for each active office, initially
   only MKX, using UTC `rate(15 minutes)`, flexible windows off, no retries, 60-second maximum event
   age, an explicit execution role, and an input containing exactly the office ID.
4. Staging resources shall use unique names and mandatory `Application`, `Environment`, and `Owner`
   tags in `us-east-2` within the selected account. Dev remains local/mock-only. Production names,
   parameters, and isolation shall remain validated template/configuration contracts but shall not
   be deployed during Personal MVP.
5. DynamoDB shall enable TTL, 35-day point-in-time recovery, and retain protections. Scheduled
   monthly backups retained for one year are deferred to Production Maturity.
6. S3 shall block all public access, enforce bucket-owner ownership, TLS, SSE-S3, versioning,
   retain protections, seven-day staging expiration, and 30-day noncurrent-version expiration.
7. Runtime and deployment IAM shall follow exact resource, prefix, key-family, version-stage,
   pass-role, source-account, and source-ARN boundaries and deny unrelated access and table scans.
8. Log groups shall have the specified retention and deployment shall configure bounded structured
   logging without sensitive content.

### FR-10: Environment Promotion and Recovery Controls

1. Local development and validation shall be mock-only and shall not create a persistent dev stack.
2. One isolated staging stack shall use dedicated test destinations. Stack creation/updates shall
   leave schedules disabled until staging smoke checks pass and the owner enables them.
3. One CodeConnections → CodePipeline → CodeBuild → CloudFormation path shall consume the exact
   GitHub revision, run required checks, create a staging change set, and execute only that reviewed
   change set. CodeBuild shall have no GitHub write permission or direct application-resource
   mutation path.
4. AI-DLC may plan staging work but shall not approve a staging mutation or directly mutate staging
   resources. Every staging change set, including an in-place change, shall pause for the owner's
   explicit cloud-native human approval after required checks pass; only the controlled
   CloudFormation path may execute that exact approved change set. Classification remains evidence
   for the owner's review; an ambiguous, failed, missing, stale, or mismatched check fails closed
   and requires a new plan.
5. Production deployment and activation are deferred to Public-Channel Readiness. Production
   templates/configuration shall remain validated and isolated; every future production application
   requires cloud-native human approval and execution of the exact reviewed change set.
6. The CloudFormation Console may inspect stacks/change sets and support a documented human-approved
   break-glass procedure, but it is not the normal reproducible deployment path.
7. Stateful resources shall be retained during replacement/deletion and rollback shall not claim to
   reverse accepted Telegram effects.
8. Personal MVP recovery shall use DynamoDB PITR into a new isolated table plus a documented manual
   validation/cutover/rollback procedure. A completed formal recovery exercise, scheduled monthly
   backups, and quarterly exercises are deferred to later maturity stages.

### FR-11: Infracost Estimation and Policy

1. A pinned Infracost CLI shall run non-mutating estimation against the reviewed SAM/CloudFormation
   inputs and record the source revision, target environment, assumptions, unsupported resources,
   and estimated monthly total.
2. Personal MVP shall produce a concise staging cost report for owner review. A custom normalized
   model, baseline freshness/compatibility lifecycle, monthly-delta policy, exception system,
   replaceable pull-request comment, and multi-environment aggregate workflow are deferred.
3. The estimated application total shall remain at or below $100 unless the owner explicitly
   approves a requirement amendment. AWS Budget notifications remain the operational spending
   control; Infracost remains an estimate and learning/visibility tool rather than a universal
   machine-enforced mutation gate.
4. Infracost shall have no AWS application-resource mutation path and shall not receive deployment
   credentials. Missing or failed estimation shall be visible in staging review but does not replace
   SAM validation, change-set review, or AWS Budget controls.

### FR-12: Build, CI/CD, Security, and Release Evidence

1. Dependency resolution shall use the pinned Python and uv versions with committed `uv.lock`.
   Production/package installation shall use `uv sync --locked --no-dev` and fail if the lock would
   change.
2. SAM builds shall use the matching Python 3.13 arm64 build image pinned by immutable digest and
   shall verify packaged native Pillow imports and representative decoding.
3. CI shall run formatting, Ruff, strict mypy, focused example and applicable property tests,
   coverage, SAM validation/build, dependency/license/vulnerability scans, SBOM generation, and a
   concise Infracost estimate as applicable. Tests shall focus on high-risk domain and security
   boundaries rather than exhaustively reproducing every cloud-service permutation.
4. GitHub shall remain the source of truth. An AWS CodeConnections GitHub source action shall use
   the default revision artifact for CodePipeline; Full clone shall remain disabled unless a later
   approved requirement demonstrates a need. Connection access shall be repository and branch
   scoped, and CodeBuild shall have no GitHub write permission.
5. Any retained GitHub Actions shall be pinned to full released commit hashes with inline release
   tags and shall use least-privilege permissions, safe fork behavior, explicit concurrency,
   redaction, and OIDC rather than long-lived AWS credentials.
6. A lean CodePipeline shall orchestrate CodeBuild validation, the Infracost report, SAM
   build/package, staging CloudFormation change-set creation, owner approval, and exact-plan
   execution. Pipeline artifacts shall be encrypted, access controlled, immutable for the execution,
   and retained with bounded lifecycle settings.
7. Personal MVP evidence shall trace the reviewed commit, lockfile, template/artifact digests,
   required test/scan/SBOM results, cost report, target staging environment, change set, recorded
   owner approval, and pipeline execution. Release notes, signed semantic-version tags, extended
   provenance bundles, published release assets, and prior-artifact rollback evidence are deferred
   to Public-Channel Readiness.
8. AI-DLC planning, owner approval, build, and CloudFormation execution shall use distinct
   least-privilege roles and pipeline conditions. A non-human role shall not approve a staging
   mutation, bypass an approval, alter an approved change set, or mutate resources directly outside
   the controlled CloudFormation action.
9. Production workflows, approvals, tags, provenance, rollback, incident procedures, and
   break-glass controls shall be implemented and verified during Public-Channel Readiness before the
   first production deployment; they do not block Personal MVP completion.

### FR-13: Verification

1. Every code change shall add or update focused example-based tests for intended behavior and
   important failure/boundary paths.
2. Deterministic property tests shall cover all identified applicable invariants and complement,
   not replace, concrete critical-path tests.
3. Integration-style tests shall cover the highest-risk application paths with deterministic mocked
   NWS, Telegram, DynamoDB, S3, SNS, clocks, and identifiers. They need not exhaustively enumerate
   equivalent adapter or cloud-policy permutations already covered by focused contract tests.
4. Explicitly opted-in read-only live NWS contract tests may exist outside normal PR commands; they
   shall use bounded requests, require no credentials, and retain no downloaded image.
5. Personal MVP shall use the isolated staging stack for one representative end-to-end smoke path:
   schedule/handler invocation, retained image, Telegram story publish/edit, dedicated private alert,
   definitive-failure fallback, and safe state/log/metric evidence. No ephemeral dev verification
   stack is required.
6. Staging verification may exercise only dedicated test destinations and shall follow FR-10's
   agent/human gate. Drift, rollback, IAM, and service-control verification shall use focused checks
   proportional to the resources and boundaries being changed.
7. Production verification and production Telegram effects are deferred to Public-Channel
   Readiness and require separate human authorization.

### FR-14: AI-DLC Governance

1. AI-DLC state, requirements, plans, user stories, application design, units, construction
   artifacts, tests, and audit history shall be the sole active SDLC/specification system for the
   repository.
2. AI-DLC requirements, story identifiers, unit identifiers, construction artifacts, and tests
   shall provide current-scope traceability; no OpenSpec-derived mapping or successor-label system
   is required.
3. The repository shall contain no active OpenSpec workflow, specification tree, migration inventory,
   or OpenSpec-derived work-label tracking. Git history alone retains historical provenance.
4. Scope, design, and lifecycle changes shall be introduced, reviewed, approved, and recorded
   through AI-DLC artifacts.

## Non-Functional Requirements

### NFR-01: Performance and Resource Bounds

- One office shall be processed per invocation, with a 14-minute processing deadline, 60-second
  completion reserve, and at most 25 changed/new revisions processed per run.
- Network requests, redirects, response metadata, images, decoded dimensions/pixels, captions,
  alerts, stored errors, and log fields shall remain explicitly bounded.
- Metrics shall expose request/run latency and Lambda duration/memory for later tuning.

### NFR-02: Reliability and Delivery Semantics

- The system shall prefer duplicate prevention over automatic retry after ambiguous Telegram
  acceptance.
- Scheduler retries shall remain disabled; recovery occurs through later office polls and durable
  reservation state.
- Conditional writes, immutable transitions, two-phase image commit, retained resources, PITR,
  restore procedures, and proportionate drift controls shall protect state integrity.
- No artifact shall claim that design-time resiliency guidance certifies production readiness.

### NFR-03: Security and Privacy

- Secrets and private identifiers shall never be committed, logged, placed in fixtures, emitted in
  outputs, included in comments/artifacts, or embedded in token-bearing URLs.
- IAM, OIDC, Secrets Manager version-stage access, S3, DynamoDB, SNS, Scheduler, and deployment roles
  shall be least privilege and environment scoped.
- CodeConnections shall be read-only and scoped to the selected GitHub repository and branch.
  AI-DLC planning, owner approval, build, and CloudFormation execution shall use separated roles so
  no single non-human role can bypass a required staging approval gate.
- Public repository workflows shall enforce secret scanning/push protection where available,
  dependency review, CodeQL or equivalent scanning, pinned dependencies/actions, and documented
  vulnerability handling.
- The enabled Security Baseline extension shall be enforced in full and shall not weaken these
  product requirements.

### NFR-04: Observability and Operability

- Structured logs shall use an allowlist of bounded, non-sensitive fields and safe correlation IDs.
- Metrics shall use only `Environment` and `OfficeId` dimensions and include run, discovery,
  publication, ambiguity, image, Telegram, alert, latency, and resource signals.
- Personal MVP shall use a concise dashboard and a small actionable alarm set. CloudWatch alarm
  transitions shall trigger dedicated Telegram alerts, with one SNS/email fallback after definitive
  delivery failure; warnings and routine deferrals remain logs/dashboard signals.
- Schedule enablement, reconciliation, manual restore, secret rotation, and compromised-workflow
  procedures shall be documented and tested proportionately. Recurring recovery and extensive
  operational evidence are deferred to later maturity stages.

### NFR-05: Cost Control

- Estimated aggregate monthly application cost shall not exceed $100 without a documented approved
  exception, and the account-level tagged AWS Budget shall notify at 80% forecast, 100% actual, and
  120% actual spend.
- Personal MVP cost evidence shall identify the reviewed revision, staging environment, assumptions,
  unsupported resources, and estimated total. Advanced baseline/delta policy and exception workflow
  are deferred.

### NFR-06: Maintainability and Reproducibility

- Code shall remain compatible with Python 3.13 and follow the repository's Ruff and strict mypy
  configuration.
- Existing protocols, Pydantic boundaries, boto3 paginators, immutable models, and deterministic
  injected effects shall be preferred over duplicated or ad hoc implementations.
- Dependency, build-image, GitHub Action, Infracost CLI, environment input, source revision, and
  artifact versions shall be pinned and reviewable where applicable to Personal MVP.
- Cloud-hosted deployment shall consume an immutable artifact derived from GitHub without maintaining
  a second repository, and the exact approved change set shall be the one executed.

### NFR-07: Property-Based Testing

- Hypothesis shall remain the selected Python property-testing framework and development dependency.
- Functional design shall identify round-trip, invariant, idempotence, commutativity, oracle,
  induction, easy-verification, and stateful-model properties per unit, or document why none apply.
- Applicable serialization, sanitizer, normalization, state-machine, retry-budget, revision,
  timestamp, image/redirect, policy, and configuration invariants shall have domain-strategy-driven
  property tests.
- Stateful components shall be evaluated against simplified models and generated operation
  sequences with invariants checked after each step.
- Strategies shall generate valid domain objects and boundaries, be reusable where shared, preserve
  Hypothesis shrinking, and avoid meaningless unconstrained primitives for domain inputs.
- CI shall run property tests, preserve seed/counterexample reproducibility, and investigate rather
  than suppress flaky failures.
- Business-critical paths shall retain explicit example-based tests. A newly discovered minimal
  counterexample should become a permanent regression example.

### NFR-08: Security Baseline

- Every persistent store and backup shall use encryption at rest. S3 shall enforce TLS, and all
  AWS, NWS, Telegram, Infracost, package-registry, and GitHub traffic shall use TLS 1.2 or newer.
- Every Lambda entry point shall use centralized structured logging with timestamp, correlation or
  request ID, level, event message/type, and allowlisted bounded context. Runtime roles shall not be
  able to delete or alter log groups, retention, or existing audit records.
- Every handler event, configuration value, external response, identifier, and environment/resource
  reference shall be schema/type/format/length validated before use. Untrusted values shall never
  be concatenated into NoSQL expressions, shell commands, paths, or URLs.
- IAM policies shall use specific actions and resources, separate read and write statements, exact
  environment and version-stage boundaries, scoped trust conditions, and documented exceptions for
  APIs that cannot support resource-level permissions.
- Protected operator functions shall deny by default and verify caller authorization and
  object/environment scope server-side. The service shall expose no anonymous mutation path.
- Runtime components shall use supported versions, no default credentials, no sample services,
  private storage, generic external errors, and Secrets Manager for all bot credentials.
- Security-critical credential, authorization, redaction, integrity, and deployment-gate logic shall
  remain isolated behind dedicated modules or narrowly scoped adapters and shall use defense in
  depth.
- Threat and abuse cases shall include forged Scheduler/operator events, cross-environment resource
  substitution, poisoned NWS content, publication replay, ambiguous-send retry abuse, alert loops,
  secret-bearing diagnostics, workflow modification, and deployment-check bypass.
- Untrusted JSON and artifacts shall use safe schema-validated deserialization. Dependencies, build
  images, release artifacts, and critical retained image data shall have checksum, signature, or
  digest verification appropriate to the source.
- Security-relevant authorization failures, denied cross-environment access, secret-rotation
  failures, workflow-integrity failures, and repeated protected-operation failures shall emit safe
  alerts. Logs shall be retained at least 90 days and application roles shall have no audit-log
  deletion authority.
- Every external call and file/data operation shall have explicit bounded error handling and
  resource cleanup. Entry points shall catch unexpected failures at the top boundary, emit a safe
  structured event, and fail closed without exposing internal paths, stack traces, versions, raw
  inputs, or secrets.

## User and Operator Scenarios

1. **New story**: A valid new MKX story is observed, its image is safely retained, one reservation
   authorizes one photo send, and acknowledged message details update current state.
2. **Changed story**: A material revision safely replaces the current retained image and edits the
   existing Telegram photo/caption without creating a companion message.
3. **Unchanged story**: Reprocessing produces no duplicate publication and leaves stable current
   state intact.
4. **Malformed sibling**: One invalid collection item is quarantined without raw content while valid
   siblings continue and the run records the quarantined outcome.
5. **Ambiguous delivery**: An uncertain Telegram outcome becomes non-retryable, alerts the operator,
   and requires protected reconciliation before a new reservation can become eligible.
6. **Alert failure**: A private Telegram operational alert fails definitively and the separate
   SNS/email fallback is invoked without causing an alert loop.
7. **Office information refresh**: An authorized operator refreshes and pins the staging office
   information message without publishing a story or leaking the invite link.
8. **Staging delivery**: CodePipeline receives the exact GitHub revision through read-only
   CodeConnections; CodeBuild validates/tests/builds SAM, emits scans/SBOM and a concise Infracost
   report, and creates a staging change set that pauses for owner approval.
9. **Routine human-approved staging update**: Required checks pass and the reviewed in-place change
   set pauses until the owner approves its exact execution through the cloud pipeline.
10. **Sensitive human-approved staging update**: A change set adds, removes, replaces, or changes a
    sensitive boundary, so the pipeline pauses until the owner approves it; smoke delivery targets
    only dedicated staging destinations.
11. **Deferred production deployment**: Production configuration/templates remain valid but no
    production resource or Telegram effect occurs until Public-Channel Readiness is separately
    approved and its human-gated controls are implemented.
12. **Manual recovery preparation**: The owner has a documented PITR-to-isolated-table validation,
    cutover, and rollback procedure; formal execution/evidence is deferred until Public-Channel
    Readiness.

## Acceptance and Completion Criteria

The selected scope is complete only when:

1. Every requirement above is implemented or explicitly marked not applicable with approved
   rationale; current-behavior conflicts have separate user approval before behavior changes.
2. AI-DLC design and construction artifacts trace units and tests back to these requirement IDs.
3. All Python changes are formatted and the repository `make check` gate passes at handoff.
4. Relevant SAM, workflow, policy, packaging, security, cost, and integration validations pass in
   their safe authorized context.
5. Every enabled Property-Based Testing rule is compliant or correctly marked not applicable at
   each stage where it applies; blocking findings prevent stage completion.
6. Current scope, design, implementation, and verification artifacts shall trace to approved AI-DLC
   requirement, story, unit, and test identifiers without requiring a retired-framework mapping.
7. No prohibited secret, private identifier, invite link, token-bearing URL, raw payload/response,
   or unsafe diagnostic content appears in source, logs, tests, fixtures, documentation, workflow
   comments, or retained artifacts.
8. A feature branch contains review-ready changes suitable for a ready-for-review pull request.
9. GitHub remains the sole source repository; CodeBuild has read-only source access and no mirrored
   repository or source-write permission exists in AWS.
10. Every staging AWS mutation is executed by the controlled CloudFormation pipeline after required
    checks and recorded owner approval of the exact change set; no non-human role can approve a
    staging mutation or directly mutate resources outside controlled CloudFormation execution.
11. No production mutation or Telegram effect is part of Personal MVP. Public-Channel Readiness
    requires a separate approved amendment and exact human-reviewed production change set.

## Requirements Traceability

| Requirements area                       | Primary AI-DLC source                                          | Baseline evidence                                                                       |
| --------------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Product, ingestion, publishing, history | FR-01 through FR-06 and E-01 through E-03                      | Reverse-engineering business, API, architecture, and code-structure artifacts           |
| Alerting and office information         | FR-07, FR-08, and E-04                                         | Existing state/config contracts; implementation gap recorded in code-quality assessment |
| AWS infrastructure and delivery         | FR-09, FR-10, FR-12, and E-05 through E-06                     | No implemented infrastructure package                                                   |
| Cost estimation                         | FR-11 and US-6.2                                               | No implemented Infracost workflow or evaluator                                          |
| Quality and testing                     | FR-13, NFR-07, `AGENTS.md`, `pyproject.toml`, and CI workflows | Passing baseline of 178 tests and 92.74% line coverage at reverse engineering           |
| AI-DLC governance                       | FR-14 and AI-DLC state/plans/artifacts                         | Approved AI-DLC artifact chain and audit history                                        |
| Security extension                      | SECURITY-01 through SECURITY-15                                | NFR-03, NFR-08, FR-01, FR-03 through FR-05, FR-07, FR-09, FR-12, FR-13                  |

## Reconciliation Notes

- The approved simplification amendment replaces custom alert fingerprints/cooldowns, persistent
  cloud dev, immediate production activation, universal Infracost gating, advanced release
  provenance, exhaustive cloud verification, and recurring recovery exercises with the phased
  requirements above. Detailed scope disposition is recorded in
  `simplification-amendment-impact.md`.
- OpenSpec and the legacy `docs/` tree are retired. Their Git history does not govern current work,
  and no active migration inventory or OpenSpec-derived work-label tracking is required.
- No confirmed requirement requires changing current implemented behavior at this stage. If later
  analysis finds one, construction shall stop at that decision and request separate approval in the
  AI-DLC question-file format.

## Extension Compliance at Requirements Analysis

- **Property-Based Testing**: Enabled in full. PBT-01 through PBT-10 are not directly enforced during
  Requirements Analysis according to the extension's stage matrix; their downstream constraints
  are captured in NFR-07 and the completion criteria.
- **Security Baseline**: Enabled in full. Requirements-stage coverage is recorded below; no blocking
  requirements finding remains.
- **Resiliency Baseline**: Disabled by the latest user decision; its full rules are no longer
  enforced and its mandatory decision questions are superseded.

### Security Compliance

| Rule        | Status    | Requirements-stage rationale                                                                                                           |
| ----------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| SECURITY-01 | Compliant | FR-09, NFR-03, and NFR-08 require encrypted storage/backups and TLS 1.2+ traffic.                                                      |
| SECURITY-02 | N/A       | No load balancer, API Gateway, or CDN is in scope; AWS service audit/operation logging is covered elsewhere.                           |
| SECURITY-03 | Compliant | FR-07, FR-09, NFR-04, and NFR-08 require centralized structured, redacted logging for every Lambda.                                    |
| SECURITY-04 | N/A       | The service has no HTML-serving endpoint.                                                                                              |
| SECURITY-05 | Compliant | FR-01, FR-02, FR-08, FR-09, and NFR-08 require schema and bounded input validation at every boundary.                                  |
| SECURITY-06 | Compliant | FR-09, NFR-03, and NFR-08 define exact-resource least-privilege IAM and trust boundaries.                                              |
| SECURITY-07 | N/A       | No customer-managed VPC, subnet, route table, network ACL, or security group is planned.                                               |
| SECURITY-08 | Compliant | FR-03, FR-08, FR-09, and NFR-08 require deny-by-default operator authorization and environment/object scope.                           |
| SECURITY-09 | Compliant | FR-09, FR-12, NFR-03, NFR-06, and NFR-08 require private storage, supported versions, generic failures, and no defaults.               |
| SECURITY-10 | Compliant | FR-12, FR-13, NFR-03, NFR-06, and NFR-08 require locked dependencies, scanning, SBOMs, and pinned build inputs.                        |
| SECURITY-11 | Compliant | NFR-08 isolates security-critical logic and identifies misuse cases; public API rate limiting is N/A because none exists.              |
| SECURITY-12 | Compliant | FR-01, FR-09, FR-12, NFR-03, and NFR-08 require Secrets Manager and prohibit hardcoded credentials; password/session subrules are N/A. |
| SECURITY-13 | Compliant | FR-03, FR-04, FR-12, NFR-08 require safe deserialization, data/artifact integrity, and auditable changes.                              |
| SECURITY-14 | Compliant | FR-07, FR-09, NFR-04, and NFR-08 require security alerts, dashboards, 90-day logs, and no runtime deletion authority.                  |
| SECURITY-15 | Compliant | FR-02, FR-04 through FR-07, FR-11, NFR-02, and NFR-08 require bounded handling, cleanup, safe errors, and fail-closed behavior.        |
