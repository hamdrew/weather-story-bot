# Standards for Deploy from GitHub Actions

## Added by this spec

- **testing/terraform-tests** (Task 3, extended in Tasks 4, 5 and 6) — `terraform test` runs
  offline with `mock_provider "aws"` and `override_data` for `aws_caller_identity`, in its own data
  dir with `-backend=false`. A mocked `aws_iam_policy_document.json` is a placeholder, so tests
  assert on the documents' inputs (statements, actions, resources, conditions). Variable
  validations are tested with `expect_failures`, one checkable object per run. Every trust policy,
  boundary and tag condition has a test. Checkov suppressions are inline
  `#checkov:skip=<ID>:<reason>`, the reason is mandatory and `make scan` enforces it.
- **infra/pipeline** (Task 9) — The four CI roles and their exact OIDC subjects. Staging applies
  before production, and production applies only after approval, from a plan made on `main` and
  stored in the private artifacts bucket. `id-token: write` only in jobs that run no project code.
  The bootstrap stack is applied by hand, so a new AWS service in the main stack means a bootstrap
  change applied first. Rollback is a revert. `make deploy ENV=production` is break-glass and
  needs `BREAK_GLASS=1`.

## Amended by this spec

- **infra/iam** (Tasks 5 and 6) — CI roles live in `infra/bootstrap/`. The plan roles may use
  `Get*`/`List*`/`Describe*` per service, but only on the project's resource ARNs and never on
  objects, items or parameters (the scoped exception to "exact actions"). A deploy role may hold
  tag-write actions only when both `aws:ResourceTag/Environment` and `aws:RequestTag/Environment`
  pin its own environment. Every role the pipeline creates or changes must carry its own
  environment's permissions boundary, and nothing in CI can change a boundary. Explicit Deny on
  table, bucket and object deletion. The list of actions that support no tag condition.
- **infra/environments** (Tasks 2, 7 and 9) — Values that would print in public logs are
  `sensitive`. The artifacts bucket and the boundary ARN come from outside the main stack, so they
  are required variables. Production pipeline-only goes from written to enforced.
- **infra/data-retention** (Task 5) — The artifacts bucket holds derived, rebuildable data (zips,
  saved plans), so lifecycle expiry is allowed there and nowhere else.

## Constraining, unchanged

The full text of each standard is in `agent-os/standards/`. How each applies here:

- **global/principles** — "Local tools are read-only": `make plan`/`make deploy` are the
  existing deploy path, the zip script only writes `build/`, and `make scan`/`make tftest` only
  read. "The office is the unit of isolation" is unaffected: CI deploys one stack per
  environment, with no per-office resources.
- **infra/budget** — `cost.md` from `make cost`, with a bootstrap project in `infracost.yml`.
  Expected: production and staging unchanged, the bootstrap adds cents (one small bucket), IAM
  and OIDC are free, and Actions is free on a public repo. No budget change.
- **infra/environments** — One `ENV` still selects backend, var file, data dir and plan file. CI
  writes `envs/<env>.backend.hcl` and `<env>.tfvars` from Actions variables, never an
  `infra/terraform.tfvars`. Created things are derived and outside things are required
  variables.
- **infra/data-retention** — Check every plan for `must be replaced` / `destroy` on the table
  and bucket. The new Deny statements make that true in IAM as well.
- **infra/alarms** — No new alarms. A failed workflow run emails through GitHub, not SNS.
- **testing/offline-tests** — `make test` and `make tftest` reach nothing outside the machine.
  The zip script's tests use `tmp_path`.
