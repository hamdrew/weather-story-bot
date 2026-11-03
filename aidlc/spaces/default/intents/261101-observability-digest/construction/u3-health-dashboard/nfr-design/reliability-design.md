# Reliability Design: u3-health-dashboard

## Sources

- `nfr-requirements/reliability-requirements.md` (NFR5.1 to NFR5.4, NFR6.9, NFR6.10) and `security-requirements.md` (NFR6.2, NFR6.5)
- `functional-design/functional-spec.md` (verdict state table, edge cases) and `rules.md` (BR1.1 to BR1.7)
- `infra/monitoring.tf`: missing-data settings (`errors` and `repost-loop` treat missing data as not breaching; `missed-runs` and `quiet` as breaching)
- Terraform AWS provider 6.71.0 documentation, `aws_cloudwatch_composite_alarm`: an alarm cannot be destroyed while a composite depends on it
- `aidlc/spaces/default/memory/team.md`: deploy on merge, staging then production after approval, rollback by revert

## Design decisions

| ID | Decision | Satisfies |
|----|----------|-----------|
| D-R1 | **Delivery order is part of the design.** (1) Bootstrap slice: the permission change and its tests; the owner reviews `bootstrap-plan` and runs `bootstrap-deploy` with MFA, from the branch, before the pull request merges, so `main` never describes permissions that are not applied. (2) Dashboard slice: merging it deploys staging, then production after approval. The dashboard slice must not merge before step 1 is applied. A laptop deploy to staging runs as the owner and so proves nothing about the CI role; only the first pipeline run of the dashboard slice proves NFR6.2. | NFR6.2, NFR6.5, NFR6.10, NFR6.1 |
| D-R2 | **A failed first apply is safe and repeatable.** If it runs before the permissions land, `terraform apply` fails on the composite alarms and the dashboard with AccessDenied; the four health alarms it reads already exist and are untouched, and a re-run after the bootstrap apply completes it. The pipeline reports red on staging and never reaches production. | NFR6.2 |
| D-R3 | **No action on either composite**, enforced by a Terraform test that fails when either carries `alarm_actions`, `ok_actions` or `insufficient_data_actions`, and when `local.alarm_names` lists either. `mise run start` and `pause` need no change. | NFR5.2 |
| D-R4 | **Existing alarms are read, never edited.** `dashboard.tf` references the alarm resources (`aws_cloudwatch_metric_alarm.errors` and so on) but defines none. A Terraform test pins the five alarms' thresholds, periods, evaluation periods, missing-data settings and action lists; the first pull-request plan must show only additions. | NFR5.1 |
| D-R5 | **Destroy ordering by reference.** Each rule term is built from `aws_cloudwatch_metric_alarm.<name>.alarm_name`, so Terraform creates the composites after the alarms and destroys them before. A rule typed as a string would lose this and fail on destroy, as the provider warns. The test asserts every term is an existing alarm's name. U4's recreation of alarms depends on this. | NFR6.9 |
| D-R6 | **Rule syntax is checked by the first staging apply.** Terms are written `ALARM("name")` and `INSUFFICIENT_DATA("name")` with the name in double quotes; a rejected rule fails the staging apply with a validation error and creates nothing. If CloudWatch rejects the quoted form, the unquoted form is the one-line fallback. The mock provider cannot check this. | NFR6.9 |
| D-R7 | **Idle and paused environments read UNKNOWN by design.** A paused schedule makes `missed-runs` go into ALARM within an hour, which puts the unknown alarm in ALARM and the page reads UNKNOWN. The key says so. Alarm actions on paused environments are toggled by the existing scripts and the composites have none, so the verdict still computes while paused. | NFR5.4 |
| D-R8 | **Rollback is the team's own:** revert the commit and let the pipeline redeploy. The composites and the dashboard hold no data, so nothing is lost and no recovery window applies. A bootstrap rollback is a revert plus `bootstrap-deploy`. | NFR5.3 |
| D-R9 | **Staging deploys first and independently.** The pipeline order is unchanged: staging on merge, then production after the owner approves the saved plan. A plan with no changes asks for no approval. | NFR6.10 |

## Failure modes

| Failure | Effect | Handling |
|---------|--------|----------|
| Permissions not applied before the dashboard slice merges | Staging apply fails with AccessDenied | D-R1, D-R2 |
| CloudWatch rejects the quoted rule syntax | Staging apply fails on the composites, nothing created | D-R6 fallback |
| A health alarm renamed or removed | Terraform refuses to destroy it while a composite depends on it | D-R5: the rule is rebuilt from the resource in the same apply |
| CloudWatch evaluates a composite a short time after an alarm changes | The page can briefly disagree with the alarm list | Accepted; both lists print alarm states |
| An alarm has no data | The page reads UNKNOWN | By design (Q2 A, D-R7) |

## Availability

No target for the page. The bot's availability is what the verdict reports, and this unit changes none of it.
