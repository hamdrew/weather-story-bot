# Code Generation Plan: u3-health-dashboard

## Summary

- Builds: the health dashboard and its two verdict alarms (HEALTHY, NOT HEALTHY, UNKNOWN) for each environment, and the pipeline permissions that let them deploy.
- Touches: new `infra/dashboard.tf` and `infra/tests/dashboard.tftest.hcl`; `infra/bootstrap/{services,locals,apply}.tf` and its two role test files; no Python, no workflow, no change to `infra/monitoring.tf`.
- Tests: about 16 offline Terraform test runs (10 for the dashboard and verdict alarms, 6 for the bootstrap permissions); the existing 300 Python tests and 31 bootstrap tests stay green.

## Sources

- `functional-design/` (`functional-spec.md`, `rules.md` BR1.1 to BR6.2, `entities.md`)
- `nfr-requirements/` and `nfr-design/` (NFR1.1 to NFR6.14; decisions D-P, D-S, D-C, D-R, D-O, LC1 to LC8)
- `infrastructure-design/` (`infrastructure-specification.md`: the bootstrap change table, the measured sizes, owner checks; `cicd-pipeline.md`: the two slices)
- `inception/requirements-analysis/requirements.md` (FR1.1 to FR1.8, FR5.3, NFR1 to NFR6) and `inception/units-generation/unit-of-work.md`
- `aidlc/spaces/default/memory/team.md` and `project.md` (testing posture, code style, ask before bootstrap-deploy and deploy, never commit without asking)

## Two slices, one plan

The steps are in two groups. **Slice 1 (steps 2 to 7)** is the bootstrap permission change and ships first as its own pull request; the owner applies it with MFA. **Slice 2 (steps 8 to 12)** is the dashboard and ships after slice 1 is applied. Both are built in this stage, in the workspace, and nothing is committed, planned against AWS or deployed here: the commit and the pull requests are the owner's call (CLAUDE.md), and `bootstrap-deploy` and `deploy` are the owner's to run.

## Changes the design reviews carried into this plan

