# Weather Story Bot User Stories

## Story Conventions

- Epics provide navigation and do not carry acceptance criteria.
- Child stories are implementation-ready value slices using the approved persona identifiers.
- Behavioral criteria use Given/When/Then. Policy and evidence criteria use testable bullets.
- Traceability lists every directly supported requirement and relevant numbered scenario from
  `requirements.md`.
- Unless marked otherwise, each story is in the current **Personal MVP** scope. Criteria explicitly
  marked **Deferred** preserve traceability for Public-Channel Readiness or Production Maturity but
  do not block Personal MVP completion.

## Epic E-01: Trusted Weather Story Acquisition

Provide bounded, validated source data and images from the configured NWS office.

### US-1.1: Maintain the Active Office Contract

**As P-02 Owner/Operator/Maintainer, I want a validated versioned office and source contract so that
the service polls only intended offices with safe environment configuration.**

#### Acceptance Criteria

- Given the versioned office seed and environment configuration, when configuration loads, then
  schema, office ID, coordinates, timezone, active state, and destination invariants are validated.
- Given the MVP configuration, when active offices are selected, then only MKX is active and dev
  Telegram operations remain mock-only.
- Invalid, cross-environment, secret-bearing, or unbounded values fail closed without logging their
  raw contents.

**Traceability:** FR-01, FR-02; NFR-01, NFR-03, NFR-08; scenarios 4 and 8.

### US-1.2: Retrieve and Normalize Current Stories

**As P-01 Telegram Subscriber, I want the bot to find each current MKX Weather Story so that I can
receive timely information from the configured official source.**

#### Acceptance Criteria

- Given a valid complete, unpaginated NWS collection, when MKX is processed, then valid current
  stories are normalized deterministically.
- Given an invalid sibling item, when the collection is processed, then the item is quarantined
  with bounded non-sensitive diagnostics while valid siblings continue.
- Given redirects, timeouts, malformed JSON, poisoned content, oversized responses, or upstream
  failures, when retrieval occurs, then explicit bounds and safe failure outcomes apply.

**Traceability:** FR-02, FR-06; NFR-01, NFR-02, NFR-08; scenarios 1, 3, and 4.

### US-1.3: Retain a Verified Story Image

**As P-01 Telegram Subscriber, I want each published story to contain its verified image so that
the visual forecast is useful and trustworthy.**

#### Acceptance Criteria

- Given a changed story with an allowed image, when retention runs, then bytes, media type,
  dimensions, pixels, redirects, and size are validated before an immutable staging object is
  promoted to the current reference.
- Given an invalid or incomplete upload, when reconciliation runs, then current state never points
  at an unverified object and orphan cleanup remains bounded.
- Given a committed image, when Telegram upload begins, then integrity and resource bounds are
  revalidated.

**Traceability:** FR-03, FR-04, FR-05; NFR-01, NFR-02, NFR-08; scenarios 1, 2, and 12.

## Epic E-02: Safe Telegram Publication

Deliver clear story messages while preventing avoidable duplicates and unsafe retries.

### US-2.1: Publish a New Story Once

**As P-01 Telegram Subscriber, I want one photo message for a new story so that the channel is
current without duplicate posts.**

#### Acceptance Criteria

- Given an eligible new revision and a successful reservation, when Telegram acknowledges the
  photo message, then one message is recorded as current with the acknowledged identifiers.
- Given concurrent processing of the same revision, when reservations compete, then at most one
  reservation authorizes a send.
- The publication contains the verified image and bounded safe caption, with no source link,
  office name, timestamp, companion message, or private configuration.

**Traceability:** FR-03 through FR-06; NFR-01, NFR-02, NFR-08; scenario 1.

### US-2.2: Update a Changed Story

**As P-01 Telegram Subscriber, I want a material story revision to update the existing message so
that I see current information without a companion post.**

#### Acceptance Criteria

