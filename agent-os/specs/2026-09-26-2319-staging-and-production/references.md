# References for Staging and Production

## Similar Implementations

### The single-environment Terraform root

- **Location:** `infra/*.tf`, with `local.name = "weather-story-bot"` in `infra/versions.tf` (moved to `infra/locals.tf` in Task 2)
- **Relevance:** Every resource name already derives from `local.name` (function, log group, roles,
  tables, bucket, SNS topic, alarms, schedule, budget), so making `local.name` depend on the
  environment is most of the naming work. The exceptions are `local.metric_namespace`
  (`infra/monitoring.tf:2`), a literal shared by any environment, and
  `var.telegram_token_param_name`, a fixed default.
- **Account-wide or production-only:** `aws_budgets_budget.monthly` (whole account),
  `aws_dynamodb_table.posted` (the MVP rollback).
- **Breaching on missing data:** `missed_runs` and `quiet` in `infra/monitoring.tf`. Idle-safe:
  `errors`, `repost_loop` and `nws_ambiguous`.
- **Scheduler:** `infra/scheduler.tf` doesn't set `state`, so it defaults to `ENABLED`. Phase 1.1
  paused it outside Terraform for a cutover. Here it is created `DISABLED` and its `state` is ignored afterwards (revised 2026-10-02).

### Partial backend config

- **Location:** `infra/backend.tf` (`backend "s3" {}`), `infra/backend.hcl.example`, and the
  gitignored `infra/backend.hcl`, which also pins `profile = "weather-deploy"`
- **Relevance:** The pattern already separates backend values from code. This spec keeps one file
  per environment under `infra/envs/`. Production's `key` stays
  `weather-story-bot/terraform.tfstate`, and `use_lockfile` gives each key its own `.tflock`.
- **Gitignored locals:** `*.tfvars` (the whole repo), `infra/backend.hcl`, `*.tfplan`, and
  `infra/override.tf`, which pins the provider profile and is shared by both environments.

### Makefile plan/deploy

- **Location:** `Makefile` (`plan`, `deploy`)
- **Relevance:** `plan` saves `deploy.tfplan` and `deploy` applies exactly that file and deletes
  it. The contract survives, with a file per environment and a required `ENV`.

### Cost tooling

- **Location:** `infracost.yml`, `scripts/infracost_usage.py`, `tests/test_infracost_usage.py`, and
  `agent-os/specs/2026-09-20-1428-decide-act-and-record/cost.md` for the format
- **Relevance:** Scenarios are office counts over per-office rates. Staging is priced always-on,
  as production's one office (revised 2026-10-02), with its own Infracost project with
  `environment: staging` so the budget and MVP table drop out.
- **Address change:** the usage key for the MVP table becomes `aws_dynamodb_table.posted[0]`.

### README

- **Location:** `README.md` "Deploy" (`make plan` / `make deploy`, smoke test), setup
  (`cp infra/terraform.tfvars.example`), the alert-tuning and add-an-office sections, and the alarm
  table
- **Relevance:** Every path and command there changes with Task 3, in the same commit as the
  Makefile and `CLAUDE.md`.

## Source Notes

### Standards review, 2026-09-16, "Environments"

- **Location:** `agent-os/notes/2026-09-16-standards-review.md:212`
- **Relevance:** The origin: a staging deployment with a `-staging` suffix, a test channel, one or
  two offices, the schedule off, started by hand, and the rule "production is only changed by
  `make deploy` (or CI); staging is where you watch real posts". Its open question "Is a staging
  stack acceptable cost-wise?" is answered by Task 6's `cost.md`.

### Phase 1.2 cost record

- **Location:** `agent-os/specs/2026-09-20-1428-decide-act-and-record/cost.md`
- **Relevance:** Production baseline: **$0.60 a month** at one office, $0.50 of it the five alarms.
  Stage 1 must leave that number unchanged.

## External

### Terraform

- `-chdir` and `TF_DATA_DIR`: Task 3 verifies that a relative `TF_DATA_DIR` resolves inside
  `infra/`, as the Makefile assumes.
- Adding `count` to an existing resource moves its object to index `[0]` without a `moved` block,
  and the plan reports it as "has moved to". Removing `count` moves it back.
- S3 backend `use_lockfile` (Terraform 1.11+) writes `<key>.tflock` next to each state object, so
  each environment has its own lock.

### Tags and ABAC

- **S3 bucket ABAC:**
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/buckets-tagging-enable-abac.html and
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/buckets-tagging.html. A general purpose
  bucket's tags count in `aws:ResourceTag`/`s3:BucketTag` conditions only once ABAC is enabled,
  object actions such as `s3:PutObject` on `bucket/*` included. Once it's on,
  `PutBucketTagging`/`DeleteBucketTagging` stop working and tags go through S3 Control
  `TagResource`/`UntagResource`. Reversible with status `Disabled`.
- **DynamoDB ABAC:**
  https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/abac-enable-ddb.html.
  `aws:ResourceTag` works on item actions, but only while the account-level setting is on
  ("enabled by default for most accounts"). Off, conditions see no tags and an Allow fails closed.
  The setting shows only on the console's Settings page, so staging's first run proves it
  (Gate 2).
- **Provider changelog, hashicorp/aws 6.23.0 (issue #45251):** `aws_s3_bucket` tagging uses S3
  Control `TagResource`/`UntagResource`/`ListTagsForResource` when the caller holds those actions,
  and otherwise falls back to `PutBucketTagging` without a warning, which fails on an ABAC bucket.
  The pinned version is 6.66.0, which also has `aws_s3_bucket_abac`.
- **SSM:** parameters support `aws:ResourceTag`. `put-parameter --tags` works only on create
  (not with `--overwrite`); an existing parameter is tagged with `add-tags-to-resource`.
