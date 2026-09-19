# Alarms

The alert email is the only context you get when an alarm fires. It must say what went wrong and where to look, without opening the repo.

Every `aws_cloudwatch_metric_alarm` has:

- `alarm_description` covering what happened (in plain words), the likely causes, what to check (log message names, schedule and field names) and `${local.logs_console_url}`
- `alarm_actions` and `ok_actions` set to `aws_sns_topic.alerts.arn`. The OK email tells you it resolved
- A `treat_missing_data` setting with a comment on what missing data means. For log-filter metrics, a quiet period has no data points, not zeros
- Tunable thresholds and windows as `variables.tf` entries with defaults and validation, listed in `terraform.tfvars.example`

```hcl
# Nothing posted means no data points, not zeros.
treat_missing_data = "breaching"
```

- Custom metrics use `local.metric_namespace`, and the alarm references the filter's `metric_transformation[0].name`
- A log metric filter matches an exact message, so see `testing/log-contracts`
