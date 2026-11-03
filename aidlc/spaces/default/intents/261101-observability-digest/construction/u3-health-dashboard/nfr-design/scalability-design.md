# Scalability Design: u3-health-dashboard

## Sources

- `nfr-requirements/scalability-requirements.md` (NFR6.7, NFR1.4, NFR6.8)
- `functional-design/rules.md` (BR1.6, BR4.1, BR4.2) and `inception/units-generation/unit-of-work.md` (what U5 adds)
- Terraform AWS provider 6.71.0 documentation: composite alarm `alarm_rule` maximum 10,240 characters

Nothing here handles load. What grows is what U4 and U5 add to this unit's two composite alarms and one
dashboard, and the design is how they add it without editing U3's pieces.

## Design decisions

| ID | Decision | Satisfies |
|----|----------|-----------|
| D-C1 | **Two extension points, both ordered lists in `infra/dashboard.tf`:** `local.not_healthy_alarms` (the alarms whose ALARM state means NOT HEALTHY; today errors, quiet, repost-loop) and `local.dashboard_rows` (the rows of widgets, top to bottom). U5 appends its error-log alarm to the first and inserts its totals row and its errors-and-warnings area into the second. Nothing in U3 is edited. | NFR6.7, BR1.6 |
| D-C2 | **Rules are built, not written.** `alarm_rule` is `join(" OR ", ...)` over a list comprehension of the alarm resources' names. The unknown rule uses the missed-runs ALARM term and an INSUFFICIENT_DATA term for each entry of `local.health_signals`. A new health signal added to that list therefore joins both rules and gets a tile and a chart. | NFR6.7, BR1.2, BR1.3 |
| D-C3 | **Rendered rule length is checked** by the Terraform test against 10,240 characters, with a stated ceiling of 1,000 so a runaway list is caught long before the service limit. Today a rule is under 400 characters. | NFR6.8 |
| D-C4 | **Free dashboard allowance accounting.** One dashboard per environment: two of three free dashboards. The test counts `aws_cloudwatch_dashboard` resources per environment (one) and metrics per dashboard (at most 50). The owner confirms the account holds no other custom dashboards before NFR1.4 is treated as met; this is not checkable offline. | NFR1.4 |
| D-C5 | **Stateless and idempotent.** Applying again changes nothing; the body is a pure function of the alarms and variables. | NFR6.7 |

## Capacity table

| Dimension | Today | Ceiling | Where it is checked |
|-----------|-------|---------|--------------------|
| Widgets per dashboard | 13 | 30 by design (the service limit was not checked) | Terraform test |
| Metrics per dashboard | 8 | 50 (free allowance) | Terraform test |
| Terms in the unknown rule | 5 | rule under 1,000 characters | Terraform test |
| Terms in the not-healthy rule | 3 | rule under 1,000 characters | Terraform test |
| Custom dashboards in the account | 2 (after this unit) | 3 free | Owner confirms |

## Not applicable

Load distribution, partitioning, auto-scaling and concurrency.
