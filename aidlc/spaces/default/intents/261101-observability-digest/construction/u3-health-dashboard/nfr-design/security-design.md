# Security Design: u3-health-dashboard

## Sources

- `nfr-requirements/security-requirements.md` (NFR6.2 to NFR6.6, NFR5.5) and `tech-stack-decisions.md` (NFR4.2, NFR6.14)
- `infra/bootstrap/services.tf`, `apply.tf`, `plan_roles.tf`, `locals.tf`: how the CI roles are built today
- Amazon CloudWatch permissions reference, "CloudWatch API operations and required permissions for actions" (docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/permissions-reference-cw.html), read in this stage
- Terraform AWS provider 6.71.0 documentation: `aws_cloudwatch_composite_alarm` supports `tags`; `aws_cloudwatch_dashboard` does not
- `aidlc/spaces/default/memory/project.md`: no AWS credentials to test jobs; bootstrap applied by hand with MFA; ask before `bootstrap-deploy`

The dashboard shows metric values and alarm states and nothing secret. This stage designs the one security-relevant
part of the unit: the permissions the pipeline needs, and the one place they cannot be as narrow as the rest.

## Correction to the requirements (read this first)

`security-requirements.md` NFR6.4 says composite alarms join the `alarms` service with the same name patterns and
`Environment` tag conditions. The AWS permissions reference says otherwise for creating one: *"To create a composite
alarm, your `cloudwatch:PutCompositeAlarm` permission must have a `*` scope."* A permission on a narrower resource
does not work. Reading composite alarms has the same rule for `cloudwatch:DescribeAlarms`, which the apply and plan
roles already hold on `*`. The dashboard actions carry no such note.

So the design differs from NFR6.4 in one action:

| Action | Scope designed | Why |
|--------|----------------|-----|
| `cloudwatch:PutCompositeAlarm` | Resource `*`, no tag condition, in its own statement | AWS requires `*`. A tag condition on an action that may not support the tag keys would refuse every call, and the reference page for this action's condition keys could not be read here, so none is relied on. |
| `cloudwatch:DeleteAlarms`, `TagResource`, `ListTagsForResource` | Unchanged: alarm ARNs by name pattern, with the `Environment` tag conditions; production's exact list gains the two composite names | These already work on a composite alarm's ARN (`arn:aws:cloudwatch:<region>:<account>:alarm:<name>`) |
| `cloudwatch:PutDashboard`, `DeleteDashboards`, `GetDashboard` | Dashboard ARNs by name pattern, no tag condition | A dashboard has no tags in the provider, so it sits with schedules and budgets in the statements that carry none |

### What the wider scope allows, and what limits it

| Risk | Reality |
|------|---------|
| The staging pipeline role could overwrite production's composite rule (or the reverse) | True. It changes what the page displays and sends nothing: the composites have no action. The next apply of the owning environment restores it, and `terraform plan` shows the drift. |
| A pipeline role could create a composite alarm that carries an action | Possible with this scope. Whether the alerts topic would accept the publish depends on the topic's access policy, which was not checked here. The worst case is a stray email, not access to data, and a composite with an action shows in `terraform plan` as drift from this unit's no-action rule (BR1.1). |
| Deleting a composite | Still limited: `DeleteAlarms` stays scoped by name and tag. |
| Other composite alarms in the account | None known. A read of `describe-alarms --alarm-types CompositeAlarm` under the `readonly` profile was attempted and the session had expired; the owner should confirm none exist before applying. |

This is a smaller guarantee than every other CloudWatch permission in the stack, and the owner should see that
before approving. It is the only way AWS lets a role create a composite alarm.

## Design decisions

| ID | Decision | Satisfies |
|----|----------|-----------|
| D-S1 | **A new local `no_resource_level_writes = ["cloudwatch:PutCompositeAlarm"]`** beside `no_resource_level_reads`, and one new apply statement `CompositeAlarmWrite` (Allow, resource `*`, no conditions), assigned to the `writes` group in `apply_group_of`. Production and staging get it identically. | NFR6.2, NFR6.4 (corrected) |
| D-S2 | **A new service `dashboards` in `services.tf`**: kind `dashboard`, `conditioned = false`, read `["cloudwatch:GetDashboard"]`, create `["cloudwatch:PutDashboard"]`, manage `["cloudwatch:PutDashboard", "cloudwatch:DeleteDashboards"]`, tag `[]`. The existing loops then hand `GetDashboard` to the plan roles through `Reads`, and the two writes to apply roles through `WritesWithoutTagConditions`. No `apply_group_of` entry is needed, because those statements already exist. | NFR6.2, NFR6.3, NFR6.14 |
| D-S3 | **`locals.tf` gains `dashboard` in both `names` and `arns`.** Names: staging by prefix (`["${e.name}*"]`), production exact (`[e.name]`). ARN: `arn:aws:cloudwatch::${local.account_id}:dashboard/${x}`, with an empty region field unlike every other kind. Staging's `weather-story-bot-staging*` cannot match production's `weather-story-bot`, and production's exact name cannot match staging's. | NFR6.4 |
| D-S4 | **Production's exact `alarm` list gains `unknown` and `not-healthy`.** Staging's prefix already covers them. The extra ARNs are repeated in `Creates`, `Changes`, `Reads` and `Tags`. | NFR6.2, NFR6.4 |
| D-S5 | **Size budget.** Each of the six policy groups stays under 5,000 characters of rendered statement text, about 80% of IAM's 6,144 limit, with the headroom named for U4 and U5 (each new production alarm name costs about 170 characters in `writes`). If `writes` goes over, `Changes` moves to the `access` group by an `apply_group_of` edit. Infrastructure Design measures the real sizes. | NFR6.6 |
| D-S6 | **Tests that can fail before apply** (NFR4.2) in `infra/bootstrap/tests/apply_roles.tftest.hcl` and `plan_roles.tftest.hcl`: each environment's role is allowed `PutDashboard`, `DeleteDashboards` and `GetDashboard` on its own dashboard ARN and refused on the other's (the regex trick `each_environment_creates_its_own_misconfigured_alarm` uses); `PutCompositeAlarm` appears once, on `*`, and is the only write action on `*` (a guard against creep); plan roles hold `GetDashboard` on both dashboards and no write action; a size proxy (the encoded length of each group's statements) is under the budget. | NFR4.2, NFR6.3, NFR6.6 |
| D-S7 | **Who applies.** The owner runs `mise run bootstrap-plan`, reviews it, and runs `mise run bootstrap-deploy` with the MFA profile; an agent asks first and never runs it. The pipeline never touches the bootstrap stack. | NFR6.5 |
| D-S8 | **No secret reaches the page.** The dashboard reads existing metrics and alarm states, adds no log or metric filter, and its text widgets are static. A Terraform test scans the decoded body for the Telegram token parameter name and for any `${` left unrendered. | NFR5.5 |

## Threats

| Threat | Mitigation |
|--------|------------|
| The pipeline cannot apply the unit (AccessDenied) | D-S1 to D-S4, ordered first (see `reliability-design.md`) |
| A wrong guess in the policy needs a second manual apply that the mock provider cannot catch | The condition keys the statements rely on are limited to the ones already used for alarms; the one action that needed a new rule (`PutCompositeAlarm`) is granted without conditions, so it has no key to get wrong |
| Wide scope of `PutCompositeAlarm` | Stated above for the owner; display-only effect; drift visible in `terraform plan` |
| A policy over the size limit | D-S5, D-S6 |

## Not applicable

Authentication of viewers (the owner's own AWS sign-in, unchanged), encryption (nothing sensitive stored), input
validation (no input) and compliance regimes.
