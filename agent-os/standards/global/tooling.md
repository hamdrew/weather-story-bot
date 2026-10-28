# Tooling

`mise.toml` is the one source of tool versions for the laptop and for every CI job, and every task
is a mise task. There is no `Makefile`, and no per-tool setup action in a workflow.

## Versions

- **Ranges say what is allowed, `mise.lock` says what is installed.** `mise.toml` holds ranges: the
  major by default (`terraform = "1"`), the minor for a 0.x tool, where a minor release is the
  breaking boundary (`uv = "0.13"`). The committed `mise.lock` records the exact version each range
  resolved to, with a URL and checksum per platform (and a verified attestation where the project
  publishes one, as uv does). The laptop and every CI job install from it, so they run the same
  tools, and a tool change is a reviewed diff that goes through the PR plans before it deploys
- **CI installs locked.** Every `jdx/mise-action` step sets `install_args: --locked` itself. The
  action adds the flag on its own only when it detects the lock file, and otherwise installs from
  the ranges without saying so. A tool or platform missing from the lock must fail the job instead
  of resolving fresh. Keep `lockfile = true`
  in `mise.toml`, and lock both platforms: `linux-x64` (the runners) and `macos-arm64` (the laptop)
- **Nothing bumps the lock for you.** Dependabot has no mise ecosystem, so a tool moves only when
  you run `mise upgrade` and then `mise lock --platform linux-x64,macos-arm64` (to fill both
  platforms), and commit `mise.lock`. Do it deliberately and often enough that Terraform security
  releases don't wait. The action's own mise binary is not in the lock: it takes the newest release
  at least 7 days old
- **Terraform's range comes from `required_version`.** mise has no `>=`, so the stacks say
  `"~> 1.11"` (1.11 or later, below 2.0) and `mise.toml` says `"1"`. Each carries a comment saying
  the two move together. `terraform init` refuses a version outside the range, so a mismatch fails
  loudly instead of drifting
- **Python comes from uv** (`requires-python`) and Checkov from `tools/checkov/uv.lock`, so neither
  is in `mise.toml`
- **`[settings] minimum_release_age = "7d"`.** A range resolves to whatever is newest, so a release
  must be a week old before an upgrade can put it in the lock (mise's default is 24h). The
  consequence: a brand-new minor (uv 0.13.0 on its first week) can't be locked until it ages. Wait,
  or override for one command with `MISE_MINIMUM_RELEASE_AGE=0d`, never in `mise.toml`
- `min_version` (hard) names the mise release the tasks need. Keep `mise.toml` free of `[env]`
  sourcing and hooks, so loading the config runs nothing
- A new tool is a `mise.toml` line plus a re-locked `mise.lock`, not a setup action

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