| From | Change |
|------|--------|
| NFR Design review (Major) | Tiles and charts are built from rows with a use flag and ONE merged trailing options object, never a conditional between tuples; a test proves both `fill` settings and an alarm with no `dimensions` |
| NFR Design review (Major) | `CompositeAlarmWrite` is added to the sid exemption list of both existing bootstrap tests, and the new "only write on `*`" guard stands in for the protection those tests gave it |
| NFR Design review (Minor) | The metric builder treats null `dimensions` as none (`quiet`, `repost-loop` set none) |
| Infrastructure Design review (Major) | The size test uses the 5,000-character budget; headroom is about three more production alarm names, so U4 and U5 regroup or raise the budget with a stated margin |
| Infrastructure Design review (Minor) | The code comments and the pull request notes say: `PutCompositeAlarm` is on `*` (staging can rewrite production's two verdict composites, and a composite can carry actions); a failed first apply can leave one composite created; revert slice 2 before slice 1; `bootstrap-deploy` runs when no pipeline run is active |
| Deviation D-P4 | Charts list the alarm's own metric from the alarm's attributes plus a threshold annotation from the alarm's `threshold`, in place of the alarm-annotation-only form (BR3.1, NFR2.10 amended) |

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

This is new code, not a bug fix, so each group below writes the code first and then its tests, in the same change. No step starts with a failing reproduction.

## Steps

### Runner

- [x] **Step 1: Verify the test runners and record the unit-scoped commands** (FR5.2, NFR4.1, NFR4.2). Run `TF_DATA_DIR=.terraform-test terraform -chdir=infra init -backend=false -input=false` and the same for `infra/bootstrap`, then the existing suites once to confirm green before any change. The exact commands are in `unit-test-instructions.md`.

### Slice 1: bootstrap permissions (ships first; the owner applies it)

- [x] **Step 2: `infra/bootstrap/services.tf`** (NFR6.2, NFR6.3, NFR6.14; D-S1, D-S2). Add the `dashboards` service (sid `Dashboard`, kind `dashboard`, `conditioned = false`, read `cloudwatch:GetDashboard`, create `cloudwatch:PutDashboard`, manage `cloudwatch:PutDashboard` and `cloudwatch:DeleteDashboards`, no tag actions) and the local `no_resource_level_writes = ["cloudwatch:PutCompositeAlarm"]`, each with a comment saying why (AWS requires `*` for `PutCompositeAlarm`; a dashboard has no tags).
- [x] **Step 3: `infra/bootstrap/locals.tf`** (NFR6.2, NFR6.4; D-S3, D-S4). Add `dashboard` to `names` (staging prefix, production exact) and `arns` (`arn:aws:cloudwatch::<account>:dashboard/<name>`, empty region field, noted in a comment), and `unknown` and `not-healthy` to production's exact alarm list.
- [x] **Step 4: `infra/bootstrap/apply.tf`** (NFR6.2, NFR6.6; D-S1, D-S5). Add the `CompositeAlarmWrite` statement (Allow, `local.no_resource_level_writes`, resource `*`, no conditions) with a comment stating the `*` scope and what it allows; set `CompositeAlarmWrite = "access"` and move `WritesWithoutTagConditions` to `access` in `apply_group_of`; replace the size comment with the measured figures (production access 4,171, roles-tags 4,039, writes 4,437; limit 6,144).
- [x] **Step 5: `infra/bootstrap/tests/apply_roles.tftest.hcl`** (NFR4.2, NFR6.4, NFR6.6; D-S6). Add `CompositeAlarmWrite` to the sid exemption lists of `the_staging_role_names_only_staging_resources` and `the_production_role_uses_no_prefix_pattern`. New runs: (a) each environment's role is allowed `PutDashboard`, `DeleteDashboards` and `GetDashboard` on its own dashboard ARN and not on the other's (the regex check used for the misconfigured alarm); (b) the two composite names are in production's alarm resources and staging's prefix covers them; (c) `PutCompositeAlarm` appears exactly once, on `*`, and is the only write action on `*`; (d) each of the six policy groups stays under 5,000 characters by a size proxy over `doc.statement` (the tests cannot use `.json`, which the mock returns as `{}`).
- [x] **Step 6: `infra/bootstrap/tests/plan_roles.tftest.hcl`** (NFR6.3; D-S6). New run: the shared plan read policy holds `cloudwatch:GetDashboard` on both dashboard ARNs and no write action on them.
- [x] **Step 7: Run the bootstrap suite** (NFR4.2): `TF_DATA_DIR=.terraform-test terraform -chdir=infra/bootstrap test`. All existing and new runs pass.

### Slice 2: dashboard and verdict alarms (ships after slice 1 is applied)

- [x] **Step 8: `infra/dashboard.tf`** (FR1.1 to FR1.3, FR1.5 to FR1.8; BR1.1 to BR6.2; D-P1 to D-P7, D-C1 to D-C3, D-R3 to D-R6, D-O1 to D-O4). New file; `monitoring.tf` is not edited. In order: (1) `local.health_signals`, the ordered signal list (missed-runs, errors, quiet, repost-loop) with the alarm resource, the tile title and a `fill` flag; (2) `local.alarm_metric`, the metric array of each alarm read from its attributes, with null `dimensions` treated as none; (3) `local.not_healthy_alarms` (errors, quiet, repost-loop) and the two rule strings, written `ALARM("name")` and `INSUFFICIENT_DATA("name")` and built with `join(" OR ", ...)`; (4) the two `aws_cloudwatch_composite_alarm` resources `local.name-unknown` and `local.name-not-healthy` with no actions; (5) the tiles (rows with a use flag, `FILL(m1, 0)`, one merged options object), the charts (alarm metric plus a horizontal threshold annotation, fill side from the comparison operator) and the text and alarm-list widgets; (6) `local.dashboard_rows` and the computed `x` and `y` (rows 5, 3, 3, 4, 3, 3, 6, 6); (7) `aws_cloudwatch_dashboard` named `local.name` with `start = "-P7D"` and `periodOverride = "inherit"`. The key text puts the three-step reading order first, then the empty-list, zero-when-UNKNOWN and quiet-needs-days sentences; the detail heading says a chart with no line has no data and to set the time zone control to Local. Comments explain why, and the extension points for U5 are named (D-C1).
- [x] **Step 9: `infra/tests/dashboard.tftest.hcl`** (FR5.2, NFR4.1, NFR2.1 to NFR2.10, NFR3.1 to NFR3.3, NFR5.1, NFR5.2, NFR5.5, NFR6.7 to NFR6.9; D-R3 to D-R5). Mock provider with the ARNs the widgets take; runs for production and staging: (a) exactly two composite alarms, named `local.name-unknown` and `-not-healthy`, and one dashboard named `local.name`; (b) neither composite has an action and neither is in the `alarm_names` output; (c) the two rule strings equal the expected text in the expected order, every term is an existing alarm's name, and each is under 1,000 characters; (d) the five existing alarms' thresholds, periods, evaluation periods, missing-data settings and actions are pinned; (e) the decoded body has 13 widgets in the specified order, every `x + width` is at most 24, the four tiles share one row and height, and the verdict area is at most 11 grid units; (f) tiles carry `FILL(m1, 0)`, a sparkline and titles with units, and both `fill` settings build; (g) each chart's metric equals its alarm's namespace, metric name, dimensions (none for `quiet` and `repost-loop`), statistic and period, and its annotation equals the alarm's threshold; (h) the alarm lists carry the right ARNs, the signals-off filter is ALARM and INSUFFICIENT_DATA, and the sort is `stateUpdatedTimestamp`; (i) no widget has `timezone`, no text has a date, a time or the environment word, and none names the Telegram token parameter; (j) the key text has the reading order before the empty and no-data sentences, and the heading names the Local control; (k) the body opens on `-P7D` with `periodOverride` inherit, has at most 50 metrics, and one extension-point stand-in (an extra term and an extra row) still yields a valid rule and layout.
- [x] **Step 10: Run the infra suite** (NFR4.1): `TF_DATA_DIR=.terraform-test terraform -chdir=infra test`. All existing and new runs pass.

### Both slices

- [x] **Step 11: Lint, scan and the Python suite** (NFR4.3, NFR5.1). `mise run lint ::: test ::: tftest ::: scan` passes: `terraform fmt -recursive` clean, Checkov has no new finding (any skip carries an inline reason), the 300 Python tests are unchanged and green, and every Terraform suite is green. `mise run plan` and `mise run deploy` are not run here: they need credentials and the owner's word, and the pull-request plan job and the pipeline cover them.
- [x] **Step 12: Documentation and traceability** (FR1.7, NFR6.1). `code-summary.md` (files, decisions, deviations, what was not run), `source-manifest.json`, and `traceability.json` mapping each assigned FR, NFR and BR to a file or test. No README or CLAUDE.md change: the page explains itself with its key.

## Story and requirement to step map

| Requirement | Steps |
|-------------|-------|
| FR1.1 (verdict), BR1.1 to BR1.6 | 8, 9 |
| FR1.2 (what is off), BR2.2 | 8, 9 |
| FR1.3 (tiles), BR2.1, BR2.3 | 8, 9 |
| FR1.5 (detail charts), BR3.1 (amended) | 8, 9 |
| FR1.6 (first screen), BR4.1, BR4.2 | 8, 9 |
| FR1.7 (empty and no-data wording), BR5.1 | 8, 9 |
| FR1.8 (no environment label), BR4.5 | 8, 9 |
| FR5.3, BR1.7, BR6.1, BR6.2 (existing alarms untouched, one new file) | 8, 9, 11 |
| NFR1 cost | 8 (two composites and one dashboard only), 9 |
| NFR2 glance time, NFR3 time zone | 8, 9 |
| NFR4 offline tests | 1, 5, 6, 7, 9, 10, 11 |
| NFR5 no regressions | 9, 11 |
| NFR6.2 to NFR6.6, NFR6.14 (permissions) | 2 to 7 |
| NFR6.7 to NFR6.9, NFR6.13 (extension points, new file) | 8, 9 |

## Not done in this stage

`mise run plan`, `mise run deploy`, `mise run bootstrap-plan` and `mise run bootstrap-deploy` (credentials and the owner's word); the first-apply rule-syntax check, the page checks at 1440 x 900 and 390 px, and the 24-hour watch, which happen on staging and production after the owner's deploy.
