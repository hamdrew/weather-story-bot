# U-01 Code Generation Plan

U-01 implements protected office information, CloudWatch/SNS private alert notification, safe
observability, and one definitive-failure fallback. It must not add custom alert state, a queue,
public endpoint, or deployment authority.

## Resume and Approval Boundary

This is the single source of truth for U-01 Code Generation. Steps 1-3 describe existing
implementation in `e0f2475`, merged as `d1d7f6d`; their checkboxes do not certify all design
invariants. The owner approved this reconciled plan and its Infrastructure Design prerequisite
in the current interaction with "Approved". This approval applies prospectively; missing historical
approvals are not inferred or backdated.

U-01 covers US-2.3, US-3.2, US-4.2 through US-4.4; FR-03, FR-06 through FR-09; NFR-03,
NFR-04, NFR-07, and NFR-08. It depends on existing configuration, NWS, Telegram, and history
modules. U-03 consumes its handler contracts and SAM resources for full staging composition.
Only `OFFICE#{office_id}/CURRENT` is owned mutable state; notifications have no persisted state.

## Implementation Sequence

- [x] Step 1: Add typed bounded command, alarm, observation, and outcome models in `src/`, using
      the locked `detect-secrets` engine as the final rejection stop-gap.
- [x] Step 2: Add office refresh and conditional current-office persistence in existing modules.
- [x] Step 3: Add alarm validation, bounded alert rendering, one fallback, and loop prevention.
- [x] Step 4: Extend runtime composition and handlers with narrow validated entry points.
      Modify `src/weather_story_bot/handler.py`, `runtime.py`, `operations.py`, and `config.py`
      as needed for protected office commands, dedicated SNS/CloudWatch envelope validation,
      configured alarm/environment/source allowlists, safe outcomes, bounded deadlines, and
      structured observations. Do not treat caller-supplied `operator_id` as authorization.
      Close gaps in the existing models and services against the approved U-01 designs, including
      validation of every rendered field and safe handling of unexpected external exceptions.
      Preserve dev mocks, configured active-office scope, conditional persistence, and disabled schedules.
- [x] Step 5: Add deterministic example tests for authorization, refresh, fallback, ambiguity, loops.
      Extend `tests/test_operations.py`, `test_handler.py`, `test_runtime.py`, `test_history.py`,
      and `test_config.py` alongside each implementation change. Cover malformed/foreign events,
      unauthorized callers, wrong office/environment, exhausted deadlines, pin failures, conditional
      conflicts, repeated refreshes, primary exceptions, and fallback failures before checking off
      the affected implementation step. Never include private identifiers or secrets in fixtures.
- [x] Step 6: Add Hypothesis properties for sanitizer, alarms, refresh, Telegram entities, lifecycle.
      Extend `tests/test_property_invariants.py` with reusable bounded domain strategies, Unicode
      boundaries, sanitizer idempotence, accepted-event invariants, entity offsets, and simplified
      office/lifecycle models checked after each generated operation. Retain shrinking and fixed-seed
      reproducibility through the normal pytest gate; add concrete regressions for discovered bugs.
- [x] Step 7: Add U-01 SAM artifacts per approved infrastructure design; validate locally only.
      Create `template.yaml` for the U-01 resource boundary and template assertions in
      `tests/test_repository_policy.py`: separate office/alert functions and roles, exact current-key
      grants, separate trigger/fallback topics, scoped secrets, retained logs, and alarm configuration.
      Coordinate shared resource inputs/outputs with U-03 without implementing the delivery pipeline.
      Run `sam validate` locally. Update `AGENTS.md` if introducing or changing tooling.
- [x] Step 8: Add code summaries/traceability, format, and run `make check`.
      Create `aidlc-docs/construction/u-01/code/implementation-summary.md` mapping requirements,
      stories, paths, tests, and SECURITY/PBT evidence. Update this plan and `aidlc-state.md`, run
      `make format` then `make check`, and record SAM validation and remaining integration limits.

Every step modifies brownfield files in place, preserves mock-only dev and no-secret fixtures, and
must be checked off in this plan in the same interaction as completion.

## Extension Planning Coverage

- SECURITY-01, SECURITY-06, SECURITY-12, SECURITY-14: resource/secret isolation, encryption,
  retained logging, and scoped policies in Step 7; safe observations in Step 4.
- SECURITY-03, SECURITY-05, SECURITY-08, SECURITY-09, SECURITY-11, SECURITY-13, SECURITY-15:
  typed trust boundaries, authorization, redaction, integrity and safe failures in Steps 4-6.
- SECURITY-10: locked dependencies and validation in Step 8; full deployment supply-chain evidence
  remains assigned to U-03/U-04. SECURITY-02/04/07 are N/A: no network intermediary, HTML endpoint,
  or customer-managed network is introduced.
- PBT-01/03/04/06/07/08/09/10: Step 6 carries the functional-design properties into deterministic
  Hypothesis tests with state models and complementary Step 5 examples. PBT-02 is covered by the
  new operations-configuration serialization round-trip; lossy rendering has no inverse. PBT-05 has no separate
  algorithm oracle; simple state models remain required under PBT-06.
- These are planning obligations, not a claim of completed implementation compliance. Security
  Baseline and PBT remain enabled in full; Resiliency Baseline remains disabled.

## Generated Evidence

All eight steps are complete for the U-01 contract boundary. See
`aidlc-docs/construction/u-01/code/implementation-summary.md` for verification, rule-by-rule
compliance, and the explicit U-03 runtime/deployment handoff. Generated code awaits owner review;
this does not mark U-03 or cloud acceptance complete.