- Given a materially changed revision with a known current Telegram message, when publication
  succeeds, then the existing photo/caption is edited and current state advances atomically.
- Given unchanged normalized content, when the story is processed again, then no edit or new send
  occurs.
- Given an edit that fails definitively, when the attempt closes, then retry eligibility follows
  the bounded policy and current acknowledged state is not falsely advanced.

**Traceability:** FR-02 through FR-06; NFR-01, NFR-02; scenarios 2 and 3.

### US-2.3: Contain Ambiguous Delivery

**As P-02 Owner/Operator/Maintainer, I want ambiguous Telegram outcomes quarantined so that an
automatic retry cannot create an avoidable duplicate.**

#### Acceptance Criteria

- Given a send whose acceptance cannot be determined, when the attempt closes, then it becomes
  non-retryable, records bounded evidence, and emits an actionable private alert.
- Given an ambiguous attempt, when a later poll observes the same revision, then publication replay
  is denied until protected reconciliation makes a new reservation eligible.
- Retry budgets are bounded and a forged or replayed reservation token cannot authorize a send.

**Traceability:** FR-03, FR-05 through FR-07; NFR-02, NFR-08; scenario 5.

### US-2.4: Render a Safe Bounded Caption

**As P-01 Telegram Subscriber, I want a readable caption that fits Telegram limits so that the
story is understandable and reliably deliverable.**

#### Acceptance Criteria

- Given normalized NWS text containing markup-like or hostile content, when a caption is rendered,
  then explicit formatting is escaped and no untrusted content becomes executable markup or URL
  structure.
- Given text beyond the allowed caption size, when rendering completes, then deterministic
  truncation preserves the permitted title, story text, and optional fitting image description.
- Property tests cover formatting, length, Unicode, and sanitization invariants with concrete
  critical examples retained.

**Traceability:** FR-02, FR-05, FR-13; NFR-01, NFR-07, NFR-08; scenarios 1, 2, and 4.

## Epic E-03: Durable State, Reconciliation, and Recovery

Maintain objective current state and auditable operational history without overstating delivery.

### US-3.1: Record Current State and Append-Only History

**As P-02 Owner/Operator/Maintainer, I want objective current and historical records so that I can
understand what the service observed, attempted, and acknowledged.**

#### Acceptance Criteria

- Current story, office, run, and publication-attempt records use validated key families,
  TTL/retention rules, conditional writes, and explicit immutable transitions; alert cooldown,
  fingerprint, aggregation, and delivery state is not stored in DynamoDB.
- Publication and reconciliation history is append-only; runtime roles cannot rewrite accepted
  audit events or delete audit logs.
- Stored error and context fields are bounded allowlists without raw payloads, responses, tokens,
  private identifiers, or invite links.

**Traceability:** FR-01, FR-03, FR-06, FR-07; NFR-02 through NFR-04, NFR-08; scenarios 3 and 5.

### US-3.2: Reconcile Incomplete Operations

**As P-02 Owner/Operator/Maintainer, I want protected reconciliation for incomplete sends and image
uploads so that state can recover without guessing about external effects.**

#### Acceptance Criteria

- Given an authorized reconciliation request, when caller, environment, object scope, and current
  state are valid, then only allowed immutable transitions are applied and audited.
- Given a forged operator event, cross-environment identifier, stale transition, or unauthorized
  caller, when reconciliation is attempted, then it is denied by default and safely alerted.
- Reconciliation never claims to undo an accepted Telegram effect and never silently retries an
  ambiguous send.

**Traceability:** FR-03 through FR-05, FR-09; NFR-02, NFR-03, NFR-08; scenario 5.

### US-3.3: Prepare a Safe Manual Restore

**As P-02 Owner/Operator/Maintainer, I want a manual PITR restore procedure so that I can recover
history into an isolated target without improvising during an incident.**

#### Acceptance Criteria

