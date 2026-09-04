# Unit of Work Plan

## Purpose

Decompose the approved Weather Story Bot scope into dependency-ordered implementation units. The
units preserve approved AI-DLC requirement and story traceability while recording current,
simplified, or deferred Personal MVP scope. They keep the single deployable Lambda service, its
protected AWS control plane, and public contributor boundary distinct.

## Inputs

- Approved requirements: `aidlc-docs/inception/requirements/requirements.md`
- Approved personas and stories: `aidlc-docs/inception/user-stories/`
- Approved Application Design: `aidlc-docs/inception/application-design/`
- Approved execution plan: `aidlc-docs/inception/plans/execution-plan.md`

## Planned Generation Checklist

- [x] Define dependency-ordered units and their responsibilities in
      `aidlc-docs/inception/application-design/unit-of-work.md`.
- [x] Assign every approved child story to one or more units and distinguish current/simplified work
      from named deferred maturity work.
- [x] Define the unit dependency matrix and permitted cross-unit contracts in
      `aidlc-docs/inception/application-design/unit-of-work-dependency.md`.
- [x] Map every approved child story to at least one unit in
      `aidlc-docs/inception/application-design/unit-of-work-story-map.md`.
- [x] Verify all units remain modules within the one Weather Story Bot service; no unit creates a
      separately deployable service unless separately approved.
- [x] Verify unit boundaries preserve runtime/delivery separation, environment isolation,
      least-privilege approval boundaries, and the no-secret evidence rule.
- [x] Verify every unit is ready for its applicable Functional Design, NFR Requirements, NFR
      Design, Infrastructure Design, Code Generation, and Build and Test work.

## Unit-of-Work Questions

### Question 1: Story Grouping

Which grouping approach should organize the remaining work?

**Recommendation: A.** It makes prerequisite contracts and runtime composition available before
stateful operational work, then isolates the high-risk AWS delivery and cost controls for focused
review and verification.

A) **Recommended** — Use dependency-ordered units for runtime composition, protected operations
and observability, staging SAM infrastructure, lean owner-gated delivery, non-mutating Infracost
visibility, and focused verification/runbook evidence

B) Group primarily by the eight user-story epics, even where a deployment or verification concern
crosses multiple epics

C) Create one large unit for all remaining work

X) Other (please describe after the `[Answer]:` tag below)

### Question 2: Dependencies

How should shared configuration, state contracts, and deployment evidence be managed between units?

**Recommendation: A.** Existing typed ports and models are the approved sharing mechanism; an
explicit dependency graph minimizes coupling and lets security/cost evidence be reviewed without
giving delivery controls authority over runtime behavior.

A) **Recommended** — Share only validated typed contracts and immutable evidence references;
enforce a directed dependency graph with no delivery-to-runtime business-logic dependency

B) Permit units to share internal helpers and mutable configuration directly when expedient

C) Duplicate shared contracts within each unit to avoid dependencies

X) Other (please describe after the `[Answer]:` tag below)

### Question 3: Team Alignment

What ownership model should guide sequencing for the current one-person Owner/Operator/Maintainer
team, while allowing Contributors to submit public source proposals?

**Recommendation: A.** One accountable maintainer can execute the dependency order with focused
reviews, while Contributors remain confined to normal GitHub Issues and Pull Requests and retain
no cloud or operational authority.

A) **Recommended** — Sequence units for one accountable maintainer; treat Contributor proposals as
review inputs and retain Owner/Operator/Maintainer approval for protected and deployment work

B) Assign independent parallel ownership to each unit now

C) Allow Contributors to own cloud deployment or protected-operator units after opening a pull
request

X) Other (please describe after the `[Answer]:` tag below)

### Question 4: Technical Considerations

What deployment relationship should the units use?

**Recommendation: A.** The approved architecture is a single Python Lambda service with related
SAM control-plane resources; independently testable units avoid an unapproved microservice split
and preserve the runtime composition boundary.

A) **Recommended** — Keep all runtime units in the single service and SAM stack family; use units
only for planning, design, implementation, and verification boundaries

B) Split selected runtime units into independently deployable services now

C) Defer all infrastructure and delivery work until after every runtime unit is complete

X) Other (please describe after the `[Answer]:` tag below)

### Question 5: Business Domain Boundary

Should infrastructure, delivery approval, and Infracost work remain separate from weather-story
runtime behavior?

**Recommendation: A.** The approved requirements require separate IAM roles, immutable evidence,
and human gates; a separate control-plane unit boundary prevents runtime publication code from
gaining deployment authority.

A) **Recommended** — Keep runtime publication/operations, infrastructure, owner-gated delivery,
and non-mutating cost visibility as separate units connected only by validated interfaces and
evidence

B) Combine delivery approval and cost policy into the runtime publication unit

C) Combine all AWS infrastructure, runtime, and delivery concerns into one unit

X) Other (please describe after the `[Answer]:` tag below)

## Extension Constraints

- SECURITY-01 through SECURITY-15 remain enforced. Unit boundaries must preserve validated input,
  least privilege, redaction, integrity, fail-closed behavior, evidence protection, and monitoring;
  SECURITY-02, SECURITY-04, and SECURITY-07 remain N/A under the approved architecture.
- PBT-01 through PBT-10 are N/A during Units Generation under the extension stage matrix. Units
  containing business logic or state must explicitly undergo PBT-01 analysis in Functional Design;
  unit planning must preserve the later PBT obligations.
- Resiliency Baseline is disabled.

## Validation Before Generation

- [x] All five question answers are complete, valid, mutually consistent, and unambiguous.
- [x] The completed plan was explicitly approved before unit artifact generation.
