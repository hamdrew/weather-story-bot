# Code Summary: agent-os to AI-DLC

Zero-Unit refactor, one pass. Nothing is committed; the deletions are staged (`git rm -r`) and the
rest is in the working tree.

## Files created, modified, deleted

- **Deleted (staged):** `agent-os/` (product, idea notes, six specs, 27 standards, `index.yml`) and
  `.claude/commands/agent-os/` (five slash commands).
- **Created:** `aidlc/spaces/default/knowledge/aidlc-shared/roadmap.md` and
  `aidlc/spaces/default/knowledge/aidlc-shared/mission.md`.
- **Modified, memory:** `aidlc/spaces/default/memory/project.md` (four setup rules under
  `## Way of Working`).
- **Modified, `CLAUDE.md`:** pointer to AI-DLC and the knowledge folder; the Standards and Skills
  sections and all standard citations removed.
- **Modified, citation text only:**
  - `README.md`, `mise.toml`, `mise-tasks/check-break-glass`, `mise-tasks/write-env-config`
  - `.github/actions/ci-setup/action.yml`, `.github/workflows/pipeline.yml`
  - `src/weather_story_bot/`: `planner.py`, `__main__.py`, `handler.py`, `history.py`, `state.py`
  - `scripts/`: `migrate_table_keys.py`, `migrate_story_keys.py`, `set_run_state.py`, `infracost_usage.py`
  - `tests/`: `conftest.py`, `test_check_break_glass.py`, `test_ci_tasks.py`, `test_history.py`, `test_state.py`
  - `infra/`: `lambda.tf`, `locals.tf`, `storage.tf`, `variables.tf`, `tests/environments.tftest.hcl`,
    `tests/iam.tftest.hcl`, `tests/lambda.tftest.hcl`
  - `infra/bootstrap/`: `apply.tf`, `artifacts.tf`, `locals.tf`, `oidc.tf`, `plan_roles.tf`,
    `services.tf`, `tests/apply_roles.tftest.hcl`, `tests/artifacts.tftest.hcl`

## Key decisions

- The roadmap is a rewrite, not a copy: phases keep their status, settled decisions and open items,
  but every standard, spec-folder and idea-note citation is reworded. Phase 2.2 lists #29, #30 and
  #31 as merged and its seven remaining tasks and gates, in the order the owner runs them.
- A pointer comment became a one-line reason; a comment that already explained itself lost only
  its parenthesized citation. Checkov skip reasons stay non-empty.
- Real paths stay: `infra/bootstrap/apply.tf:296` still says "mirroring infra/iam.tf's role".
- Alarm strings "Telegram message sent" and "Ambiguous stories from NWS" are untouched, and
  `infra/monitoring.tf` has no diff.
- The only non-comment edit is the `error_message` text in `infra/tests/iam.tftest.hcl`, as planned.

## Test results (NFR1)

| | Before (unchanged tree) | After |
|---|---|---|
| pytest | 296 passed, 0 failed, 0 skipped | 296 passed |
| `terraform test` | 30 passed, 31 passed (two folders) | 30 passed, 31 passed |
| Checkov scan | 183 passed, 0 failed, 18 skipped | 183 passed, 0 failed, 18 skipped |
| lint | passed | passed |

The final `mise run lint ::: test ::: tftest ::: scan` was run once more on the finished tree and
exited clean. No tests were added (NFR1 requires the same count).

## Requirement checks

All print nothing, except the one real path noted above: tracked `agent-os` files, the
`agent-os|agentos|agent_os` grep (intents and codekb excluded, also with `--untracked`), the 27
standard short names, `superpowers|shape-spec` in `CLAUDE.md` and `.claude/commands`, and the
alarm-string search over `git diff -U0 -- src infra`.

## Tests written but not executed in this stage

None written. `mise run plan staging` (NFR3) is not run here: it needs the owner's MFA session.

## Deviations from the plan

1. `infra/bootstrap/locals.tf`: "until Phase 2.2 Task 9" pointed at the deleted spec. After the
   gate review it now names the task by what it does: "until the closing cleanup task (done once
   the five-office watch has passed) removes it". Comment text only; lint, `terraform test` (30 and
   31) and pytest (296) were re-run clean.
2. `infra/bootstrap/services.tf`: the replacement for "listed in infra/iam" reads "no tag condition
   keys (schedules and budgets)", taken from the matching comment in `apply.tf`.
3. The removed Skills section also held the rules "never run `deploy`, `start`/`pause` or
   `bootstrap-deploy`" and "never commit without asking". They now live in `project.md` (ask before
   running those commands) and in the owner's global instructions (no commit without asking).
4. The roadmap's Phase 2.2 entry cannot confirm from the repo whether the owner has applied the
   bootstrap stack by hand, so it says to confirm that before the first per-office schedule deploys.
5. Roadmap Phase 2.2 item 7 no longer mentions updating "the tech stack's office line": the tech
   stack file was deleted with `agent-os/product/` and is not recreated.
6. Deferred: FR6.1 (codekb rebuild after Build and Test), NFR3 (owner's staging plan), NFR5 (one
   pull request when the owner says yes).
