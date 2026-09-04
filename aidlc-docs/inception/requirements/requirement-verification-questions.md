# Requirements Verification Questions

The existing OpenSpec changes provide detailed target behavior, while the current repository has
already implemented part of the application and has not yet implemented the AWS infrastructure or
deployment path. Please answer every question by entering a letter after its `[Answer]:` tag. If
none of the listed choices fits, select the final **Other** option and describe the intended answer.

## Question 1: AI-DLC Delivery Scope

What outcome should this AI-DLC workflow treat as its implementation scope?

**Recommendation: A.** Both changes describe interdependent delivery requirements: the service
cannot safely deploy its planned AWS infrastructure until the Infracost gate exists, so handling
them in one AI-DLC scope avoids an unsafe sequencing gap.

A) **Recommended** - Complete all remaining requirements in both `init` and
`infracost-integration`, including application, infrastructure, CI/CD, documentation, and
verification work

B) Complete only the remaining `init` requirements, leaving `infracost-integration` for a separate
workflow

C) Complete only the `infracost-integration` change

D) Plan the full remaining scope but stop construction after the next coherent implementation unit

X) Other (please describe after the `[Answer]:` tag below)

## Question 2: OpenSpec Artifact Role

How should AI-DLC treat the existing OpenSpec artifacts while assuming SDLC responsibility?

**Recommendation: D.** The stated goal is to replace OpenSpec completely. A controlled migration
preserves requirement and task coverage before the OpenSpec directory and its contributor-guide
governance are retired.

A) **Recommended** - Use them as binding requirements references, reconcile stale statements in
AI-DLC artifacts, and continue updating their task checkboxes as implementation finishes

B) Use them as binding requirements references, but track all future progress only in AI-DLC
artifacts and leave OpenSpec task checkboxes unchanged

C) Treat them as advisory inputs that AI-DLC may replace where its analysis recommends a different
requirement

D) **Recommended** - Use them only as temporary migration sources; transfer all required behavior,
decisions, tasks, and traceability into approved AI-DLC artifacts, then archive them outside the
active repository, remove `openspec/`, and update repository governance to AI-DLC

X) Other (please describe after the `[Answer]:` tag below)

## Question 3: External Delivery Boundary

How far should later construction work proceed when it reaches GitHub and AWS operations?

**Recommendation: C.** The revised delivery authority explicitly includes the complete cloud
deployment lifecycle. The requirements amendment must replace the local-only boundary with
environment-specific cloud deployment, change-set, and approval controls.

A) **Recommended** - Produce and locally validate review-ready implementation and runbooks; require
separate explicit authorization before creating or changing remote GitHub or AWS resources

B) Include authorized dev and staging GitHub/AWS setup and verification, but stop before production
deployment or production mutations

C) Include the complete reviewed dev, staging, and production delivery lifecycle, subject to every
specified approval and safety gate

X) Other (please describe after the `[Answer]:` tag below)

## Question 4: Requirements Conflict Policy

If current code, living documentation, and an OpenSpec statement disagree, which reconciliation
policy should govern?

**Recommendation: D.** This makes approved AI-DLC requirements the durable target while treating
current code as the implementation baseline and OpenSpec only as a completeness source during the
migration. It avoids carrying competing specification authorities forward.

A) **Recommended** - Treat approved OpenSpec behavioral requirements as the target contract, treat
the current code and reverse-engineering artifacts as the implementation baseline, and update
stale documentation without weakening the target

B) Preserve current implemented behavior unless the user separately approves each conflicting
OpenSpec requirement

C) Pause at every conflict and create a dedicated decision question before changing any artifact
or code

D) **Recommended** - Treat approved AI-DLC requirements as the target contract and current code as
the implementation baseline; use OpenSpec only to detect migration omissions until it is retired,
and resolve behavior changes through AI-DLC approval rather than continued OpenSpec governance

X) Other (please describe after the `[Answer]:` tag below)

## Question 5: Security Baseline Extension

Should security extension rules be enforced for this project?

**Recommendation: A.** This is a public-repository, production-targeted AWS service handling bot
credentials, private destinations, deployment identities, and external effects, so security rules
should be blocking rather than advisory.

A) **Recommended** - Yes — enforce all security rules as blocking constraints (recommended for
production-grade applications)

B) No — skip all security rules (suitable for proofs of concept, prototypes, and experimental
projects)

X) Other (please describe after the `[Answer]:` tag below)

## Question 6: Property-Based Testing Extension

Should property-based testing rules be enforced for this project?

**Recommendation: A.** The service contains state machines, normalization, sanitization, bounded
retry logic, serialization, and lifecycle invariants that benefit materially from generated inputs
and shrinking.

A) **Recommended** - Yes — enforce all property-based testing rules as blocking constraints
(recommended for projects with business logic, data transformations, serialization, or stateful
components)

B) Partial — enforce property-based testing rules only for pure functions and serialization
round-trips (suitable for projects with limited algorithmic complexity)

C) No — skip all property-based testing rules (suitable for simple CRUD applications, UI-only
projects, or thin integration layers with no significant business logic)

X) Other (please describe after the `[Answer]:` tag below)

## Question 7: Resiliency Baseline Extension

Should the resiliency baseline be applied to this project?

Enabling it applies directional, design-time AWS reliability practices covering business goals,
change management, observability, high availability, disaster recovery, and continuous
improvement. It is a starting point, not a production-readiness certification or a substitute for
a formal AWS Well-Architected Review.

**Recommendation: A.** The workload has scheduled execution, durable state, ambiguous external
delivery, alert fallback, backup/restore, and environment promotion concerns, so directional
resiliency checks add useful design discipline without claiming certification.

A) **Recommended** - Yes — apply the resiliency baseline as directional best practices and
design-time guidance (recommended for business-critical workloads)

B) No — skip the resiliency baseline (suitable for proofs of concept, prototypes, and experimental
projects where rapid iteration matters more than reliability)

X) Other (please describe after the `[Answer]:` tag below)
