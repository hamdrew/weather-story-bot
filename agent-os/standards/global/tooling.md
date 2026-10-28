# Tooling

`mise.toml` is the one source of tool versions for the laptop and for every CI job, and every task
is a mise task. There is no `Makefile`, and no per-tool setup action in a workflow.

## Versions

- **Ranges, not exact pins.** Dependabot can't bump `mise.toml`, so a pin would only ever move by
  hand. The major by default (`terraform = "1"`), the minor for a 0.x tool, where a minor release is
  the breaking boundary (`uv = "0.13"`)
- **Terraform's range comes from `required_version`.** mise has no `>=`, so the stacks say
  `"~> 1.11"` (1.11 or later, below 2.0) and `mise.toml` says `"1"`. Each carries a comment saying
  the two move together. `terraform init` refuses a version outside the range, so a mismatch fails
  loudly instead of drifting
- **Python comes from uv** (`requires-python`) and Checkov from `tools/checkov/uv.lock`, so neither
  is in `mise.toml`
- **`[settings] minimum_release_age = "7d"`.** A range installs whatever is newest, in jobs that hold
  AWS credentials, so a release must be a week old first (mise's default is 24h). The consequence: a
  brand-new minor (uv 0.13.0 on its first week) can't be installed by a range until it ages. Wait,
  or override for one command with `MISE_MINIMUM_RELEASE_AGE=0d`, never in `mise.toml`
- `min_version` (hard) names the mise release the tasks need. Keep `mise.toml` free of `[env]`
  sourcing and hooks, so loading the config runs nothing
- A new tool is a `mise.toml` line, not a setup action. `mise upgrade` moves the laptop within the
  ranges

## Tasks

- Short tasks are `[tasks.<name>]` in `mise.toml`. Anything with arguments, or long enough to need a
  script, is a bash file task in `mise-tasks/` (`#!/usr/bin/env bash`, `set -euo pipefail`)
- An environment is a required positional argument with `choices "staging" "production"`
  (`mise run plan staging`), never an environment variable, so a stray export can't pick a target
- Hidden helper tasks (`#MISE hide=true`) hold shared checks, like `check-plan`
- **Several tasks need `:::`**: `mise run lint ::: test`. Without it, mise passes the second name to
  the first task as an argument, and the second never runs
- Flags go after the task name and belong to the task (`mise run plan staging --no-lock`). mise's
  own flags go before it (`mise run --quiet build`)
