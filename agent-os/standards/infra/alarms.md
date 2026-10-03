# Alarms

The alert email is the only context you get when an alarm fires. It must say what went wrong and where to look, without opening the repo.

Every `aws_cloudwatch_metric_alarm` has:

- `alarm_description` covering what happened (in plain words), the likely causes, what to check (log message names, schedule and field names) and `${local.logs_console_url}`
- `alarm_actions` and `ok_actions` set to `aws_sns_topic.alerts.arn`. The OK email tells you it resolved
- A `treat_missing_data` setting with a comment on what missing data means. For log-filter metrics, a quiet period has no data points, not zeros
- Tunable thresholds and windows as `variables.tf` entries with defaults and validation, listed in `infra/envs/production.tfvars.example`

```hcl
# Nothing posted means no data points, not zeros.
treat_missing_data = "breaching"
```

- `actions_enabled = false` with `lifecycle { ignore_changes = [actions_enabled] }`: every environment is created paused, and `make start` / `make pause` toggle the actions with the schedule. An alarm that treats missing data as breaching because of the schedule (`missed-runs`, `quiet`) then sits in ALARM without emailing while paused. Add the alarm to `local.alarm_names` (the `alarm_names` output), or the toggle won't reach it
- Custom metrics use `local.metric_namespace`, which is per environment, and the alarm references the filter's `metric_transformation[0].name`
- A log metric filter matches an exact message, so see `testing/log-contracts`
