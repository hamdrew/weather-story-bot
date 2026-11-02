# Code Generation Plan: u1-logging-review

## Summary

- Builds: the written logging review, published as a Markdown document, plus one small test that keeps its inventory complete.
- Touches: a new `docs/logging-review.md` and a new `tests/test_logging_review.py`; no change to `src/`, `infra/` or any existing file.
- Tests: 3 offline pytest tests (the document lists every log call in `src/`, every event name is well-formed and unique, no row claims a level that differs from the code).

## Sources

- `functional-design/functional-spec.md`, `rules.md`, `entities.md` (tables 1 to 3, the secrets check, W1)
- `nfr-requirements/security-requirements.md` and `nfr-design/security-design.md`
- `inception/units-generation/unit-of-work.md` (U1: a document; no code changes) and `requirements.md` (FR6.1, FR6.2)

## Files this plan creates or changes

| File | Change | Note |
|------|--------|------|
| `docs/logging-review.md` | create | The review itself (FR6.1, FR6.2). A new `docs/` folder; nothing existing is touched. |
| `tests/test_logging_review.py` | create | Keeps the inventory honest. The one addition beyond the document, named here because the unit definition says "no code changes": it changes no production code, and the Standard test strategy asks for tests. Ask for it to be dropped under Request Changes if you would rather keep the unit document-only. |

## Plan steps

- [x] Step 1. Project structure: create the `docs/` folder with `docs/logging-review.md`.
- [x] Step 2. Test runner: the existing runner is pytest through `uv run pytest`; the unit-scoped command is `uv run pytest tests/test_logging_review.py` (recorded in `unit-test-instructions.md`). No new dependency or configuration.
- [x] Step 3. Write the review (custom ordering: new content first, then its tests in the same change). In `docs/logging-review.md`: purpose and scope; table 1 (inventory L01 to L20 with decided events); table 2 (findings F1 to F9); table 3 (decisions D1 to D9, with D2's note on the `repr` class name); the secrets check; the run.slow design (W3); the corners; what U2, U4 and U5 take from it; assumptions. Content comes from `functional-spec.md` and `rules.md`, with each rule cited as BRx.y so the document reads on its own. Traces to FR6.1 and FR6.2.
- [x] Step 4. Add the nfr-design controls as requirements for U2 in a closing section of the document ("What U2 must build"): the token leak test through the real formatter with `configure_logging()` and a route-matched control assertion (NFR4.1, NFR5.2), the `run.slow` test (NFR4.2), the formatter fallback (ADR-005). The document records them; U2 builds them.
- [x] Step 5. Write `tests/test_logging_review.py` (test 1: every message string passed to a `logger.*` call in `src/weather_story_bot/` appears in the document's inventory; test 2: every event name in the document matches BR1.2 (`^[a-z]+(\.[a-z_]+)+$`, allowed areas) and is unique; test 3: the level written beside each message in the inventory matches the level of the call in `src/`, so a changed level is noticed). The module uses `ast` and `pathlib` only, with no network or credentials.
- [x] Step 6. Environment and build configuration: none. The wheel build and the Lambda zip do not include `docs/`.
- [x] Step 7. Documentation and traceability: `code-summary.md` and `traceability.json` mapping FR6.1 and FR6.2 to Steps 3 to 5; `source-manifest.json` listing the two new files.

## Traceability

| Requirement | Steps |
|-------------|-------|
| FR6.1 (written review of every log call, with findings and decisions) | Steps 3, 5 |
| FR6.2 (secrets and bodies check) | Steps 3, 4 |
| NFR4 (offline tests; line coverage at or above 80%) | Step 5 (no production code changes, so coverage of `src/` is unchanged) |
| NFR5 (no change to what the bot posts) | all steps (only new files) |
| NFR6 (one revertible pull request) | Step 7 |

## Testing Contract

```json
{
  "version": 1,
  "methodology": "custom",
  "source": "team",
  "ordering": "Bug fixes start with a failing test that reproduces the bug, then the fix; new code is written first, then its tests, in the same change.",
  "scope": "classic",
  "test_strategy": "standard",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    },
    {
      "layer": "team",
      "text": "- **Methodology**: custom\n- **Methodology evidence**: Affirmed at the interview (Q2): test-first for bug fixes, test-after\n  for new code. The history cannot show the order (tests land in the same squashed commit as the\n  code in every behaviour change); its one explicit signal is a review finding \"fixed test-first\"\n  in #27, which fits the bug-fix half of the rule.\n- **Ordering**: Bug fixes start with a failing test that reproduces the bug, then the fix; new code\n  is written first, then its tests, in the same change.\n- **Coverage floor**: 80% line coverage, checked in CI by a separate coverage step. That CI step is\n  later work and not part of the current change; until it exists, the floor is checked with\n  `mise run coverage`. At affirmation the suite measured 99% branch coverage of\n  `src/weather_story_bot/` (296 tests).\n- **Coverage stays opt-in locally**: `--cov` is never in pytest `addopts`, because it breaks\n  debugger breakpoints; coverage runs through its own task or CI step.\n- **Offline suites**: every suite runs without network or credentials. respx mocks HTTP, moto mocks\n  AWS, an autouse fixture replaces any real AWS or Telegram credentials, and Terraform tests use\n  `mock_provider \"aws\"` with `-backend=false`.\n- **Test types**: Python unit and component tests in `tests/` (pytest), one test module per source\n  module (`tests/test_<module>.py`), plus tests that run the bash tasks for real with fake\n  `terraform` and `aws` on `PATH`; Terraform tests in `infra/tests/` and `infra/bootstrap/tests/`.\n  There is no live integration suite: live behaviour is checked on staging (see Deployment).\n- **Test data**: real captured NWS listings in `tests/fixtures/`, loaded through `office_payload` /\n  `office_stories`, plus the `make_story(**overrides)` builder.\n- **Tooling**: `mise run test` (pytest, `-ra --strict-markers`), `mise run tftest`,\n  `mise run coverage` (pytest-cov, branch coverage, terminal and HTML report).\n- **CI**: the `checks` job runs `lint`, `test`, `tftest` and `scan` on every pull request and every\n  push to `main`, and must pass before merge."
    }
  ],
  "obligations": {
    "strategy": "standard",
    "strategy_volume": [
      "Five to eight tests per component.",
      "Unit tests plus integration tests for key boundaries.",
      "Add E2E, performance, or security tests when requirements demand them."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "custom",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Custom ordering - Bug fixes start with a failing test that reproduces the bug, then the fix; new code is written first, then its tests, in the same change.",
      "Implementation and tests - preserve that exact ordering; do not convert it to layer-local TDD.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:f9e88e854eeb6103790c56799563833a0b9d3ef436070b8ad352f04757086cd7",
  "contract_sha256": "sha256:94ddaaa54604ce1f0e6fde36d5d40f5fc90cb099cd0232c1dd12e9b12ec0e67d"
}
```
