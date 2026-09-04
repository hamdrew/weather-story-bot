# Weather Story Bot Units of Work

## Decomposition Rules

- Units are implementation and verification boundaries within the existing single Python Lambda
  service and its SAM stack family. They are not independently deployable services.
- Units communicate through validated domain models, narrow ports, SAM parameters/outputs, and
  immutable evidence references. They do not share mutable configuration, secrets, private
  identifiers, raw external payloads, or deployment authority.
- AI-DLC requirement, story, unit, construction-artifact, and test identifiers provide the active
  traceability chain. Retired-framework task labels are not used.
- Security Baseline controls remain enforced in every unit. PBT analysis and tests occur in the
  applicable downstream construction stages, not as a substitute for focused example tests.

## Unit U-01: Protected Runtime Operations and Observability

**Purpose:** Complete protected office-information management, CloudWatch-driven alert dispatch,
safe observability, and runtime-facing contracts without granting infrastructure or deployment
authority.

**Responsibilities:**

- Implement the on-demand office-information Lambda, its local mock-only behavior, pin
  verification, and schedule-disabled-on-failure behavior.
- Implement bounded alert rendering, structured sanitization/schema, CloudWatch alarm-event
  dispatch to the dedicated private Telegram alert channel, definitive-failure-only SNS/email
  fallback, and loop prevention.
- Use CloudWatch alarm state/history for noise reduction and evidence. Do not implement DynamoDB
  alert fingerprint, cooldown, aggregation, or alert-delivery state.

**AI-DLC traceability:** US-2.3, US-3.2, and US-4.2 through US-4.4; FR-03, FR-06 through FR-09,
and NFR-03, NFR-04, NFR-08.

**Completion boundary:** All protected operations deny invalid callers, environments, objects, and
state. Alert and log paths retain only allowlisted bounded data, cannot notify the public channel,
and cannot loop back into their trigger path.

## Unit U-02: Infracost Staging Visibility

**Purpose:** Produce a pinned, non-mutating, exact-revision staging estimate and safe evidence for
owner review without creating a custom policy, baseline, exception, or deployment-gate system.

**Responsibilities:**

- Define the reviewed staging SAM inputs, assumptions, unsupported-resource reporting, allocation
  cap, and exact-revision/environment identity for a concise Infracost report.
- Run the estimate without deployment credentials or application-resource mutation and retain its
  bounded evidence for owner review alongside AWS Budget notifications.
- Make failed or missing estimation visible without blocking a staging change set; required build,
  change-set, owner-approval, and fail-closed controls remain independent.

**AI-DLC traceability:** US-6.2; FR-11 through FR-13; NFR-03, NFR-05, NFR-06, and NFR-08.

**Deferred scope:** Custom policy, baseline, exception, pull-request-comment, and multi-environment
cost workflows are deferred to Public-Channel Readiness or Production Maturity.

**Completion boundary:** Infracost cannot obtain deployment credentials, approve a change, or
mutate AWS application resources. Its report is evidence for review, not a machine-enforced gate.

## Unit U-03: Staging SAM Infrastructure and Runtime Composition

**Purpose:** Define the isolated staging SAM resources and bind the existing application and U-01
capabilities into deployable Lambda runtime composition.

**Responsibilities:**

- Author staging resources, scoped IAM, DynamoDB PITR, S3 versioning/retention, Scheduler,
  CloudWatch metrics/alarms, SNS, Secrets Manager references, AWS Budget, and environment
  isolation. Production template/configuration contracts remain validated but undeployed.
- Build reproducible Python 3.13 arm64 artifacts with pinned dependencies, SBOM, and scans.
- Compose validated configuration and concrete ports for publisher, protected operators, alerts,
  and office-information handlers; preserve local mocks and fail-closed boundaries.
- Document the manual PITR-to-isolated-table restore procedure; scheduled monthly backups and
  recurring recovery exercises are not Personal MVP work.

**AI-DLC traceability:** US-1.1, US-1.3, US-2.1, US-2.2, US-3.1, US-3.3, US-4.1, US-5.1 through
US-5.3, and US-6.3; FR-01, FR-03, FR-04, FR-06, FR-09, FR-12, and NFR-01 through NFR-08.

**Completion boundary:** Staging template and runtime boundaries enforce `us-east-2` isolation,
retained/encrypted state, scoped IAM, disabled schedules until approved smoke checks, and no secret
or private-identifier disclosure in parameters, outputs, or evidence.

## Unit U-04: Lean Staging Delivery Control Plane

**Purpose:** Build the GitHub-to-AWS staging control plane that consumes a read-only exact revision,
produces protected evidence, and pauses every staging change set for owner approval.

**Responsibilities:**

- Configure scoped CodeConnections, CodePipeline, CodeBuild, CloudFormation change-set, and role
  boundaries without long-lived keys or source-write access.
- Run required validation, supply-chain evidence, concise Infracost visibility, and change-set
  classification before the owner's cloud-native approval for every staging mutation.
- Execute only the exact approved staging change set through controlled CloudFormation; build,
  agent, and deployment roles cannot approve or directly mutate resources.
- Retain concise staging release, rollback, break-glass, and security evidence. Production release,
  provenance, and execution portions remain deferred.

**AI-DLC traceability:** US-6.1, US-6.4 through US-6.8, US-7.3, US-8.2, and US-8.3; FR-10 through
FR-14 and NFR-03, NFR-05, NFR-06, NFR-08.

**Deferred portions:** Production deployment, activation, release provenance, and advanced release
verification within these identifiers are deferred to Public-Channel Readiness.

**Completion boundary:** No non-human role can bypass owner approval, alter an approved change set,
write to GitHub, or mutate application resources outside the controlled CloudFormation path.

## Unit U-05: Focused Verification and Recovery Evidence

**Purpose:** Add the focused example, property, integration, staging-smoke, and recovery-preparation
evidence needed to prove Personal MVP runtime and control-plane behavior.

**Responsibilities:**

- Test source/media, state transitions, reconciliation, captions, secret/log boundaries, alerting,
  environment/IAM/Scheduler behavior, and integration paths using deterministic mocks.
- Execute one representative authorized staging smoke path covering handler invocation, retained
  image, Telegram publish/edit, dedicated private alert, definitive-failure email fallback, and
  safe state/log/metric evidence. No ephemeral dev stack is required.
- Preserve attributable, bounded verification, rollback, reconciliation, and manual-restore
  preparation evidence without claiming accepted Telegram effects are reversible.

**AI-DLC traceability:** US-7.1, US-7.2, US-8.1, and US-8.2; FR-01 through FR-13 and NFR-01,
NFR-02, NFR-07, and NFR-08.

**Deferred scope:** Formal recovery exercises and ephemeral cloud-development verification are not
Personal MVP work.

**Completion boundary:** Example tests and applicable Hypothesis properties prove expected behavior.
External staging actions require the exact plan, required checks, and recorded owner approval; no
production or ephemeral-development cloud action is part of Personal MVP.

## Completion Check

- [x] Every approved child story maps to one or more units, and every unit links to applicable
      AI-DLC requirements and non-functional requirements.
- [x] Each unit has a bounded responsibility and an explicit completion boundary.
- [x] No unit introduces an unapproved deployable service or mixes runtime publication with
      delivery-approval authority.
