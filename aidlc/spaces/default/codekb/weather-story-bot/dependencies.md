# Dependencies

## External Runtime Dependencies

| Dependency | Source | Used by | Notes |
|---|---|---|---|
| httpx 0.28.1 | PyPI, `[project].dependencies` | `nws.py`, `telegram.py`, `handler.py`, `__main__.py` | the only vendored package; arm64 manylinux wheels required by `mise run build` (`--only-binary :all:`) |
| boto3 / botocore | Lambda runtime | `state.py`, `history.py`, `handler.py` (botocore errors at import; boto3 lazy) | dev-only locally; must not be added to `dependencies` |
| NWS API | network | `NwsClient` | public, needs a descriptive User-Agent |
| Telegram Bot API | network | `TelegramClient` | token from SSM |
| SSM, DynamoDB, S3 | AWS | handler wiring, stores | per-environment resources |

Note: `state.py`, `history.py` and `handler.py` import `botocore.exceptions` at module load, so the Lambda relies on the runtime-provided botocore even for a path that never calls AWS.

## Development and Tooling Dependencies

See `technology-stack.md` for versions. Relationships: moto and respx back all AWS and HTTP tests; `types-boto3[...]` extras must match the AWS services used (a new service needs its extra); `tools/checkov` is isolated because Checkov pins boto3 exactly.

## Internal Module Dependencies

Listed in `code-structure.md` (Module Import Graph). No cycles. `handler.py` is the only fan-in point; `scripts/migrate_story_keys.py` imports `archive`, `models` and `state` from the package, so those three modules' key and path functions are a contract with the migration tools.

## Infrastructure Dependencies

- The runtime stack takes `artifacts_bucket` and `permissions_boundary_arn` from the bootstrap stack's outputs (variables, not remote state).
- `infra/monitoring.tf` depends on two exact log messages emitted by `telegram.py` and `handler.py`.
- `infra/lambda.tf` comments tie the 300 s timeout to `state.LEASE_DURATION` (360 s) and the schedule interval.
- `scripts/set_run_state.py` depends on the Terraform outputs `schedule_name`, `alarm_names`, `region`.
- `deploy` depends on the plan's variables and the output `lambda_s3_key`.
- Bootstrap IAM name patterns assume the naming scheme in `infra/locals.tf` (production unsuffixed, others `-<env>`) and three-letter office ids.

## Pipeline Dependencies

`checks` gates `plan`, `deploy-staging`; `deploy-staging` gates `plan-production`; `plan-production` gates `deploy-production` (skipped when the plan has no changes). Required repository settings: variables `AWS_ACCOUNT_ID`, `AWS_REGION`, `TF_STATE_BUCKET`; secrets `STAGING_TFVARS`, `PRODUCTION_TFVARS`.

## Dependency Hygiene

Dependabot weekly across five ecosystems; mise tools and `mise.lock` are moved by hand; a 7-day release-age rule applies to mise installs.
