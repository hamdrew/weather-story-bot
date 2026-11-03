# Unit Test Instructions: u3-health-dashboard

Every command runs offline: no AWS or Telegram credentials, no network beyond the one-time provider download that `terraform init` already needs (the providers are cached after the first `init`).

## Prerequisites

- `mise install` has run (Terraform 1.16.x, Python 3.13 and uv from `mise.toml`).
- Each Terraform root has been initialised once without a backend:
  - `TF_DATA_DIR=.terraform-test terraform -chdir=infra init -backend=false -input=false`
  - `TF_DATA_DIR=.terraform-test terraform -chdir=infra/bootstrap init -backend=false -input=false`

## Unit-scoped commands

| What | Command | Expected |
|------|---------|----------|
| Slice 1: the bootstrap permission tests (existing and new) | `TF_DATA_DIR=.terraform-test terraform -chdir=infra/bootstrap test` | every run passes (31 existing plus about 6 new) |
| Slice 1: one file only | `TF_DATA_DIR=.terraform-test terraform -chdir=infra/bootstrap test -filter=tests/apply_roles.tftest.hcl` | passes |
| Slice 2: the dashboard and verdict-alarm tests | `TF_DATA_DIR=.terraform-test terraform -chdir=infra test -filter=tests/dashboard.tftest.hcl` | about 10 runs, all pass |
| Slice 2: the whole infra suite, so the existing alarms stay pinned | `TF_DATA_DIR=.terraform-test terraform -chdir=infra test` | every existing run and every new run passes |
| Format | `terraform fmt -recursive -check` | no output |

The same Terraform suites run together through `mise run tftest`.

## Whole-project gate (what CI's `checks` job runs)

`mise run lint ::: test ::: tftest ::: scan`

- `lint`: ruff check, ruff format check, `terraform fmt -recursive`, `ty check`, actionlint and zizmor. This unit touches no Python and no workflow, so only the Terraform formatting is new ground.
- `test`: the Python suite (300 tests), unchanged and green.
- `tftest`: both Terraform suites.
- `scan`: Checkov, blocking. A new finding on the composite alarms or the dashboard is fixed or skipped inline with `#checkov:skip=<ID>:<reason>`.

## Coverage

The 80% line-coverage floor applies to `src/weather_story_bot/`, which this unit does not touch. Confirm it still holds with `mise run coverage` (opt-in; `--cov` never goes into pytest `addopts`). The Terraform tests are not line-measured.

## Not run here

`mise run plan <env>`, `mise run deploy <env>`, `mise run bootstrap-plan` and `mise run bootstrap-deploy` need credentials and the owner's word. The pull request's plan job covers the plan for slice 2; the owner runs `bootstrap-plan` and `bootstrap-deploy` with the MFA profile for slice 1. The checks that only a live account can give (the quoted rule syntax, the page at 1440 x 900 and 390 px, the first 24 hours) happen on staging after the owner's deploy.

## Reading a failure

A red run of `the_staging_role_names_only_staging_resources` in the bootstrap suite can crash Terraform 1.16.6 while it prints the failed assertion (marked values) instead of showing a message. If that test "crashes", check first that `CompositeAlarmWrite` is in its sid exemption list.
