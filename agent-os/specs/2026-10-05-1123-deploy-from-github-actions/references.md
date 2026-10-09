# References for Deploy from GitHub Actions

## Similar Implementations

### Phase 2.0 spec (the gate model)

- **Location:** `agent-os/specs/2026-09-26-2319-staging-and-production/plan.md`
- **Relevance:** Stages that each end in a deployable, revertible gate, with pass criteria and a
  rollback. What a condition reads goes live a deploy before the condition. Staging proves a
  permission change before production takes it.

### Makefile deploy contract

- **Location:** `Makefile` (`build`, `check-env`, `plan`, `deploy`, `start`/`pause`)
- **Relevance:** One `ENV` selects backend, var file, `TF_DATA_DIR` and plan file. `plan` saves
  `deploy-<env>.tfplan` and `deploy` applies exactly that file. CI reuses these targets rather than
  re-implementing them, so `deploy` gains `init` (a fresh runner) and a hash check, and `build`
  becomes reproducible. `build` currently runs `zip -qr`, which records mtimes and walk order:
  every build has new bytes, so every plan shows a Lambda update.

### The main Terraform stack

- **Location:** `infra/*.tf`
- **Relevance:**
  - `lambda.tf`: `filename` + `source_code_hash = filebase64sha256(var.lambda_zip_path)`, which
    becomes an S3 location and a hash variable
  - `iam.tf`: the existing policy-document style (`sid` per statement, tag conditions on exact
    ARNs, commented). The CI roles follow it. The Lambda and Scheduler roles gain
    `permissions_boundary`
  - `providers.tf`: `default_tags`, which moves to a local for `terraform test`
  - `variables.tf`: validation patterns (`environment`, `telegram_token_param_name` under
    `/${local.name}/`), which `permissions_boundary_arn` copies
  - `locals.tf`: `local.name`. Production is unsuffixed, which is why production ARNs need exact
    names
  - `override.tf` (gitignored): `profile = "weather-deploy"`, absent in CI, so the default
    credential chain picks up OIDC credentials
  - `.terraform.lock.hcl`: committed with `zh:` hashes for all platforms

### Credentialed scripts

- **Location:** `scripts/set_run_state.py` (`session(profile, region)`, `DEFAULT_PROFILE`)
- **Relevance:** How a local tool picks the `weather-deploy` profile. The `make deploy` upload
  step uses the same profile locally and the ambient credentials in CI.

### README

- **Location:** `README.md` "Deploy", "Staging", "Starting and pausing an environment", "Cost
  estimate"
- **Relevance:** Deploy is rewritten in Task 9 (pipeline, approval, rollback, break-glass).
  Setup gains the bootstrap and GitHub environments and variables in Gate 2.

## External

### GitHub OIDC

- **Docs:** https://docs.github.com/en/actions/reference/security/oidc and
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- **Subjects:** `repo:<owner>/<repo>:pull_request`, `repo:<owner>/<repo>:ref:refs/heads/main`,
  `repo:<owner>/<repo>:environment:<name>`. A job that names an environment gets the environment
  subject instead of the ref subject.
- **Dependabot:** GitHub doesn't mint OIDC tokens for Dependabot-triggered runs. Keep
  `id-token: write` on the jobs that need it, not the workflow, so the other jobs still run and
  report.

### Trivy compromise (why not Trivy)

- https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23 (CVE-2026-33634)
  and https://www.wiz.io/blog/trivy-compromised-teampcp-supply-chain-attack. From Feb 27 to Mar 22,
  2026, mutable `trivy-action`/`setup-trivy` tags were force-pushed to a credential stealer that
  ran before the real scan.

### Checkov

- https://github.com/bridgecrewio/checkov, "Suppressing and Skipping Policies": an inline
  `checkov:skip=<check_id>:<suppression_comment>` inside the resource block, one per line. The
  comment is optional in Checkov, so the project enforces it.

### terraform test

- https://developer.hashicorp.com/terraform/language/tests and `.../tests/mocking`:
  `mock_provider` generates computed attributes, `override_data` supplies chosen values,
  assertions may reference any named value in the configuration (locals included), and
  `expect_failures` reliably covers one checkable object per run, apart from `check` blocks.

### S3 conditional writes

- https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html: a bucket
  policy can Deny `s3:PutObject` when `s3:if-none-match` is Null, forcing `If-None-Match: *`.
  Multipart uploads need an `s3:ObjectCreationOperation` exemption, and copies into the bucket
  stop working. Neither applies to a single small zip.

### IAM

- Service Authorization Reference (per service): which actions accept `aws:ResourceTag`,
  `aws:RequestTag` and `aws:TagKeys`. Task 6 builds the gap list from it.
- Permissions boundaries: `iam:PermissionsBoundary` condition key on `CreateRole`,
  `PutRolePolicy`, `AttachRolePolicy`, `PutRolePermissionsBoundary`.
