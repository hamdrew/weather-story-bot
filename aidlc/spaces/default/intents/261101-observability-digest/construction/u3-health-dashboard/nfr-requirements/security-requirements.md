# Security Requirements: u3-health-dashboard

## Sources

- `infra/bootstrap/services.tf`, `apply.tf`, `locals.tf`: the apply roles' CloudWatch permissions today
- `infra/monitoring.tf`: how the existing alarms are named and tagged
- Terraform AWS provider 6.71.0 documentation: `aws_cloudwatch_composite_alarm` (supports `tags`) and `aws_cloudwatch_dashboard` (no `tags` argument; exports `dashboard_arn`)
- `aidlc/spaces/default/memory/project.md` rules: no AWS credentials to test jobs; the bootstrap stack is applied by hand with MFA, never by the pipeline
- `inception/requirements-analysis/requirements.md`: NFR1, NFR6

The dashboard holds no secrets and no story content: it shows metric values and alarm states. The unit adds no
authentication, no data store and no network surface, so those do not apply. What it does touch is the
pipeline's AWS permissions, and that is a blocking finding.

## Finding: the pipeline cannot create these resources today

The apply roles (`ci-apply-staging`, `ci-apply-production`) allow only `cloudwatch:PutMetricAlarm`,
`cloudwatch:DeleteAlarms` and `cloudwatch:TagResource` on `arn:aws:cloudwatch:<region>:<account>:alarm:<name>`
(`services.tf`, service `alarms`), plus `cloudwatch:DescribeAlarms` as a read. Production's alarm names are an
exact list of six (`locals.tf`). Nothing allows `cloudwatch:PutCompositeAlarm`, and nothing allows any dashboard
action. On the first merge to `main` the staging apply would fail with `AccessDenied` on the composite alarms and
the dashboard, and production would never be reached. The failure is safe (nothing half-built is harmful and a
re-run after the fix completes it), but it stops the pipeline, so the permission change has to land first.

## Requirements

| ID | Requirement | Check | Origin |
|----|-------------|-------|--------|
| NFR6.2 | Before the U3 Terraform merges, each apply role can create, update and delete the two composite alarms and the dashboard of its own environment, and no other environment's. | Bootstrap Terraform tests (`infra/bootstrap/tests/apply_roles.tftest.hcl`) show each environment's role allowed on its own names and refused on the other's; the first staging pipeline apply succeeds. | NFR6 |
| NFR6.3 | Each plan role can read the new resources so `terraform plan` refreshes them: `cloudwatch:GetDashboard` on the dashboard (`DescribeAlarms` already covers composite alarms). Plan roles stay read-only. | `plan_roles.tftest.hcl`: plan roles hold no write action. | NFR6 |
| NFR6.4 | The new permissions are as narrow as the existing ones: composite alarms join the `alarms` service (the same name patterns and the same `Environment` tag conditions, with `PutCompositeAlarm` added beside `PutMetricAlarm`); dashboards are a new service scoped by name pattern, because a dashboard carries no tags and so no tag condition can apply. Staging matches by prefix; production by exact name; neither pattern can match the other's dashboard. | Bootstrap tests assert the resource patterns, as `each_environment_creates_its_own_misconfigured_alarm` does for alarms. | NFR6, project rule on least privilege |
| NFR6.5 | The bootstrap change is applied by the owner with the MFA profile (`mise run bootstrap-deploy`), never by the pipeline, and an agent asks before running it. | Project rules; the plan is reviewed before apply. | NFR6, project rules |
| NFR6.6 | The three apply-role policy documents per environment stay under IAM's 6,144-character managed-policy limit after the change. The `writes` group was about 4.5 KB in production. | `terraform plan` of the bootstrap stack succeeds; Infrastructure Design measures the rendered size. | NFR6 |
| NFR5.5 | The page and the composite alarms show no secret: no Telegram token, caption, story text or request body reaches a metric, an alarm description or a widget. The unit reads only existing metrics and alarm states and adds no log or metric filter, so the bot's output and logs are untouched. | Review of the dashboard body in the Terraform test; no new log or metric filter (BR6.1). | NFR5, project rule on the token |

## To confirm in Infrastructure Design

The exact condition keys CloudWatch supports for `PutCompositeAlarm` (tag keys are expected, as for
`PutMetricAlarm`) and for the dashboard actions (none are expected). The AWS Service Authorization Reference could
not be read in this stage, so these are expectations, not facts. If `PutCompositeAlarm` does not honour the tag
conditions, the `Creates` and `Changes` statements would refuse it and the composites would need their own
statement. The first plan against the mock provider will not catch this; the first staging apply will, so
Infrastructure Design should settle it from the reference before then.

## Threat considerations

| Threat | Where | Mitigation |
|--------|-------|------------|
| A pipeline role writing a dashboard or alarm in the wrong environment | Dashboard actions have no tag condition | Name patterns that cannot overlap (NFR6.4) |
| Permission creep from widening the alarm patterns for convenience | `locals.tf` alarm names | Production's names stay an exact list; the two new names are added, no wildcard (NFR6.4) |
| The pipeline applying its own permission change | Bootstrap stack | Owner applies by hand with MFA (NFR6.5) |

## Not applicable

Authentication, authorization of dashboard viewers (the owner's own AWS sign-in, unchanged), encryption (CloudWatch
holds dashboards and alarm configuration encrypted by default; nothing sensitive is stored) and compliance regimes.