- The documented procedure restores DynamoDB PITR into a new isolated table, reapplies non-data
  controls, encryption, tags, access, and retention, and keeps the source retained.
- The procedure defines sampled-record and image-reference validation, blocks cutover on integrity
  or environment mismatch, and provides rollback steps without exposing protected data.
- **Deferred - Public-Channel Readiness:** execute and retain evidence from a formal recovery
  exercise. **Deferred - Production Maturity:** schedule recurring backups and recovery exercises.

**Traceability:** FR-03, FR-04, FR-09, FR-10; NFR-02 through NFR-04, NFR-08; scenario 12.

## Epic E-04: Bounded Operations and Operator Awareness

Run each office predictably and give operators actionable, non-sensitive control and signals.

### US-4.1: Process One Bounded Scheduled Run

**As P-01 Telegram Subscriber, I want scheduled processing to complete predictably so that current
stories are published without runaway retries or resource use.**

#### Acceptance Criteria

- Given the MKX Scheduler event, when the poller runs, then exactly one office is processed within
  the 14-minute deadline, 60-second reserve, and 25-revision cap.
- Given a forged event, retry event, wrong office, or malformed input, when the handler validates
  it, then processing fails closed before external effects.
- Scheduler retries remain disabled and partial outcomes are durably summarized for later polls.

**Traceability:** FR-01, FR-02, FR-06, FR-09; NFR-01, NFR-02, NFR-08; scenarios 1 and 4.

### US-4.2: Deliver Actionable Operational Alerts

**As P-02 Owner/Operator/Maintainer, I want actionable CloudWatch-driven alerts in a dedicated
Telegram channel with an email fallback so that I can respond without alert loops or sensitive
diagnostics.**

#### Acceptance Criteria

- Given an actionable condition, when a CloudWatch alarm enters ALARM according to its M-of-N and
  missing-data policy, then its SNS trigger invokes a small notification Lambda that sends one
  bounded, redacted message to the dedicated private Telegram alert channel.
- Given definitive Telegram alert failure, when the notification Lambda invokes the separate
  SNS/email fallback, then one fallback notification is attempted without returning to the trigger
  topic or recursively producing another Telegram alert.
- Given ambiguous Telegram alert delivery, when dispatch completes, then the outcome is logged and
  measured without automatic resend or fallback. CloudWatch alarm state/history supplies noise
  reduction and evidence; no custom alert fingerprint or cooldown store is used.

**Traceability:** FR-03, FR-06, FR-07, FR-09; NFR-03, NFR-04, NFR-08; scenario 6.

### US-4.3: Observe Service Health Safely

**As P-02 Owner/Operator/Maintainer, I want bounded logs, metrics, alarms, and dashboards so that I can
diagnose behavior without leaking sensitive data or creating unbounded cardinality.**

#### Acceptance Criteria

- Every Lambda entry point emits centralized structured logs with timestamp, request/correlation
  ID, level, event type, and allowlisted bounded context.
- Metrics use only Environment and OfficeId dimensions and cover the bounded signals required to
  operate runs, discovery, publication, ambiguity, images, Telegram, alerts, latency, duration, and
  memory through a concise dashboard and small actionable alarm set.
- Logs are retained at least 90 days; runtime roles cannot delete or alter log groups, retention,
  existing audit records, alarms, or dashboards.

**Traceability:** FR-06, FR-07, FR-09; NFR-03, NFR-04, NFR-08; scenarios 5 and 6.

### US-4.4: Refresh Office Information Safely

**As P-02 Owner/Operator/Maintainer, I want to refresh the pinned office-information message so
that subscribers see current channel context without triggering story publication.**

#### Acceptance Criteria

- Given an authorized staging request, when office information is refreshed, then the dedicated
  message is created or edited and pinned without publishing a Weather Story.
- Local dev remains mock-only, staging uses only its dedicated destination, and destinations cannot
  be substituted across environments.
