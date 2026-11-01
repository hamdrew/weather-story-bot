# Build Instructions: agent-os to AI-DLC

This is zero-Unit refactor work, so there is one build for the whole project. The inputs are
`code-generation-plan.md` (what changed), `unit-test-instructions.md` (the commands) and
`code-summary.md` (the baseline numbers).

## Dependency installation

Nothing to install by hand. `mise` provides the tool versions pinned in `mise.toml` and `mise.lock`;
`uv` provides the Python dependencies from `uv.lock` (dev group) and Checkov from
`tools/checkov/uv.lock`.

## Environment setup

- No environment variables, config files or local services are needed. Every suite runs offline
  (respx for HTTP, moto for AWS, Terraform `mock_provider "aws"` with `-backend=false`).
- `mise run plan staging` is the one exception: it needs the owner's MFA session and reads
  staging's state. It is a read-only plan; nothing is applied.

## Build commands

| Step | Command | What it does |
|---|---|---|
| Lambda zip | `mise run build` | Vendors runtime deps for aarch64 manylinux2014 / Python 3.13 into `build/lambda.zip` and writes its base64 sha256 to `build/lambda.zip.sha256` |
| Staging plan | `mise run plan staging` | Builds first, then saves `infra/deploy-staging.tfplan` |

## Build verification

- Run `mise run build` twice; both must print the same hash. The reproducible build is what makes
  the plan below show a code-hash change and nothing else.
- Compare `build/lambda.zip.sha256` with the `source_code_hash` that `mise run plan staging` shows
  for `aws_lambda_function.bot`.

## Troubleshooting

- `mise run build` fails on a dependency with no arm64 manylinux wheel: a new runtime dependency
  must ship one. This change adds no dependencies.
- `mise run plan staging` fails on credentials: log in with the owner's MFA profile first. Only the
  owner can run it.
