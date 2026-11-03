# Reliability Requirements: u3-health-dashboard

## Sources

- `functional-design/functional-spec.md` (verdict state table, edge cases) and `rules.md` (BR1.1 to BR1.7)
- `infra/monitoring.tf`: missing-data settings of the four health alarms (`errors` and `repost-loop` treat missing data as not breaching; `missed-runs` and `quiet` as breaching)
- Terraform AWS provider 6.71.0 documentation, `aws_cloudwatch_composite_alarm`: an alarm cannot be destroyed while a composite alarm depends on it
- `aidlc/spaces/default/memory/team.md`: deployment, rollback and the 35-day data undo window
- `inception/requirements-analysis/requirements.md`: NFR5, NFR6

The verdict is only as reliable as the four alarms under it, and this unit must not make them less so.

## Requirements

| ID | Requirement | Check | Origin |
|----|-------------|-------|--------|
| NFR5.1 | The unit changes none of the five existing alarms: thresholds, periods, evaluation periods, missing-data settings and actions are as before (BR1.7). The first plan shows only additions: two composite alarms and one dashboard per environment. | `terraform plan` output in the pull request; a Terraform test compares the five alarms' settings. | NFR5, FR5.3 |
| NFR5.2 | The verdict alarms carry no action, so they send no email and the alerts topic is untouched (BR1.1); they stay out of `alarm_names`, so `mise run start` and `pause` need no change. | Terraform test: no `alarm_actions`, `ok_actions` or `insufficient_data_actions` on either composite, and `alarm_names` lacks them. | NFR5, FR5.3 |
| NFR5.3 | Removing this unit loses nothing: the composites and the dashboard hold no data, so a revert and redeploy restores the previous state and a re-apply restores this one. No data window applies. | Rollback is the team's own: revert the commit, the pipeline redeploys. | NFR5, NFR6 |
| NFR5.4 | A paused or idle environment reads UNKNOWN, not HEALTHY (Q2 A, BR1.2): a missed-runs alarm in ALARM, or any of the four alarms without data, puts the unknown alarm in ALARM. The page says so in words (BR5.1). | Staging checkpoint: with staging's schedule paused the page reads UNKNOWN, and the key explains why. | FR1.1, NFR5 |
| NFR6.9 | The composites are created after the four alarms they read and removed before them. Terraform orders this itself when each rule is built from the alarm resources' names (BR1.6); a rule typed as plain strings would lose the ordering and fail on destroy. U4 recreates some alarms, so the same rule keeps U4's changes safe. | Terraform test: each rule term is an existing alarm resource's name (BR1.6). | NFR6 |
| NFR6.10 | A deploy of this unit to staging does not wait for, or depend on, a production deploy. The pipeline's order is unchanged: staging, then production after the owner's approval. | Pipeline run read with `gh run view <id> --json jobs`. | NFR6 |

## Failure modes

| Failure | Effect | Handling |
|---------|--------|----------|
| The pipeline lacks the new permissions | The staging apply fails with `AccessDenied`; nothing is harmed | Land and apply the bootstrap change first (NFR6.2, NFR6.5) |
| An alarm under a composite is renamed or removed | Terraform cannot delete it while a composite depends on it | Rules built from resources (NFR6.9) |
| A health alarm has no data | The verdict reads UNKNOWN by design | Q2 A; the key says so (NFR5.4) |
| CloudWatch is slow to update a composite after an alarm changes | The page can lag the alarm list by a short time | Accepted; the alarm lists beside the verdict show each alarm's own state |

## Availability

No availability target for the page: it is a console feature used by hand. The bot's own availability is
unchanged and is what the verdict reports.
