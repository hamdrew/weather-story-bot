# Terraform Tests

`terraform test` checks the rules `infra/` is meant to keep, offline. They were `terraform console`
checks by hand in Phase 2.0. Now a pull request and a laptop run them the same way (`make tftest`).

## Running

- `make tftest` runs `terraform init -backend=false` and `terraform test` in `TF_DATA_DIR=.terraform-test`,
  so it never touches an environment's state or its `.terraform-<env>/` dir
- Tests live in `infra/tests/*.tftest.hcl`: `environments` (names, namespaces, production-only
  `count`s, tags), `variables` (sensitivity and validations) and `iam` (policy conditions)
- The bootstrap stack has its own tests in `infra/bootstrap/tests/` (`trust`, `plan_roles`,
  `apply_roles`, `artifacts`), run by the same `make tftest` after the main stack's
- They need no AWS credentials. `mock_provider "aws"` replaces the provider, so the laptop's
  gitignored `override.tf` (`profile = "weather-deploy"`) is never configured

## Writing them

- Every file declares the same `mock_provider "aws"` with `override_data` for
  `aws_caller_identity` (`account_id = "123456789012"`). A mocked resource's ARN is a random
  string that arguments such as `role` and `alarm_actions` reject, so give each resource type
  used that way an ARN under `mock_resource ... defaults`. A mocked `aws_iam_policy_document.json`
  is a placeholder (`"{}"`)
- **Assert on the policy documents' inputs**, not on `.json`:
  `one([for s in data.aws_iam_policy_document.lambda.statement : s if s.sid == "State"])`, then
  its `resources`, `actions` and `condition`
- Run with `command = apply` (the default) when a value comes from a mocked resource, as a plan
  leaves it unknown. Use `command = plan` for variable rules
- A validation gets one `run` each with `expect_failures = [var.<name>]`. Any other failure still
  fails the run, so put one bad value in each
- Anything a test needs to read, such as the provider's `default_tags`, is a local
  (`local.default_tags`) that the production code uses too. Never add a local only for a test
- **Compare collections with `jsonencode(a) == jsonencode(b)`** (or `toset(a) == toset(b)` for
  unordered lists). Terraform's `==` is false for a list against a tuple or a map against an
  object, and a failed comparison of mocked values can crash the test runner while it prints the
  diff ("value has marks"). A crash like that means an assertion is false, not a Terraform bug:
  bisect it one assert at a time
- Build an ARN a test reads from names (`"arn:aws:s3:::${local.bucket}"`), not from a mocked
  resource's `.arn`, which is a random string
- A new test must be seen to fail: break the rule it guards (a capitalised tag, a wildcard ARN, a
  removed `sensitive`), run `make tftest`, and put it back

## What gets a test

- Names and metric namespaces per environment, and the production-only `count`s
- The lowercase `Environment` tag (`local.default_tags`)
- Each variable validation, including the slash-less and other-environment forms
- Every `sensitive` variable (`issensitive`)
- Every IAM statement's exact ARN and its `Environment` tag condition. `Logs` has none, and
  that is asserted too
- Every trust policy, boundary and tag condition gets a test in the task that adds it. The
  bootstrap stack's: each role's `aud` and exact `sub`, the plan roles reading no object, item or
  parameter, each apply role naming only its own environment's ARNs and state key, the Deny, the
  boundary conditions, tag writes pinning the request tag but never the resource tag, the
  retention Deny, and no allowed bucket ARN with a wildcard
- Policy documents built from a `for_each` or a `dynamic` block are asserted per environment the
  same way: collect an environment's statements across its documents, then filter by `sid`

## Security scan (Checkov)

`make scan` runs Checkov on `infra/` (which includes `infra/bootstrap/`) from its own uv project,
`tools/checkov/`, the same on a laptop and in CI, so no third-party GitHub Action ever runs beside CI credentials.
It is blocking: any failed check exits non-zero.

- Fix a finding when the fix is free and safe. Otherwise suppress it inside the resource block:
  `#checkov:skip=CKV_AWS_50:<why>`, one line per check
- **The reason is mandatory.** `make scan` fails first on any `checkov:skip=<ID>` with no
  `:reason`. Write the actual constraint (cost, a service limit, a decision), and name the
  standard or spec where it is recorded
- A fix that changes infrastructure goes in the plan for the spec's next deploy gate. Do not
  apply it from the scan
- Checkov is a separate project because it pins `boto3` exactly, which the main project's dev tools
  can't share. Its version lives in `tools/checkov/uv.lock`, never in the Makefile, and Dependabot proposes
  bumps
- A Checkov bump can add rules. Triage what the new rules find in the same PR that bumps it
