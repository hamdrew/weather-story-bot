# Code Generation Plan: agent-os to AI-DLC

## Summary

- Builds: removal of agent-os, its standards and every citation of them; roadmap and mission moved into AI-DLC knowledge; a pure AI-DLC `CLAUDE.md`
- Touches: `agent-os/`, `.claude/commands/agent-os/`, comments in `src/`, `scripts/`, `tests/`, `infra/`, `mise.toml`, `mise-tasks/`, `.github/`, `README.md`, `CLAUDE.md`, `aidlc/spaces/default/knowledge/aidlc-shared/`, `aidlc/spaces/default/memory/project.md`
- Tests: no new tests (comment and doc text only; NFR1 requires the same test count); the existing suites plus grep checks verify it

## Context

This is a zero-Unit refactor: one implementation pass, working from
`inception/requirements-analysis/requirements.md` and the workspace. Units
Generation and Functional Design do not apply to it. Every change is a deletion,
a moved document, or comment, docstring, assertion-message or doc text. No
executable statement, log message, metric filter, resource argument, or test
assertion logic changes.

Ground rules for every step:

- **Alarm contracts are untouched (NFR2).** The strings "Telegram message sent"
  (`src/weather_story_bot/telegram.py:98`, `infra/monitoring.tf:32,36,126`) and
  "Ambiguous stories from NWS" (`src/weather_story_bot/handler.py:247`,
  `infra/monitoring.tf:147,151,162`) keep every byte. `infra/monitoring.tf` is not
  edited at all.
- **A pointer comment becomes a reason (FR2.3).** A comment that only says "see
  standard X" is rewritten as a one-line reason in plain words. A comment that
  already explains itself just loses the citation in parentheses. No comment is
  left empty or ending in a dangling "see".
- **Real paths stay.** `infra/iam.tf` and `infra/bootstrap` are real paths, not
  citations: `infra/bootstrap/apply.tf:296` ("mirroring infra/iam.tf's role") and
  the "created by infra/bootstrap" clause of `infra/variables.tf:104` keep them.
- **Checkov skip reasons stay non-empty (FR2.4).** Each `#checkov:skip=<ID>:<reason>`
  loses only its parenthesized citation and keeps the rest of its reason.
- **No formatter runs over the tree.** Edits are hand-made and line-local;
  `mise run lint` checks that formatting still passes.

## Steps

### Step 1: Baseline and runner check (NFR1)

- [ ] Run `mise run lint ::: test ::: tftest ::: scan` on the unchanged tree and record
  in `code-summary.md`: the pytest passed/failed/skipped counts, the number of
  `terraform test` runs per test folder (`infra/tests/`, `infra/bootstrap/tests/`),
  and whether lint and scan passed. This is the "before" result NFR1 compares
  against. If anything fails before any edit, stop and report it.

### Step 2: Move the roadmap and mission into AI-DLC knowledge (FR3.1, FR3.2)

- [ ] Read `agent-os/product/roadmap.md`, `agent-os/product/mission.md`, and the
  Phase 2.2 spec `agent-os/specs/2026-10-29-1409-wisconsin-and-minneapolis-offices/plan.md`
  (to learn what Phase 2.2 still has left).
- [ ] Write `aidlc/spaces/default/knowledge/aidlc-shared/roadmap.md` and
  `aidlc/spaces/default/knowledge/aidlc-shared/mission.md` (assumption A1). Keep
  every phase, its status, its settled decisions and its open items. Reword so
  neither file names a standard, an agent-os path, a spec folder or an idea note.
