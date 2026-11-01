# Test Instructions: agent-os to AI-DLC

This is zero-Unit work: the whole change is one pass over the project, so the
project-wide suites are this work's scope and Build and Test runs them once.
The change touches only comment, docstring, assertion-message and doc text, so
it adds no tests (NFR1 requires the same test count before and after).

## Framework setup

Nothing to set up. Tool versions come from `mise.toml` and `mise.lock`; Python
dependencies from `uv.lock`; Checkov from `tools/checkov/uv.lock`. All suites run
offline with no credentials (respx, moto, Terraform `mock_provider "aws"`).

## Commands

Run each as a command of its own, before the first edit (baseline) and after the
last (result):

1. `mise run lint` - ruff check and format check, `terraform fmt`, `ty check`, actionlint and zizmor.
2. `mise run test` - pytest, `-ra --strict-markers`. Record passed, failed and skipped counts.
3. `mise run tftest` - `terraform test` on `infra/tests/` and `infra/bootstrap/tests/`. Record the run count per folder.
4. `mise run scan` - Checkov; proves every skip still carries a reason (FR2.4).

Requirement checks (each must print nothing):

5. `git ls-files agent-os .claude/commands/agent-os`
6. `git grep -n -I -i -E 'agent-os|agentos|agent_os' -- ':!aidlc/spaces/default/intents' ':!aidlc/spaces/default/codekb'`
7. `git grep -n -I -E '(backend/(archive-layout|cli|client-errors|dynamodb-schema|env-config|injected-clients|retries|run-outcomes|secrets-in-errors|side-effect-order|story-identity|structured-logging|untrusted-nws-data)|global/(launch-configs|principles|tooling)|infra/(alarms|budget|data-retention|environments|iam|pipeline)|testing/(handler-tests|log-contracts|offline-tests|terraform-tests|test-data))' -- ':!aidlc' ':!.claude'`
   - Expected matches only: `infra/bootstrap/apply.tf` "mirroring infra/iam.tf's role" (a real path, `infra/iam.tf`). Any other line is a missed citation.
8. `git grep -n -i -E 'superpowers|shape-spec' -- CLAUDE.md .claude/commands`
9. `git diff -U0 -- src infra` piped to a search for `Telegram message sent|Ambiguous stories from NWS` prints nothing, and `git diff --stat -- infra/monitoring.tf` is empty (NFR2).

## Expected coverage targets

The team's 80% line-coverage floor is measured by Build and Test on the full
suite (`mise run coverage`). No executable line changes here, so coverage must
match the baseline. Nothing is lowered or disabled to make a run pass.

## Mocking and stubbing

Unchanged: the suites' existing respx, moto and mock-provider setup. No new mocks.

## Test data

Unchanged: `tests/fixtures/` and the `make_story` builder. No fixture is edited.
