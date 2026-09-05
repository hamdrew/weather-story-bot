# U-03 Code Generation Plan

## Scope and Approval Boundary

U-03 turns the existing agnostic publisher and U-01 protected-operation contracts into a locally
validated staging SAM/runtime composition. It covers US-1.1, US-1.3, US-2.1, US-2.2, US-3.1,
US-3.3, US-4.1, US-5.1 through US-5.3, and US-6.3; FR-01, FR-03, FR-04, FR-06, FR-09, FR-12; and
NFR-01 through NFR-08.

This plan authorizes only local implementation after owner approval. It does not authorize an AWS
deployment, schedule enablement, staging mutation, real Telegram operation, GitHub mutation, or
change-set approval/execution. U-04 owns the delivery control plane and U-05 owns authorized
staging smoke evidence.

## Implementation Sequence

- [ ] Step 1: Create a compliant feature branch before any application/SAM implementation and retain
      the existing documentation changes. Review current brownfield contracts in `runtime.py`,
      `handler.py`, `history.py`, `image_retention.py`, `scheduled_processing.py`, `telegram.py`,
      `config.py`, and the U-01 handoff. Do not duplicate files or add a second runtime framework.
- [ ] Step 2: Complete validated runtime composition in `src/weather_story_bot/runtime.py` and
      `handler.py`. Bind versioned registry/environment/configuration inputs, exact resource
      references, bounded boto3/NWS/Telegram adapters, publisher/reconciliation/U-01 factories, and
      safe cold-start failure behavior. Preserve mock-only dev and deny event-supplied resource
      overrides or authorization labels.
- [ ] Step 3: Extend configuration and adapter boundaries in existing `src/` modules as needed for
      active-office validation, deadline propagation, secret-shape validation, conditional
      current-state access, verified media, and safe structured observations. Do not hardcode any
      office ID, introduce alert persistence/queue/public endpoint/VPC, or bypass existing typed
      contracts.
- [ ] Step 4: Extend `template.yaml` in place with U-03 staging resources: publisher and protected
      runtime bindings, DynamoDB/S3 retention/encryption/TLS protections, exact secret references,
      per-active-office disabled Scheduler schedules, scoped execution roles, retained logs, metrics,
      alarms, and dashboard. Preserve U-01 resources and the U-04 delivery handoff. Do not deploy.
- [ ] Step 5: Add deterministic example tests in existing test modules for runtime assembly failure,
      mock-only dev, active/inactive configured offices, malformed scheduler events, exact resource
      scope, budgets, conditional state/media behavior, secret redaction, and parsed-template IAM,
      storage, schedule, alarm, and no-public/no-scan constraints. Fixtures must never include
      secrets, private Telegram identifiers, or token-bearing URLs.
- [ ] Step 6: Add Hypothesis properties to `tests/test_property_invariants.py` using reusable bounded
      domain strategies. Cover deterministic assembly admission, active-office invariants, idempotent
      safe projection, configuration round trips where applicable, and stateful current-media
      transitions. Retain shrinking/fixed-seed reproducibility and complementary examples.
- [ ] Step 7: Produce local package and contract evidence without cloud mutation. Update repository
      policy tests and contributor guidance only when tooling changes. Run `make validate-sam` after
      template changes; no `sam deploy`, `sam sync`, or other remote command is permitted.
- [ ] Step 8: Create `aidlc-docs/construction/u-03/code/implementation-summary.md` mapping changes,
      requirements/stories, tests, Security Baseline/PBT evidence, U-04/U-05 handoffs, and known
      cloud-integration limits. Update this plan and state, run `make format`, `make check`,
      `make validate-sam`, and `git diff --check`.

Each completed step is checked off in this plan in the same interaction. Brownfield files are
modified in place; implementation remains on the feature branch and all cloud-facing behavior stays
unexecuted locally.

## Extension Coverage

- SECURITY-01, SECURITY-03, SECURITY-05, SECURITY-06, and SECURITY-08 through SECURITY-15 are
  implemented and tested through runtime validation, encrypted/retained resources, exact IAM,
  safe observations, locked inputs, and bounded failures. SECURITY-02, SECURITY-04, and SECURITY-07
  remain N/A because no intermediary, HTML endpoint, or customer-managed network is added.
- PBT-01 through PBT-10 apply as relevant: example tests and Hypothesis properties are required,
  with domain-specific strategies, shrinking, reproducible seeds, state models, and distinct
  example coverage. A separate algorithm oracle/commutativity/induction is N/A where no meaningful
  independent or unordered/recursive operation exists; the summary must justify each N/A.
- Resiliency Baseline is disabled.
