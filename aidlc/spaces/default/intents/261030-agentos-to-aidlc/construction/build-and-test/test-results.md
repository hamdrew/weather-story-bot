# Test Results: agent-os to AI-DLC

Run on 2026-11-01 (America/Chicago) against branch `agentos-to-aidlc` at `010380e`. The commands come
from `unit-test-instructions.md`; the plan and scope come from `code-generation-plan.md`; the
"before" numbers come from `code-summary.md`, where Step 1 recorded them on the unchanged tree.

## Build

| Command | Exit | Result |
|---|---|---|
| `mise run build` | 0 | `build/lambda.zip` built, hash `JTT76d6Mc3gq55aU2JbfqO5qJUxg3kHN5zAVtphbp/Y=` |
| `mise run build` (second run) | 0 | Same hash, so the zip is reproducible |

## Tests

| Command | Exit | Result | Before (baseline) |
|---|---|---|---|
| `mise run lint` | 0 | ruff check, ruff format (276 files), `ty check`, `terraform fmt`, actionlint and zizmor all clean (zizmor: no findings, 4 ignored, 4 suppressed) | passed |
| `mise run test` | 0 | 296 passed, 0 failed, 0 skipped | 296 passed |
| `mise run tftest` | 0 | `infra/tests/`: 30 passed, 0 failed. `infra/bootstrap/tests/`: 31 passed, 0 failed | 30 and 31 |
| `mise run scan` | 0 | Checkov: 183 passed, 0 failed, 18 skipped | 183 / 0 / 18 |
| `mise run coverage` | 0 | 296 passed; 764 statements, 6 missed, 138 branches, 5 partial: 99% | 99% (team-affirmed measurement) |

No test was added, removed, skipped or weakened.

## Coverage

Provider: pytest-cov (`mise run coverage`, branch coverage). The team's floor is 80% line coverage;
the measured figure is 99% (758 of 764 statements). The missed lines are `__main__.py` 25-28 and
112, `handler.py` 109, `models.py` 60, all unchanged by this work. No exclusion or threshold was
touched.

## Requirement checks

| Check | Result |
|---|---|
| `git ls-files agent-os .claude/commands/agent-os` | prints nothing |
| `git grep -n -I -i -E 'agent[ _-]?os' -- ':!aidlc/spaces/default/intents' ':!aidlc/spaces/default/codekb'` | prints nothing |
| The 27 standard short names over project files (`:!aidlc :!.claude`) | one line: `infra/bootstrap/apply.tf:296` "mirroring infra/iam.tf's role", a real file, as expected |
| agent-os, superpowers and process-skill names in `CLAUDE.md` and `.claude/commands` | prints nothing |
| `specs/`, `notes/`, `idea note` in `aidlc/spaces/default/knowledge/aidlc-shared` | prints nothing |
| `git diff -U0 657c6f0 HEAD -- src infra` filtered for "Telegram message sent" and "Ambiguous stories from NWS" | prints nothing |
| `git diff --stat 657c6f0 HEAD -- infra/monitoring.tf` | empty |
| FR8.1: cursors, clone id, sessions and `.aidlc-engine/` paths tracked; key/token/secret strings in `.mcp.json` and `aidlc.settings.json` | none tracked, none found |

## Only comments and text changed

Baseline `657c6f0` against `HEAD`:

- 14 changed Python files (`src/`, `scripts/`, `tests/`): the syntax tree is identical once
  docstrings are removed, so no executable statement changed.
- 15 changed Terraform files: identical once whole-line comments are removed, except
  `infra/tests/iam.tftest.hcl`, whose two `error_message` strings were reworded as planned (the
  assertion conditions are unchanged).

## NFR3: staging plan

`mise run plan staging`, run by the owner's session on 2026-11-01: `Plan: 0 to add, 1 to change,
0 to destroy.` The one change is `aws_lambda_function.bot` updated in place: `s3_key`
`staging/lambda/TYC6d-Fl2fc89zfZV4GYIjdMEBH8UUcp-UjjvOJtgkU.zip` to
`staging/lambda/JTT76d6Mc3gq55aU2JbfqO5qJUxg3kHN5zAVtphbp_Y.zip`, `source_code_hash`
`TYC6d+Fl2fc89zfZV4GYIjdMEBH8UUcp+UjjvOJtgkU=` to `JTT76d6Mc3gq55aU2JbfqO5qJUxg3kHN5zAVtphbp/Y=`
(the hash of the zip built above), and `last_modified` (known after apply). The only output change
is `lambda_s3_key`. The plan was saved to `infra/deploy-staging.tfplan` and was not applied.

## Failures

None.

## Loop-Back Log

No loop-back was needed.
