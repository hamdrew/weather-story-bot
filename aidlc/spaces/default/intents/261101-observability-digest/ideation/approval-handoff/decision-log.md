# Decision Log: Ideation

Decisions the owner made during Ideation, in order. Sources: the questions files under `ideation/`, the
intent statement, stakeholder map, scope document, intent backlog and wireframes.

| # | Decision | Stage | Source |
|---|----------|-------|--------|
| D1 | Approach the request as an open idea, not from the old roadmap; widen it to review the logging strategy so alarms don't depend on log wording | Plan | Plan approval |
| D2 | The problems: unseen warnings, no at-a-glance health, alarms tied to log wording | Intent Capture | Q1 |
| D3 | The owner is the only reader | Intent Capture | Q2 |
| D4 | Success is measured by: none missed (named kinds), healthy in under a minute, and an automated test that alarms survive rewording | Intent Capture | Q3, Q10, Q12, Q13 |
| D5 | Trigger: learning observability on AWS | Intent Capture | Q4 |
| D6 | Out: Telegram changes, services outside AWS; alert emails open to change | Intent Capture | Q5, Q14 |
| D7 | A "warning" is anything unusual; "none missed" covers a named list | Intent Capture | Q6, Q10 |
| D8 | Extra cost up to about $5 a month | Intent Capture | Q9 |
| D9 | Remove the weekly digest; warnings live on the dashboard (replaces Q7, Q8, Q11) | Intent Capture | Q15 |
| D10 | Health view is worth having first, and is delivered first | Scope Definition | Q1, Q4 |
| D11 | All capabilities and a broader logging tidy-up are must-haves; a full logging review is its own deliverable | Scope Definition | Q2, Q3 |
| D12 | No deadlines; done when running in production; other offices out | Scope Definition | Q5, Q6, Q7 |
| D13 | Dashboard layout: one verdict on top, counts and recent list, one page, readable on a phone, standard look | Rough Mockups | Q1 to Q5 |
| D14 | Show errors the same way as warnings | Intent Capture (raised at Rough Mockups) | Q16 |
| D15 | Errors change the verdict, warnings don't; no data gives "unknown", which wins; one dashboard per environment | Rough Mockups | Q6, Q7, Q8, review R-07 |
| D16 | Any warning trips an alarm that emails the owner (replaces "never notifies" for warnings) | Intent Capture (raised at Approval & Handoff) | Q17, Approval Q1 |
| D17 | Accept the remaining risks; go into Inception | Approval & Handoff | Q1, Q2 |
