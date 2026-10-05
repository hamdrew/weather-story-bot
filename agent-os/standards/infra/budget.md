# Budget

What the project costs is a design input, not something found on the bill. The shape that matters:
a small fixed monthly cost, and everything else paid per use.

- **Fixed monthly cost stays O(1) in offices.** Alarms, the SNS topic and the budget are shared by
  every office, so adding one adds usage cost only. A resource per office (an alarm, a custom
  metric, a table, a schedule) is the thing to refuse. See `global/principles` (the office is the
  unit of isolation) for what is per office instead
- **Per-office visibility comes from queries and reports**, not per-office alarms or custom
  metrics. Logs Insights, the ledger and the archive already hold the per-office facts
- **Prefer pay-per-use with no idle cost.** Lambda, on-demand DynamoDB, S3 and the scheduler cost
  nothing while idle. A resource that bills by the hour (a NAT gateway, a provisioned table, an
  always-on endpoint) needs a reason in the spec
- **Every spec carries a `cost.md`**, produced by `make cost`, with the figures at the scales that
  spec cares about, what is fixed and what scales, and what Infracost doesn't price. Record the
  date and the Infracost version. When a spec changes nothing, say so and show the unchanged total
- **Retention is a cost decision.** The archive and state table are kept forever
  (`infra/data-retention`), so storage grows every month. State what a new store keeps and for how
  long before adding it
- **The estimate is list price**, with no free tier subtracted. It is the worst case. Say so, then
  say what the account's free allowances do to it (the CloudWatch free alarms are the one that
  matters here)
- **The account budget (`monthly_budget_usd`) rises deliberately**, in the spec that raises
  expected spend, with the new figure in that spec's `cost.md`. It never rises to silence an alert
- A new environment is a new `Scenario` in `scripts/infracost_usage.py` and a project in
  `infracost.yml`, so its cost is estimated before anything is created