- **Deferred - Public-Channel Readiness:** production refresh requires its applicable human gate
  after production deployment and activation are separately approved.
- Invite links and private identifiers are used only at the protected boundary and never enter
  logs, fixtures, retained evidence, or public captions.

**Traceability:** FR-01, FR-08, FR-09, FR-10; NFR-03, NFR-08; scenario 7.

## Epic E-05: Secure AWS Infrastructure

Provision isolated, recoverable service resources with least-privilege boundaries.

### US-5.1: Define the Service as SAM Stacks

**As P-02 Owner/Operator/Maintainer, I want complete SAM templates so that staging can be deployed
reproducibly and production contracts remain valid for later public readiness.**

#### Acceptance Criteria

- SAM defines the required Lambdas, schedules, DynamoDB, S3, Secrets Manager references, SNS,
  CloudWatch resources, Budget, PITR/retention controls, and deployment/runtime roles.
- Python Lambdas use Python 3.13 arm64; the publisher uses the specified timeout and memory; one
  disabled ScheduleV2 exists per active office with the required retry and event-age bounds.
- Local dev creates no persistent stack. Staging resources have unique names and mandatory
  Application, Environment, and Owner tags in us-east-2.
- Production names, parameters, isolation, and configuration remain validated contracts, but
  production resources are not deployed or activated during Personal MVP.

**Traceability:** FR-06 through FR-10; NFR-01, NFR-03, NFR-06, NFR-08; scenarios 8-11.

### US-5.2: Protect Durable Resources

**As P-02 Owner/Operator/Maintainer, I want encrypted retained state and images so that deployment
or recovery mistakes do not silently destroy service history.**

#### Acceptance Criteria

- DynamoDB enables TTL, 35-day point-in-time recovery, and retain protection.
- S3 blocks public access, enforces bucket-owner ownership, TLS, encryption, versioning, retain
  protection, seven-day staging expiration, and 30-day noncurrent-version expiration.
- Any change set that replaces, removes, or weakens a stateful resource requires human approval and
  preserves recovery evidence.
- **Deferred - Production Maturity:** scheduled monthly backups retained for one year.

**Traceability:** FR-03, FR-04, FR-09, FR-10; NFR-02, NFR-03, NFR-08; scenarios 11 and 12.

### US-5.3: Enforce Environment-Scoped Identity and Secrets

**As P-02 Owner/Operator/Maintainer, I want isolated identities and secret access so that a
compromise or mistake cannot cross environments.**

#### Acceptance Criteria

- Runtime, build, planning, agent execution, human approval, and CloudFormation execution roles use
  specific actions/resources, scoped trust, pass-role, prefix, key-family, version-stage,
  source-account, and source-ARN conditions.
- Bot credentials reside only in Secrets Manager values conforming to the versioned schema; no
  default or long-lived repository credential exists.
- Cross-environment substitution, privilege changes, secret-access changes, and deployment-role
  changes fail closed and always require human approval.

**Traceability:** FR-01, FR-08 through FR-10, FR-12; NFR-03, NFR-08; scenarios 7, 10, and 11.

## Epic E-06: Lean Staging Cloud Delivery

Move an exact GitHub revision through reproducible cloud validation, approval, and deployment.

### US-6.1: Consume GitHub as the Sole Source

**As P-02 Owner/Operator/Maintainer, I want CodePipeline to consume a read-only revision artifact from
GitHub so that builds are reproducible without a second repository or source-write path.**

#### Acceptance Criteria

- GitHub is the sole source repository and an environment-scoped CodeConnections source action
  emits the default artifact for the selected repository, branch, and commit.
- CodeBuild receives the artifact without GitHub write permission; Full clone and repository
  mirroring are disabled.
- Pipeline records the source revision and artifact digest, and any mismatch or untrusted artifact
  fails closed before build or deployment.

**Traceability:** FR-10, FR-12; NFR-03, NFR-06, NFR-08; scenarios 8 and 11.

