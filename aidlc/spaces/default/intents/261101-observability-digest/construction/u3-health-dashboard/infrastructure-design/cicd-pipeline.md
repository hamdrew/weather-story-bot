# CI/CD Pipeline: u3-health-dashboard

## Sources

- `aidlc/spaces/default/memory/team.md` (Way of Working, Deployment) and `project.md` (Corrections: read pipeline job states with `gh run view <id> --json jobs`, never `gh run watch`, for a run stopped at the production gate)
- `CLAUDE.md` of the project: `mise run plan|deploy|bootstrap-plan|bootstrap-deploy`, who runs them, and the production break-glass rule
- `nfr-design/reliability-design.md` (D-R1 to D-R9) and `security-design.md` (D-S7)
- `infrastructure-specification.md` in this folder (the bootstrap change and the measurements)

The unit changes no build, no Lambda zip and no workflow. Its delivery is two slices, and the order matters.

## Slices

| Slice | Content | Who applies it | Reaches AWS how |
|-------|---------|----------------|-----------------|
| 1. Bootstrap permissions | The bootstrap change in `infrastructure-specification.md`, its tests, and the measured sizes | The owner, from the branch, with the MFA profile: `mise run bootstrap-plan`, review, `mise run bootstrap-deploy`. An agent asks first and never runs it | By hand; the pipeline never touches the bootstrap stack |
| 2. Dashboard | `infra/dashboard.tf`, `infra/tests/dashboard.tftest.hcl`, the AI-DLC records | The pipeline | Merge to `main` deploys staging, then production after the owner approves the saved plan |

## Order

1. Slice 1 is reviewed as a pull request, then the owner applies it **from the branch before it merges**, so `main` never describes permissions that are not applied. Merging first and applying after is acceptable if the owner prefers it; nothing deploys either way, since the pipeline does not apply the bootstrap stack.
2. Slice 2 is opened after slice 1 is applied. If it merges earlier, the staging apply fails with `AccessDenied` on the composite alarms and the dashboard, nothing harmful is left, and a re-run after slice 1 completes it.
3. A deploy of slice 2 from the laptop to staging runs as the owner and proves nothing about the CI role. Only the first pipeline run of slice 2 proves the permissions (NFR6.2).

## Stage to gate

| Stage | Gate | Evidence |
|-------|------|----------|
| Pull request, both slices | `checks` job: `lint`, `test`, `tftest`, `scan` pass; Checkov findings fixed or skipped inline with a reason | The `checks` job on the pull request |
| Slice 1 review | Plan shows only policy and statement changes; each group under 5,000 characters by the size test; the owner has done the checks listed in `infrastructure-specification.md` | `bootstrap-plan` output; bootstrap tests |
| Slice 2 pull request plan | Only additions: two composite alarms and one dashboard per environment; none of the five existing alarms changes | The plan summary of the pull request's plan job, which plans both environments with the read-only plan role (it needs the `GetDashboard` read from slice 1 only once the dashboard exists) |
| Staging deploy on merge | Green apply; the checklist in `monitoring-design.md` passes | `gh run view <id> --json jobs`, then the page at both sizes |
| Production approval | The owner approves the saved plan in the `production` GitHub environment | The approval; a plan with no changes asks for none |
| After production | 24-hour watch: the production page reads HEALTHY while the schedule runs, failed counts in the run records unchanged, no new email | The owner's check |

## Rollback

| Case | Action |
|------|--------|
| Slice 2 misbehaves | Revert the commit; the pipeline redeploys staging, then production after approval. No data is lost; the composites and dashboard are rebuilt from the same source |
| Slice 1 misbehaves | Revert plus `mise run bootstrap-deploy` by the owner |
| A rule is rejected on staging (quoted names) | Switch to the unquoted form in `dashboard.tf` and re-run; nothing was created by the failed apply |

## Secrets

None added. The unit uses no token, no parameter and no new credential; no job that runs tests or linters gains AWS credentials, and no plan is uploaded as an artifact.

## Pull request notes

Each pull request body records what changed, how it was tested, the review result and what to check after merge (the window above), and slice 1 states the `*` scope of `PutCompositeAlarm` and the owner checks explicitly.
