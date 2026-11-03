# Tech Stack Decisions: u3-health-dashboard

## Sources

- `aidlc/spaces/default/codekb/weather-story-bot/technology-stack.md`
- `inception/requirements-analysis/decisions.md`: ADR-004 (monitoring stays in `infra/`), ADR-006 (the verdict is two composite alarms)
- `functional-design/rules.md` (BR1.1, BR1.6, BR3.1, BR6.1, BR6.2)
- Terraform AWS provider 6.71.0 documentation (`aws_cloudwatch_composite_alarm`, `aws_cloudwatch_dashboard`)
- AWS CloudWatch pricing, checked in this stage: a composite alarm costs $0.50 per month; a standard alarm metric costs $0.10 per month after 10 free; the first 3 custom dashboards (up to 50 metrics each) are free; the owner's own dashboard views in the console add no metric-data charge
- `infra/bootstrap/services.tf`, `apply.tf`, `locals.tf`

## Decisions

| ID | Decision | Rationale | Alternatives rejected |
|----|----------|-----------|----------------------|
| NFR1.1 | Two composite alarms per environment (`unknown`, `not-healthy`), no action. Cost: 2 per environment x 2 environments x $0.50 = **$2.00 a month**, the unit's whole added cost. | A dashboard cannot compute one word from alarm states (ADR-006), so the verdict has to be an alarm state the page can show. Two alarms plus a printed key give the three answers. | One composite and a text key (cannot tell UNKNOWN from NOT HEALTHY); a Lambda custom widget (code to run and secure, a bill per view); Grafana or a hosted page (new service, new credentials). |
| NFR1.2 | The unit leaves $3.00 of the $5 monthly limit for U5 (its two alarm metrics and its Logs Insights queries). | NFR1 is a limit across both environments for the whole intent. | none |
| NFR1.3 | One dashboard per environment, 13 widgets, 8 metrics, inside the free allowance of 3 dashboards of up to 50 metrics. No Logs Insights widget in this unit. | Free, and a page view scans no log bytes. | A dashboard per signal (more of the allowance for no gain). |
| NFR6.13 | New file `infra/dashboard.tf` beside `monitoring.tf`; `monitoring.tf` is not edited (BR6.2). The dashboard body is `jsonencode` of an HCL local built from ordered lists, so positions are computed (NFR6.7) and Terraform tests can read the decoded body. | ADR-004; U4 and U5 edit `monitoring.tf` and would conflict if this unit did too. JSON built in HCL cannot drift from the alarm resources it names. | A hand-written JSON file or `templatefile` (strings drift from the alarms; no list to extend); editing `monitoring.tf` (merge conflicts with U4 and U5). |
| NFR2.9 | Tiles use metric math `FILL(m1, 0)` over the alarm's own metric, statistic and period, with a sparkline and the single-value view. | "0, not blank" needs a named mechanism (functional-design review); FILL is CloudWatch's own. | `treatMissingData`-style alarm settings (alarms only, not widgets); leaving blank (the page would read as broken). |
| NFR2.10 | Detail charts refer to their alarm by an alarm annotation with no separate metric list; fallback in NFR2.7. | Metric, statistic, period and threshold cannot drift from the alarm (FR5.2). | Own metric lists plus typed thresholds (drift). |
| NFR4.1 | Terraform tests in a new `infra/tests/dashboard.tftest.hcl` with `mock_provider "aws"` and `-backend=false`, decoding `dashboard_body` and the rules. Alarm ARNs are known only after apply under the mock, so the runs use `command = apply`, or `override_resource` for the ARN values. | The team's offline Terraform test practice; the same mock provider as the existing `infra/tests/`. | A live test (not offline); asserting on strings (breaks on formatting). |
| NFR4.2 | The bootstrap change has its own offline tests in `infra/bootstrap/tests/` (each environment allowed on its own composite and dashboard names and refused on the other's; plan roles hold no write action). | The permission change is the riskiest part of the unit and must be proved before anyone applies it. | Relying on the first staging apply to find a wrong pattern. |
| NFR4.3 | `mise run lint`, `test`, `tftest` and `scan` pass in the `checks` job; a Checkov finding on the new resources is fixed or skipped inline with a reason. Line coverage of the Python source stays at or above 80% (unchanged, since no Python changes). | Team testing posture and the project rule on Checkov skips. | A skip without a reason (fails the scan). |
| NFR6.1 | The unit is delivered through the pipeline as revertible pull requests (see delivery order below), each saying what to watch after merge. | Team practice. | One large pull request. |
| NFR6.14 | The permission change goes in the bootstrap stack, as its own slice and pull request ahead of this unit's (see delivery below). It adds `PutCompositeAlarm` to the `alarms` service's create and manage lists, adds the two composite names to production's alarm name list, and adds a new unconditioned `dashboards` service (kind `dashboard`, ARN `arn:aws:cloudwatch::<account>:dashboard/<name>`, create `PutDashboard`, manage `PutDashboard` and `DeleteDashboards`, read `GetDashboard`). The dashboard has no tags, so it sits with schedules and budgets in the statements that carry no tag condition. | The pipeline cannot apply this unit otherwise (security-requirements). Precedent: the Phase 2.2 Stage 2 bootstrap change shipped as its own pull request (#30). | Granting `cloudwatch:*` (far wider than needed); creating the dashboard by hand (leaves a resource Terraform does not own); applying the bootstrap change from the pipeline (forbidden by project rule). |

## Delivery order (NFR6)

1. A bootstrap slice: the permission change above, with its tests; the owner reviews the plan and runs
   `mise run bootstrap-deploy` with MFA (an agent asks first).
2. This unit's slice: `infra/dashboard.tf`, its tests and the AI-DLC records; merging it deploys staging, then
   production after the owner approves.

Two revertible slices rather than one, because the second cannot succeed until the first is applied by hand.
Infrastructure Design confirms this split; the owner decides at that stage's approval.

## Unchanged

Python 3.13, httpx as the only runtime dependency, boto3 dev-only, Terraform `~> 1.11`, the AWS provider version
in `infra/versions.tf`, pytest and respx. This unit changes no Python.