### US-6.2: Review Estimated Staging Cost

**As P-02 Owner/Operator/Maintainer, I want a concise exact-revision staging cost estimate so that I
can understand expected spend while practicing AWS cost tooling.**

#### Acceptance Criteria

- A pinned Infracost CLI runs without deployment credentials in CodeBuild against the reviewed
  GitHub artifact and resolved staging SAM inputs without creating AWS resources.
- The concise report records source revision, staging environment, assumptions, unsupported
  resources, tool version, and estimated monthly total for owner review.
- Missing or failed estimation is visible in staging review but is not a universal machine-enforced
  mutation gate; SAM validation, change-set review, and AWS Budget controls remain independent.
- An estimate above $100 requires an approved requirement amendment, while the tagged AWS Budget
  supplies operational notifications based on actual and forecast spend.

**Traceability:** FR-11 through FR-13; NFR-03, NFR-05, NFR-06, NFR-08; scenario 8.

### US-6.3: Produce Reproducible Build and Supply-Chain Evidence

**As P-02 Owner/Operator/Maintainer, I want cloud builds to prove code and artifact integrity so that
only reviewed dependencies and packages can reach a change set.**

#### Acceptance Criteria

- The pipeline uses pinned Python, uv, lockfile, SAM build image digest, Infracost version, actions,
  scanners, and policies; production installs are locked and no-dev.
- CI runs formatting, Ruff, strict mypy, focused example/property/integration tests, coverage, SAM
  validation/build, dependency/license/vulnerability scans, SBOM generation, and applicable policy
  tests.
- Packaged native Pillow import and representative decode are verified, and artifacts/SBOMs/scans
  carry integrity evidence tied to the source revision.
- Unsafe forks, dependency substitution, workflow modification, or poisoned artifacts cannot gain
  credentials or produce trusted release evidence.

**Traceability:** FR-12, FR-13; NFR-03, NFR-06 through NFR-08; scenarios 8 and 11.

### US-6.4: Create and Classify a CloudFormation Plan

**As P-02 Owner/Operator/Maintainer, I want each proposed deployment classified from its actual
change set so that the correct approval gate is selected.**

#### Acceptance Criteria

- CodePipeline/CodeBuild creates a staging CloudFormation change set from the exact revision,
  resolved parameters, artifacts, and passing evidence without executing it.
- Classification detects Add, Remove, Replacement, IAM, permission-boundary, secret-access,
  environment-target, and deployment-role changes; ambiguity is classified as human-required.
- The plan identity, digest, drift state, classification, target, and evidence references are
  immutable inputs to approval and execution.

**Traceability:** FR-10 through FR-12; NFR-03, NFR-05, NFR-08; scenarios 8, 10, and 11.

### US-6.5: Pause Every Staging Change for Owner Approval

**As P-02 Owner/Operator/Maintainer, I want every staging change to pause for my explicit approval
so that no staging mutation occurs without my deliberate cloud-native decision.**

#### Acceptance Criteria

- Given any staging change set, including a routine in-place update, when the exact revision,
  resolved parameters, artifacts, evidence, change-set identity, and drift state are ready, then
  the cloud pipeline pauses for the owner's explicit approval before any staging mutation.
- Given any failed, missing, stale, ambiguous, or mismatched check, when staging execution is
  requested, then approval and resource mutation are denied until a new exact plan is produced.
- The AI-DLC agent, build role, and deployment role cannot approve the staging gate or directly
  mutate staging resources.
- Local dev remains mock-only; staging effects remain confined to dedicated test destinations.

**Traceability:** FR-01, FR-10 through FR-13; NFR-03, NFR-05, NFR-08; scenarios 9 and 10.

### US-6.6: Execute Only an Owner-Approved Staging Change

**As P-02 Owner/Operator/Maintainer, I want staging execution to use only the change set I approved
so that automation cannot substitute a different plan or silently cross a trust boundary.**

