# weather-story-bot Constitution

## Core Principles

### I. Distrust Upstream Data

The NWS API is an untrusted source. It has re-issued stories under new image IDs, sent
`updateTime` values of 1970, and returned duplicates.

- When active stories cannot be told apart (shared image ID, shared title and start time, or the
  same image), the bot MUST post none of them, take no other action on them, and alert the owner
  by email.
- Stories past their end time MUST be ignored and MUST NOT be downloaded.
- New parsing or identity logic MUST fail closed: an unrecognized shape is rejected, not guessed.

Rationale: a wrong or duplicate story in Telegram is worse than a short delay while NWS fixes its
data.

### II. A Repost Beats a Missed Story

Delivery is at-least-once.

- A story MUST be recorded as posted in DynamoDB only after Telegram accepts it.
- A changed story MUST be posted again as an update (so it notifies), and the superseded message
  removed.
- Only one run per office may act at a time; concurrency control MUST be per office, not global.

Rationale: a duplicate is recoverable and visible; a silently missed story defeats the mission.

### III. Decide Purely, Act Thinly

Each office's run is a pure plan (`post`, `update`, `unchanged`, `expired`, `rejected`) followed by
a thin apply step that performs side effects.

- Decision logic MUST live in the pure planner, not in archiving, sending or recording code.
- The CLI (`--dry-run`) MUST call the same planner and MUST make no writes of any kind. Adding a
  write mode requires an explicit design change, recorded in a spec.
- What the bot did MUST be recorded as append-only data (ledger events, last-seen, per-run
  records), not only in logs.

Rationale: a pure planner is testable and makes the dry run tell the truth.

### IV. Offline, Contract-Pinned Tests

- `mise run test` and `mise run tftest` MUST run fully offline (respx for HTTP, moto for AWS, a
  mock AWS provider for Terraform) and need no credentials.
- New behavior and bug fixes MUST ship with tests that fail without the change.
- Frozen contracts MUST be pinned by tests: the story identity hash encoding (a known-hash test),
  and any log event an alarm depends on.
- Fix type errors instead of suppressing them; coverage stays opt-in and out of pytest `addopts`.

Rationale: silent drift in a hash or an alarm's event name reposts every story or blinds an alarm.

### V. Out-of-Band Observability

- Failure, recovery, silent-problem (gone quiet, repost loop, ambiguous NWS data) and cost alerts
  MUST go by email, never through Telegram, since Telegram may be what is broken.
- Alarms MUST NOT fire on a single flaky run, and MUST send a recovery notice.
- Log events that feed metric filters (`nws.ambiguous_stories`, `telegram.message_sent`) are
  contracts: they change only in the same change as `infra/monitoring.tf`.

Rationale: the owner learns about problems on their phone without relying on the failing path.

### VI. Personal Scope, Minimal Surface

This is a single-user tool.

- Features MUST serve the mission in `docs/mission.md`; speculative generality is out of scope,
  except where the roadmap names it (for example, adding offices later).
- httpx is the only runtime dependency. boto3 stays dev-only. Any new runtime dependency MUST ship
  arm64 manylinux wheels for Python 3.13 and needs written justification.
- Infrastructure cost MUST stay within the account's small monthly budget alarm.

Rationale: less code and fewer dependencies mean fewer ways to break and less to maintain.

## Security & Infrastructure Constraints

- Runtime: Python 3.13 on Lambda arm64; all infrastructure is Terraform in `infra/`.
- Each environment's Telegram token lives in its own SSM parameter, never in Terraform variables,
  state or committed files. `*.tfvars`, `*.backend.hcl` and `.env` stay local-only.
- Every GitHub Action MUST be pinned to a full commit SHA. Every Checkov skip and zizmor ignore
  MUST carry an inline reason; `mise run scan` is blocking.
- Jobs that run project tests or linters MUST NOT receive AWS credentials (`id-token: write`).
- Saved Terraform plans MUST NOT be uploaded as artifacts; the repository is public.
- Read-only AWS work uses the `readonly` profile. Terraform applies and admin AWS work belong to
  the owner's MFA profiles. The bootstrap stack is applied by hand, never from the pipeline.
- Deploys use the saved-plan pattern: the deployed zip MUST be the planned one, by hash.

## Development Workflow & Quality Gates

- Every change lands on `main` through a pull request whose `checks` job passes. `main` is never
  force-pushed or deleted.
- Before review, `mise run lint ::: test ::: tftest ::: scan` MUST pass locally.
- Merging to `main` deploys staging, then production after manual approval. Production
  `plan`/`deploy` outside the pipeline requires `BREAK_GLASS=1`.
- Commits, deploys, and starting or pausing a live environment happen only when the owner asks.
- Times reported to the owner are in America/Chicago.

## Governance

This constitution supersedes conflicting practice in specs, plans and tasks. `CLAUDE.md` holds
runtime development guidance and command details; where the two disagree, amend one so they agree.

- Amendments are made by pull request that updates this file, states the version bump and its
  reason, and updates any affected docs in the same change.
- Versioning follows semantic versioning: MAJOR for removing or redefining a principle, MINOR for
  a new principle or section or materially expanded guidance, PATCH for clarifications.
- Every `/speckit-plan` MUST include a Constitution Check against these principles; any violation
  MUST be justified in the plan's complexity tracking or the design changed.
- Reviews MUST confirm that alarm-contract event names, the identity hash and the
  posted-after-accepted ordering are unchanged or deliberately migrated.

**Version**: 1.1.0 | **Ratified**: 2026-11-09 | **Last Amended**: 2026-11-21
