# Code Summary: u3-health-dashboard

## Files created or modified

| File | Change | Slice |
|------|--------|-------|
| `infra/bootstrap/services.tf` | New `dashboards` service (sid `Dashboard`; read `GetDashboard`; create `PutDashboard`; manage `PutDashboard` and `DeleteDashboards`; no tag actions) and the local `no_resource_level_writes = ["cloudwatch:PutCompositeAlarm"]` | 1 |
| `infra/bootstrap/locals.tf` | `names.dashboard` and `arns.dashboard`; `unknown` and `not-healthy` added to production's exact alarm list | 1 |
| `infra/bootstrap/apply.tf` | New `CompositeAlarmWrite` statement (`PutCompositeAlarm`, resource `*`, no conditions); `CompositeAlarmWrite` and `WritesWithoutTagConditions` assigned to the `access` group; size comment updated | 1 |
| `infra/bootstrap/tests/apply_roles.tftest.hcl` | `CompositeAlarmWrite` added to both sid exemption lists; 4 new runs (15 to 19) | 1 |
| `infra/bootstrap/tests/plan_roles.tftest.hcl` | 2 new runs (7 to 9): the plan role reads dashboards and holds no write; the plan read policy stays under the size budget | 1 |
| `infra/dashboard.tf` (new) | Two action-free composite alarms (`<name>-unknown`, `<name>-not-healthy`) and one dashboard `<name>`; widgets built from ordered lists with computed positions | 2 |
| `infra/tests/dashboard.tftest.hcl` (new) | 14 runs against the mock provider (`command = apply`) | 2 |

`infra/monitoring.tf` is untouched. No Python, workflow, README or CLAUDE.md change.

## Key implementation decisions

- **Everything reads from the alarms.** Rule terms, tiles, charts and annotations take names, metrics, statistics, periods and thresholds from the `aws_cloudwatch_metric_alarm` resources, so the page cannot drift from what the alarms do, and Terraform orders create and destroy itself (NFR6.9).
- **Rows with a use flag** and one merged options object build the tiles, so both `fill` settings share one type; null `dimensions` (`quiet`, `repost-loop`) read as none.
- **Rule syntax in one local.** `local.rule_term_format` holds the quoted form `ALARM("name")`; the unquoted fallback is a one-line change, to be taken only if the first staging apply rejects the quotes.
- **Positions are computed** from row heights and widget widths; a precondition fails any row wider than 24 columns. The verdict area (key, verdict list, signals-off list) is 11 grid units.
- **Chart design (D-P4).** Each chart is the alarm's own metric plus a horizontal threshold annotation, shaded on the breaching side from the comparison operator.
- **Bootstrap permissions.** `PutCompositeAlarm` is its own statement on `*` because AWS accepts no narrower resource for it; dashboards have no tags, so their names alone scope them (staging prefix, production exact). `WritesWithoutTagConditions` moved to the `access` group to balance sizes.
- **Bootstrap tests read `local.apply_statements`** and not the for_each data source, which avoids the Terraform 1.16.6 crash that a failed assertion on marked values causes.

## Policy sizes (proxy, production)

access 4,171, roles-tags 4,039, writes 4,437 characters against the 5,000 test budget (the managed-policy limit is 6,144). Headroom is about three more production alarm names, so Units 4 and 5 must regroup or raise the budget with a stated margin.

## Test coverage summary

| Suite | Result |
|-------|--------|
| `terraform -chdir=infra test` | 44 passed (30 existing, 14 new) |
| `terraform -chdir=infra/bootstrap test` | 37 passed (31 existing, 6 new) |
| `mise run test` | 300 passed |
| `mise run lint` | clean (ruff, format, ty, `terraform fmt`, actionlint, zizmor) |
| `mise run scan` | Checkov 183 passed, 0 failed, 18 skipped, no new skip |

The developer reported these results and I reran both Terraform suites after the hand-back (44 and 37 passed). The developer also mutation-checked the new tests: breaking a composite name, a layout height, a chart fill side and a rule term each turned the matching runs red.

The Terraform tests are not line-measured. The 80% line-coverage floor applies to `src/weather_story_bot/`, which this unit does not touch; Build and Test checks it on the full suite.

## Tests written but not executed, and checks not made

- `mise run plan`, `mise run deploy`, `mise run bootstrap-plan` and `mise run bootstrap-deploy`: they need credentials and the owner's word.
- Whether CloudWatch accepts the quoted rule terms: only the first staging apply shows it.
- The page at 1440 x 900 and 390 px, and the 24-hour watch: after the owner's deploy.
- `fill = false` is not exercised end to end: a test cannot flip a local. The shared metric row and the no-dimensions case are checked, and the shape builds from the same rows.
- The extension-point stand-in covers the rule (one extra term, still well formed and under 1,000 characters) and the layout (each `y` equals the heights above it). It does not append a real row, because a test cannot override a local.

## Deviations from the plan

1. **`unknown` rule term order.** It follows tile order (D-C2): `ALARM(missed-runs)`, then `INSUFFICIENT_DATA` for missed-runs, errors, quiet, repost-loop. The infrastructure specification's example listed errors first. The tests pin the built order; the meaning is the same.
2. **Requirement targets.** NFR6.5 (the owner applies the bootstrap change by hand) and NFR6.10 (staging before production) are process rules; their targets are the bootstrap file's comments and the unchanged pipeline, not new code.

## For the owner

- Apply slice 1 with `mise run bootstrap-deploy` (MFA) before slice 2 merges, when no pipeline run is active.
- Read and accept the `*` scope for `PutCompositeAlarm`: the staging apply role could overwrite production's two verdict composites, and a composite can carry actions.
- Check the account has no other composite alarms and no other custom dashboards (three are free).
- A failed first apply can leave one composite created; the re-run converges. Revert slice 2 before slice 1.