#### Acceptance Criteria

- Given an owner-approved staging plan, when execution begins, then the pipeline executes the same
  change-set identity and digest without rebuilding, substitution, or direct mutation.
- Approval records the human identity, time, environment, exact change-set identity/digest, drift
  evidence, and decision for every staging change, regardless of classification.
- Given rejection, expiry, drift, artifact mismatch, changed parameters, or failed evidence, when
  execution is requested, then it fails closed and requires a new plan and owner approval.
- The build, agent, and deployment roles cannot approve the gate, mutate resources directly, or
  replace the plan after approval.

**Traceability:** FR-09, FR-10, FR-12; NFR-03, NFR-08; scenarios 9 and 10.

### US-6.7: Human-Approve and Execute Production

**Maturity:** Public-Channel Readiness (deferred; non-blocking for Personal MVP).

**As P-02 Owner/Operator/Maintainer, I want every production plan to pause for my approval so that
only the exact reviewed change set can affect production.**

#### Acceptance Criteria

- Given a passing production plan, when the immutable change set and drift evidence are ready, then
  the cloud pipeline pauses for human approval regardless of change classification.
- Given approval, when execution begins, then the pipeline executes the same change-set identity and
  digest without rebuilding, substitution, or direct mutation.
- Given drift, artifact mismatch, expired approval, changed parameters, or failed evidence, when
  execution is requested, then it fails closed and requires a new plan and human approval.
- Production checks remain non-publishing until a human separately authorizes scheduler enablement
  or a Telegram effect.

**Traceability:** FR-09, FR-10, FR-12, FR-13; NFR-03, NFR-05, NFR-08; scenario 11.

### US-6.8: Retain Release, Rollback, and Break-Glass Evidence

**As P-02 Owner/Operator/Maintainer, I want attributable deployment and recovery evidence so that I
can audit, roll back infrastructure, and respond without overstating external-effect reversal.**

#### Acceptance Criteria

- Personal MVP evidence links the reviewed commit, lockfile, template/artifact digests, required
  test/scan/SBOM results, concise Infracost report, staging target, change set, owner approval for
  every staging change, pipeline execution, and smoke result.
- Normal rollback retains stateful resources and explicitly states that accepted Telegram effects
  are not reversed.
- CloudFormation Console use is inspection-only except for documented human-authorized break-glass;
  break-glass activity is least privilege, time bounded, alerted, and reconciled into evidence.
- **Deferred - Public-Channel Readiness:** release notes, signed semantic-version tags, extended
  provenance bundles, published release assets, and prior-artifact rollback evidence.

**Traceability:** FR-10 through FR-13; NFR-02 through NFR-06, NFR-08; scenarios 10-12.

## Epic E-07: Verification and Security Assurance

Prove critical behavior, invariants, and abuse resistance before deployment.

### US-7.1: Verify Examples and Properties

**As P-02 Owner/Operator/Maintainer, I want deterministic example and property tests so that boundary
and state-machine defects are found with reproducible counterexamples.**

#### Acceptance Criteria

- Every code change adds focused examples for intended behavior and important failure/boundary
  paths; business-critical examples remain even where property tests exist.
- Functional design evaluates round-trip, invariant, idempotence, commutativity, oracle, induction,
  easy-verification, and stateful-model opportunities and records applicability.
- Hypothesis strategies generate valid domain objects and boundaries, preserve shrinking, model
  stateful transitions, and retain newly discovered minimal counterexamples as regression examples.
- Normal CI is deterministic and network-independent, preserves reproduction data, and does not
  suppress unexplained flaky failures.

**Traceability:** FR-13; NFR-01, NFR-02, NFR-07; scenarios 1-6 and 8-12.

### US-7.2: Verify Contracts and Deployed Boundaries

**As P-02 Owner/Operator/Maintainer, I want layered integration and deployment verification so that
local behavior and cloud controls agree before promotion.**