- [ ] In the Phase 2.2 entry, state what is merged (atomic post recording #29; the
  bootstrap for per-office schedules and the `misconfigured` alarm #30;
  generalized office test fixtures #31) and what remains, taken from the Phase 2.2
  spec's unfinished tasks, written so the next piece of work can be planned from
  that entry alone.

### Step 3: Re-home the four setup facts (FR4.1, FR4.2)

- [ ] Add these four rule lines under `## Way of Working` in
  `aidlc/spaces/default/memory/project.md`, replacing that section's placeholder
  comments and nothing else in the file:
  - ALWAYS use the `readonly` AWS profile for read-only AWS work; report a denied read to the owner instead of escalating to another profile.
  - ALWAYS leave Terraform and admin AWS work to the owner's MFA profiles, which only the owner can run.
  - ALWAYS give a boto3 script that runs under an MFA profile the AWS CLI's cached session.
  - ALWAYS report times to the owner in America/Chicago.
- [ ] Add nothing else from the deleted private notes (FR4.2).

### Step 4: Delete agent-os (FR1.1, FR1.2, FR2.1, FR3.3)

- [ ] `git rm -r agent-os .claude/commands/agent-os` (after Step 2 has read what it
  needs). This removes `product/` (roadmap, mission, tech stack), the four idea
  notes, all six specs, the 27 standards and `index.yml`, and the five slash
  commands. Nothing is recreated elsewhere.

### Step 5: Remove citations in `src/` (FR1.3, FR2.2, FR2.3)

- [ ] `src/weather_story_bot/planner.py:4`: replace "See `agent-os/standards/global/principles.md`." with a one-line reason for keeping decisions pure (the planner decides; only the handler acts, so the decision logic tests without AWS or Telegram).
- [ ] `src/weather_story_bot/__main__.py:4`: drop "(`global/principles.md`)" and change "a spec change" to "a deliberate design change".
- [ ] `src/weather_story_bot/handler.py:182,333`: drop "(backend/client-errors)" and "(backend/side-effect-order)".
- [ ] `src/weather_story_bot/history.py:6,45`: line 6's "See `backend/dynamodb-schema` for the item ..." becomes a self-contained statement of where the item layout is defined (the key constants in `state.py`); line 45 drops the citation.
- [ ] `src/weather_story_bot/state.py:3,31,67,113,119,166,283,285`: drop each citation; line 31's "See backend/story-identity.md." becomes a one-line reason (why the story key must stay stable); line 283's "Step 0 of backend/side-effect-order" becomes "The first write of the safety chain".

### Step 6: Remove citations in `scripts/`

- [ ] `scripts/migrate_table_keys.py:7,19`: drop "(backend/dynamodb-schema)".
- [ ] `scripts/migrate_table_keys.py:26`, `scripts/migrate_story_keys.py:18`: replace the pointer to a spec's pause command with the command itself (`mise run pause <env>`).
- [ ] `scripts/set_run_state.py:4`: drop "(`infra/environments`)".
- [ ] `scripts/infracost_usage.py:152`: replace "see the spec's cost record" with the reason in plain words (Infracost cannot price the scheduler, so its cost is left out rather than shown as zero).

### Step 7: Remove citations in `tests/`

- [ ] `tests/conftest.py:84`, `tests/test_check_break_glass.py:1`, `tests/test_ci_tasks.py:1`, `tests/test_history.py:43,263`, `tests/test_state.py:253`: drop each citation from the docstring or comment. On `test_history.py:43,263` "backend/dynamodb-schema's EVENT# key" becomes "the EVENT# key". No assertion, fixture or test name changes.

### Step 8: Remove citations in `infra/` (FR2.2, FR2.4)

- [ ] `infra/lambda.tf:2,3,10,11` (Checkov skips): drop "(infra/budget)", "(backend/secrets-in-errors)", "(backend/retries)"; each reason keeps its remaining text.
- [ ] `infra/storage.tf:39,76` (Checkov skips): drop "(infra/data-retention)", keeping the reason.
- [ ] `infra/storage.tf:31,56,127`, `infra/locals.tf:4`, `infra/variables.tf:104`: drop the citation or turn it into the plain rule it stood for (for example "infra/data-retention forbids" becomes "the 35-day undo window forbids", "records are permanent").
- [ ] `infra/tests/environments.tftest.hcl:2`, `infra/tests/iam.tftest.hcl:2`, `infra/tests/lambda.tftest.hcl:2`: drop the citation.
- [ ] `infra/tests/iam.tftest.hcl:98,163` (`error_message` text only): "Review a new one against infra/iam." becomes "Review a new one for least privilege before adding it."

### Step 9: Remove citations in `infra/bootstrap/`

- [ ] `apply.tf:4,160,165,175`, `artifacts.tf:3`, `locals.tf:11,59`, `oidc.tf:10`, `plan_roles.tf:6`, `services.tf:5,37`: drop each citation or state the rule it pointed at ("the gaps are listed in infra/iam" becomes "these services have no tag condition keys"; "the scoped exception to 'exact actions' in infra/iam" becomes "the one scoped exception to granting exact actions"). Line 296 of `apply.tf` keeps its real path.
- [ ] `tests/apply_roles.tftest.hcl:229`, `tests/artifacts.tftest.hcl:2`: drop "infra/data-retention", keeping the sentence whole.

### Step 10: Remove citations in tooling, CI and the README

- [ ] `mise.toml:1-2`: the header no longer mentions agent-os or "standard global/tooling"; it still says `mise.toml` is the one source of tool versions and tasks, and `mise.lock` the exact versions.
- [ ] `mise-tasks/check-break-glass:9`, `mise-tasks/write-env-config:9`: drop the citation.
- [ ] `.github/actions/ci-setup/action.yml:4`, `.github/workflows/pipeline.yml:2,5,50`: drop the citation. Comment lines only; no step, key or value changes.
- [ ] `README.md:95`: drop "(standard `infra/pipeline`)".
- [ ] `README.md:217`: replace "are in the spec's Gate 2" with the plain statement that these checks are made against staging before merge.

### Step 11: Rewrite `CLAUDE.md` for a pure AI-DLC workflow (FR5.1, FR5.2, NFR4)

- [ ] Line 3: replace "Specs and roadmap are in `agent-os/`." with: AI-DLC (`/aidlc`) is the workflow; the roadmap and mission are in `aidlc/spaces/default/knowledge/aidlc-shared/`.
- [ ] Remove the `## Standards` section and the whole `## Skills` section (agent-os planning, superpowers skills, stopping points, "agent-os rules win").
- [ ] In Commands, drop "(standard `global/tooling`; ...)" down to its instructions (keep the `mise upgrade` / `mise lock` how-to), "(see `testing/terraform-tests`)" and "(`infra/pipeline`)".
- [ ] Keep Commands, Docs (Context7 IDs) and Gotchas otherwise as they are. Check every command named still exists in `mise.toml` or `mise-tasks/`.

### Step 12: Verify (NFR1, NFR2, NFR4, FR1.3, FR2.2)

- [ ] `git grep -n -I -i -E 'agent-os|agentos|agent_os' -- ':!aidlc/spaces/default/intents' ':!aidlc/spaces/default/codekb'` prints nothing (the codekb is rebuilt by FR6 later).
- [ ] The 27-short-name grep from `unit-test-instructions.md` prints nothing over project files.
- [ ] `git grep -n -i -E 'superpowers|shape-spec' -- CLAUDE.md .claude/commands` prints nothing.
- [ ] `git diff -U0 -- src infra | grep -E 'Telegram message sent|Ambiguous stories from NWS'` prints nothing, and `infra/monitoring.tf` has no diff.
- [ ] `mise run lint ::: test ::: tftest ::: scan` passes with the same pytest counts and `terraform test` run counts as Step 1; record the "after" result in `code-summary.md`.

## Traceability

| Requirement | Plan step |
|---|---|
| FR1.1, FR1.2 | Step 4 |
| FR1.3 | Steps 5-12 |
| FR2.1 | Step 4 |
| FR2.2, FR2.3 | Steps 5-11 |
| FR2.4 | Steps 8, 12 |
| FR3.1, FR3.2 | Step 2 |
| FR3.3 | Step 4 |
| FR4.1, FR4.2 | Step 3 |
| FR5.1, FR5.2 | Step 11 |
| FR6.1 | Deferred: a Reverse Engineering scan after Build and Test |
| FR7.1, FR7.2 | Delivered by the Practices Discovery stage (`team.md` affirmed 2026-10-30) |
| NFR1 | Steps 1, 12 |
| NFR2 | Ground rules, Step 12 |
| NFR3 | Deferred: `mise run plan staging` needs the owner's AWS session; checked in Build and Test |
| NFR4 | Steps 11, 12 |
| NFR5 | No commit is made here; the change lands as one pull request when the owner says yes |

## Testing Contract

```json
{
  "version": 1,
  "methodology": "custom",
  "source": "team",
  "ordering": "Bug fixes start with a failing test that reproduces the bug, then the fix; new code is written first, then its tests, in the same change.",
  "scope": "refactor",
  "test_strategy": "minimal",
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
    "strategy": "minimal",
    "strategy_volume": [
      "One verifiable test per requirement at the narrowest effective level.",
      "At least one happy-path unit test per component.",
      "Unit tests are the default; a bugfix/security scope floor may require an integration or E2E regression when that is the narrowest level that reproduces the defect."
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
  "input_sha256": "sha256:0827627db65a26e753836b27c400aef131d3a09285025680b457108cccc8cbf4",
  "contract_sha256": "sha256:074e74ed0131f601c97d88fca89e777dab9262fade587d8bbcee0284565018c3"
}
```

### How this plan applies the contract

The custom ordering covers bug fixes and new code; this change is neither. It
adds no behaviour, so there is nothing to test first or after. The Minimal
strategy's one-test-per-requirement is met by the requirement pass checks
(grep, `git ls-files`, `git diff`) in Step 12, and the existing suites are the
behaviour check: NFR1 requires the same number of tests before and after, so
adding tests would break that requirement. The 80% coverage floor is unaffected
because no executable line changes.
