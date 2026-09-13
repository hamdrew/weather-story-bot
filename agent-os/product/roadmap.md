# Product Roadmap

## Phase 1: MVP

- **Detect new stories:** Check the NWS MKX (Milwaukee/Sullivan) office on a schedule and notice when a new Weather Story is published.
- **Push notification via Telegram:** Post each new story's image and description to Telegram. Telegram handles both the notification and the display.
- **MKX only:** Only one office is needed for launch. The design should still make it easy to add more offices later.
- **Failure alerts:** Watch the Lambda and email me when it fails or stops running on schedule. The Gmail app shows the email as a push notification on my iPhone. Alerts don't go through Telegram, because Telegram could be the thing that's broken. Send a follow-up email when things recover, and don't alert on a single flaky run.
- **Silent-problem alerts:** Email me when the bot runs without errors but something is still wrong:
  - **Gone quiet:** No stories posted for a couple of days (for example, the NWS API changed and now returns nothing).
  - **Repost loop:** Far more posts than normal in a short time.
- **Cost alert:** Email me if monthly AWS spend for the account goes over a small budget.
- **Cost estimate command:** A command I can run whenever I want (`make cost`) that shows the estimated monthly AWS cost of what's in `infra/`, using Infracost. It doesn't run before deploys or in CI.

## Phase 2: Post-Launch

- **Multiple offices:** Support more NWS offices, with a separate Telegram channel for each office.
- **Story archive:** Save past Weather Stories so they can be looked up later.
- **CI/CD pipeline:** Deploy from GitHub Actions instead of running `make deploy` from my laptop.
  - **Starting approach:** One workflow that reuses the Makefile. Pull requests run lint, test, build, and `terraform plan`. Merges to `main` run the same steps plus `terraform apply` in a protected environment.
  - **AWS access:** GitHub OIDC with a narrowly scoped IAM role (managed in Terraform), so no long-lived keys. Variables that aren't committed (`nws_user_agent`, backend config) come from GitHub Actions variables.
  - **Fixes it needs first:** Make the Lambda zip reproducible so a plan only shows a change when the code really changed. Make `plan`/`deploy` build first, or fail if the zip is missing.
  - **Later, if needed:** Upload versioned zips to S3 (keyed by git SHA) so plan and apply can be separate jobs with an approval between them, and rollback is just re-applying an older SHA.
  - **Alternative to evaluate: a cloud Terraform runner** (HCP Terraform, or Spacelift/env0/Scalr, which can also run OpenTofu).
    - **Gives:** a web UI for plans and applies, run history, approval buttons, drift detection, and policy checks.
    - **Costs:** another account and vendor, and variables kept in the platform. The S3 backend already covers state and locking for a project this size.
    - **The zip problem:** Remote runs don't have `build/lambda.zip`, because it's gitignored. Runs triggered from GitHub need S3 zips (above) or a build step inside the run (Spacelift hooks with a custom image). HCP Terraform can't run a build first, so either GitHub Actions builds the zip and starts a CLI-driven run that uploads it, or it uses S3 zips.
    - **If chosen:** Start with S3 zips so the runner never needs a local file. Move state from the S3 backend with `terraform init -migrate-state`. Point the OIDC role's trust at the platform instead of GitHub. Check current free-tier limits before committing.
- **Channel promotion (long-term):** Possibly promote the per-office channels to a wider audience.