#### Acceptance Criteria

- Mocked integration tests cover NWS, Telegram, DynamoDB, S3, SNS, time, and identifiers without
  live mutation; opted-in live NWS tests are bounded, read-only, credential-free, and retain no image.
- Personal MVP uses one isolated staging stack for a representative smoke path covering handler
  invocation, retained image, Telegram publish/edit, dedicated private alert, definitive-failure
  email fallback, and safe state/log/metric evidence; no ephemeral dev stack is required.
- Staging tests use only dedicated destinations.
- **Deferred - Public-Channel Readiness:** production validation remains non-publishing until
  separately authorized.

**Traceability:** FR-02, FR-05 through FR-13; NFR-01 through NFR-08; scenarios 8-11.

### US-7.3: Enforce Security Boundaries

**As P-02 Owner/Operator/Maintainer, I want layered data, identity, and authorization controls so
that untrusted inputs or compromised components cannot cross trust boundaries.**

#### Acceptance Criteria

- Persistent stores/backups are encrypted; S3 and all AWS, NWS, Telegram, Infracost, registry, and
  GitHub traffic require TLS 1.2 or newer. (SECURITY-01)
- Events, configuration, responses, identifiers, artifacts, and environment/resource references
  are schema/type/format/length validated; untrusted data is never concatenated into expressions,
  commands, paths, or URLs. (SECURITY-05, SECURITY-13)
- IAM is exact-resource least privilege with separated read/write and scoped trust; protected
  operator functions deny by default and verify caller, object, and environment. (SECURITY-06,
  SECURITY-08, SECURITY-12)
- Forged events, cross-environment substitution, poisoned NWS content, replay, retry abuse, alert
  loops, diagnostic leakage, workflow modification, and deployment-check bypass all fail closed
  with safe attributable evidence.

**Traceability:** FR-01 through FR-05, FR-08 through FR-13; NFR-03, NFR-08; scenarios 4-11.

### US-7.4: Operate Securely by Default

**As P-02 Owner/Operator/Maintainer, I want secure runtime, supply-chain, logging, and error defaults so
that failures remain observable without expanding attack surface.**

#### Acceptance Criteria

- Every Lambda uses centralized redacted structured logging; security failures alert safely and
  application roles cannot alter retained audit evidence. (SECURITY-03, SECURITY-14)
- Supported runtimes, private storage, no default credentials/services, generic external errors,
  pinned dependencies/images/tools, scans, and SBOM/integrity checks are enforced. (SECURITY-09,
  SECURITY-10, SECURITY-11)
- External calls and file/data operations have bounded error handling and cleanup; top boundaries
  catch unexpected errors, emit safe events, and expose no stack trace, path, version, raw input, or
  secret. (SECURITY-15)
- SECURITY-02 is N/A because no load balancer, API Gateway, or CDN is in scope; SECURITY-04 is N/A
  because no HTML is served; SECURITY-07 is N/A because no customer-managed network is selected.

**Traceability:** FR-02, FR-04 through FR-07, FR-09, FR-12, FR-13; NFR-03, NFR-04, NFR-06, NFR-08;
scenarios 4-6 and 8-11.

## Epic E-08: Governed Completion and Continuous Recovery

Preserve AI-DLC obligations and operational readiness through implementation and change.

### US-8.1: Preserve AI-DLC Traceability

**As P-02 Owner/Operator/Maintainer, I want every implementation unit tied to approved requirements
and migrated obligations so that retirement of prior documents causes no scope loss.**

#### Acceptance Criteria

- Every approved requirement is assigned to later AI-DLC story, unit, construction, and test
  artifacts without silent scope loss.
- Design, code, tests, deployment evidence, and exceptions trace to FR/NFR and story identifiers.
- OpenSpec and legacy `docs/` remain absent from the working tree; Git history and the migration
  inventory provide historical provenance without restoring active governance requirements.

