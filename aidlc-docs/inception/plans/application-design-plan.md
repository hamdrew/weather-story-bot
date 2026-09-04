# Application Design Plan

## Purpose

Define high-level Weather Story Bot component responsibilities, interfaces, services, and
dependencies for the approved system-wide scope. Detailed algorithms, state transitions, NFR
patterns, infrastructure resource properties, and code remain deferred to later approved stages.

## Inputs

- Approved requirements: `aidlc-docs/inception/requirements/requirements.md`
- Approved user stories and personas: `aidlc-docs/inception/user-stories/`
- Approved execution plan: `aidlc-docs/inception/plans/execution-plan.md`
- Brownfield architecture, code structure, and API inventory:
  `aidlc-docs/inception/reverse-engineering/`

## Design Checklist

- [x] Analyze existing ports-and-adapters modules, planned SAM resources, delivery controls, and
      user-story boundaries.
- [x] Confirm the component organization and ownership boundaries.
- [x] Confirm the runtime-composition boundary for Lambda handlers and AWS adapters.
- [x] Confirm the delivery-control-plane boundary for templates, build, cost, and approval logic.
- [x] Define high-level components and their responsibilities in `components.md`.
- [x] Define public component methods and input/output contracts in `component-methods.md`.
- [x] Define application and delivery orchestration services in `services.md`.
- [x] Define communication patterns and dependency relationships in `component-dependency.md`.
- [x] Consolidate the approved design in `application-design.md`.
- [x] Validate component ownership, dependency direction, requirements/story traceability, and
      extension compliance.

## Application Design Questions

### Question 1: Component Organization

Which high-level organization should the design use for the existing Python application plus the
new AWS delivery controls?

**Recommendation: A.** It preserves the tested ports-and-adapters application boundaries while
making infrastructure and delivery concerns explicit, reviewable components instead of embedding
them in domain services.

A) **Recommended** — Keep domain/application adapters, runtime composition, infrastructure,
delivery control plane, observability, and runbooks as separate collaborating component groups

B) Consolidate all Python runtime concerns under one application component and model only
infrastructure/delivery separately

C) Use a service-per-capability design, splitting NWS, history, media, Telegram, reconciliation,
alerting, and scheduling into independently deployable services

X) Other (please describe after the `[Answer]:` tag below)

### Question 2: Runtime Composition Boundary

Where should production composition of configuration, AWS adapters, secrets, and Lambda entry points
reside?

**Recommendation: A.** A dedicated composition root keeps handlers thin, permits deterministic
injected tests, and prevents domain services from resolving environment, credentials, or AWS client
configuration themselves.

A) **Recommended** — A runtime-composition component constructs validated configuration and
adapters; Lambda handlers only validate events, invoke a service, and map safe results

B) Each handler constructs its own configuration and AWS adapters for its invocation type

C) Each domain service lazily resolves the configuration and AWS clients it needs

X) Other (please describe after the `[Answer]:` tag below)

### Question 3: Delivery Control-Plane Boundary

How should SAM, CodePipeline/CodeBuild, Infracost, change-set classification, and approval evidence
appear in the application design?

**Recommendation: A.** The approved requirements treat delivery as a protected control plane with
separate roles and immutable evidence. A distinct component group preserves that security boundary
and keeps it independent from the Weather Story runtime.

A) **Recommended** — Model an infrastructure-and-delivery control-plane component group, with
explicit evidence, policy, approval, and execution interfaces separate from runtime services

B) Model the delivery system only as implementation files under infrastructure, without an
application-design component boundary

C) Treat deployment planning and execution as methods of the runtime-composition component

X) Other (please describe after the `[Answer]:` tag below)

## Quality and Extension Constraints

- Component interfaces must accept validated, bounded models and must not pass raw secret-bearing
  requests, responses, Telegram identifiers, invite links, or untrusted paths/URLs across layers.
- Runtime services use explicit narrow ports for NWS, Telegram, DynamoDB, S3, SNS, time, and
  identifiers; handlers and composition remain the only effectful assembly boundaries.
- The delivery control plane must preserve exact-revision provenance, least-privilege role
  separation, immutable evidence, fail-closed gates, and human approval requirements.
- SECURITY-01 through SECURITY-15 are enforced where applicable. SECURITY-02, SECURITY-04, and
  SECURITY-07 are currently N/A because no network intermediary, HTML endpoint, or
  customer-managed network is selected.
- PBT-01 through PBT-10 are N/A during Application Design under the enabled extension stage matrix;
  later Functional Design, NFR Requirements, Code Generation, and Build and Test artifacts must
  enforce the applicable rules.
- Resiliency Baseline is disabled.
