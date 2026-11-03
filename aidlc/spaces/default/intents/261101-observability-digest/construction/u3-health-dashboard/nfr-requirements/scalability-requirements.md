# Scalability Requirements: u3-health-dashboard

## Sources

- `functional-design/rules.md`: BR1.6 (one extensible list), BR4.2 (room for U5's totals), BR6.1
- `inception/units-generation/unit-of-work.md`: U5 adds an area, a totals row and an alarm to this unit's resources
- `inception/requirements-analysis/requirements.md`: NFR1, NFR6

There is no load to scale: one owner opens one page per environment. The growth that matters is in what other
units add to this unit's two composite alarms and one dashboard.

## Requirements

| ID | Requirement | Check | Origin |
|----|-------------|-------|--------|
| NFR6.7 | U5 can add its error-log alarm to the not-healthy rule, and its area and totals row to the dashboard, by appending to the ordered lists this unit defines. It changes no widget of this unit and no rule term. The dashboard's widget positions are computed from one ordered list, so inserting an area moves what is below it. | A Terraform test appends a stand-in term and a stand-in area and sees the rule and the layout still valid (BR1.6, BR4.1). | NFR6, FR1.1 |
| NFR1.4 | The dashboards stay inside the free allowance of 3 custom dashboards (50 metrics each) per account: this unit uses 2 (one per environment), so one spare remains. A third dashboard, or a dashboard above 50 metrics, is a cost decision for the owner. | Count in the Terraform test: one `aws_cloudwatch_dashboard` per environment; metric count per dashboard at most 50. | NFR1 |
| NFR6.8 | A composite rule stays far under CloudWatch's rule length limit (10,240 characters per the provider documentation). Four to six alarm names per rule use well under 1,000. | Terraform test checks the rendered rule length. | NFR6 |

## Not applicable

Load projections, scaling triggers, concurrency and data growth: the unit has no compute and stores no data.