**Traceability:** FR-14; NFR-06; completion criteria 1, 2, 6, and 8.

### US-8.2: Maintain Operational Readiness

**As P-02 Owner/Operator/Maintainer, I want concise runbooks and proportionate evidence so that
routine operation, recovery, secret rotation, and incidents remain executable after delivery.**

#### Acceptance Criteria

- Runbooks cover alarm response, reconciliation, purge, drift, secret rotation, rollback, restore,
  compromised workflow, break-glass, and scheduler/alarm enablement with bounded evidence.
- The Personal MVP manual recovery procedure defines PITR restoration into isolation and validation
  of data, images, controls, cutover, and rollback.
- **Deferred - Public-Channel Readiness:** complete and retain evidence from a formal recovery
  exercise. **Deferred - Production Maturity:** run recurring backups and recovery exercises.
- Procedures never contain tokens, invite links, private identifiers, raw payloads/responses, or
  production configuration values.

**Traceability:** FR-03, FR-04, FR-07, FR-09, FR-10, FR-12; NFR-02 through NFR-04, NFR-08;
scenarios 5, 6, 11, and 12.

### US-8.3: Propose an Issue or Source Change

**As P-03 Contributor, I want to raise a GitHub Issue or Pull Request so that I can suggest a
reproducible fix or improvement without receiving operational access.**

#### Acceptance Criteria

- A GitHub Issue can report a defect or improvement with bounded reproduction, expected behavior,
  and public-safe context; it contains no token, private identifier, invite link, production
  configuration, raw private payload/response, or other secret.
- A Pull Request is focused, follows repository conventions, links its motivation, and adds or
  updates example tests plus meaningful property tests where applicable.
- Fork-originated workflows use safe permissions and cannot access secrets, assume AWS roles,
  mutate resources, approve deployment, or write trusted release evidence.
- The owner reviews the proposal and decides through AI-DLC whether it changes approved scope;
  submitting an Issue or Pull Request does not itself amend requirements or authorize deployment.

**Traceability:** FR-12 through FR-14; NFR-03, NFR-06 through NFR-08; completion criteria 1, 3, 7,
and 8.

## Coverage and INVEST Validation

| Epic                                             | Child stories | Primary personas | Direct requirement coverage                            |
| ------------------------------------------------ | ------------: | ---------------- | ------------------------------------------------------ |
| E-01 Trusted Weather Story Acquisition           |             3 | P-01, P-02       | FR-01 through FR-06                                    |
| E-02 Safe Telegram Publication                   |             4 | P-01, P-02       | FR-02 through FR-07, FR-13                             |
| E-03 Durable State, Reconciliation, and Recovery |             3 | P-02             | FR-01, FR-03 through FR-10                             |
| E-04 Bounded Operations and Operator Awareness   |             4 | P-01, P-02       | FR-01, FR-02, FR-06 through FR-10                      |
| E-05 Secure AWS Infrastructure                   |             3 | P-02             | FR-01, FR-03, FR-04, FR-06 through FR-12               |
| E-06 Lean Staging Cloud Delivery                 |             8 | P-02             | FR-01, FR-09 through FR-13                             |
| E-07 Verification and Security Assurance         |             4 | P-02             | FR-01 through FR-13                                    |
| E-08 Governed Completion and Continuous Recovery |             3 | P-02, P-03       | FR-03, FR-04, FR-07, FR-09, FR-10, FR-12 through FR-14 |

All FR-01 through FR-14 and NFR-01 through NFR-08 have direct child-story coverage. All twelve
requirements scenarios are referenced. Each child story represents one independently verifiable
outcome, remains negotiable below its acceptance boundary, names a value-receiving persona, is
estimable from bounded criteria, is small enough to become a coherent work unit or be split without
losing traceability, and is testable through objective evidence. Deferred criteria and US-6.7 remain
traceable but do not block the current Personal MVP.
