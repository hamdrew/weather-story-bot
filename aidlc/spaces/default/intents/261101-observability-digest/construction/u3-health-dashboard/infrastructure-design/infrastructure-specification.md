# Infrastructure Specification: u3-health-dashboard

## Sources

- `nfr-design/` (all seven files, especially `security-design.md` D-S1 to D-S8 and `logical-components.md` LC1 to LC8)
- `nfr-requirements/tech-stack-decisions.md` (cost lines, delivery order)
- `functional-design/functional-spec.md` (layout) and `rules.md`
- `inception/domain-design/components.md` (the component catalogue): the Monitoring component owns the verdict composite alarms and the dashboard, and the `VerdictAlarm` and `Dashboard` entities
- `infra/monitoring.tf`, `infra/locals.tf`, `infra/bootstrap/{services,locals,apply,plan_roles}.tf` and `infra/bootstrap/tests/`
- Amazon CloudWatch permissions reference (docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/permissions-reference-cw.html), read 2026-11-02: `PutCompositeAlarm` must have a `*` scope; `DescribeAlarms` must have `*` scope to return composite alarms
- Terraform AWS provider 6.71.0 documentation: `aws_cloudwatch_composite_alarm` (supports `tags`, `alarm_rule` up to 10,240 characters), `aws_cloudwatch_dashboard` (`dashboard_name`, `dashboard_body`; no tags)
- AWS CloudWatch pricing (aws.amazon.com/cloudwatch/pricing), as checked in NFR Requirements on 2026-11-02: composite alarm $0.50 a month; the first 3 custom dashboards (up to 50 metrics each) free
- Measurements and checks run in this stage in a scratch copy under the session's scratchpad directory, not in the repository (see Verification)

## Deployment

| Facet | Choice | Rationale |
|-------|--------|-----------|
| Owning component | **Monitoring** (components.md): its Terraform in `infra/` holds the verdict composite alarms and the dashboard; this unit builds the composites and the dashboard, U4 and U5 build the rest of that component's alarms, filters and areas. The composites are not "metric alarms" in the catalogue's sense, so they stay out of `alarm_names` and carry no action | Matches the catalogue's `VerdictAlarm` (no actions) and `Dashboard` entities |
| Compute model | None. CloudWatch configuration only: two composite alarms and one dashboard per environment | The unit shows the state of alarms that already watch the Lambda; it runs nothing |
| Networking | None | Console features reached through the owner's AWS sign-in |
| Storage | None. The composites and the dashboard hold no data | Rollback loses nothing (NFR5.3) |
| Environments | `staging` and `production` from the one Terraform root `infra/`; names follow `local.name`; the dashboard is named `local.name` | Environment parity; differences only through `local.production` and variables |
| IaC approach | New file `infra/dashboard.tf` beside `monitoring.tf` (which is not edited); a bootstrap change in `infra/bootstrap/` as its own slice | ADR-004; BR6.2 |
| Sizing | 13 widgets, 8 metrics, 2 composite alarms, 1 dashboard per environment | Inside the free dashboard allowance; a rule well under 1,000 characters |
| Region | `var.region` (us-east-2); dashboard and composite alarms are regional like the alarms they read | Same region as the alarms |
| Cost | Four composite alarms (two per environment) at $0.50 a month = **$2.00 a month**; two dashboards inside the free three; no other billed resource. **$3.00** of the $5 limit stays for U5 | NFR1.1 to NFR1.4 |

## Infrastructure Services

| Service | Role | Configuration | Notes |
|---------|------|---------------|-------|
| CloudWatch composite alarm `<name>-unknown` | Verdict carrier: ALARM when the bot should have run and gave no data | `alarm_rule` = `ALARM("<missed-runs>") OR INSUFFICIENT_DATA("<errors>") OR INSUFFICIENT_DATA("<missed-runs>") OR INSUFFICIENT_DATA("<quiet>") OR INSUFFICIENT_DATA("<repost-loop>")`, each name read from the alarm resource; no actions; tags from the provider's `default_tags` | Quoted names first; the unquoted form is the fallback if staging rejects the quotes (D-R6) |
| CloudWatch composite alarm `<name>-not-healthy` | Verdict carrier: ALARM when a signal other than missed-runs is off | `alarm_rule` = `ALARM("<errors>") OR ALARM("<quiet>") OR ALARM("<repost-loop>")` built from `local.not_healthy_alarms`; no actions | U5 appends its error-log alarm to the list |
| CloudWatch dashboard `<name>` | The page | `dashboard_body` = `jsonencode` of `{ start = "-P7D", periodOverride = "inherit", widgets = [...] }`; 13 widgets computed from rows (D-P3) | No tags (provider limitation) |
| IAM (bootstrap stack) | Lets the CI roles create and read these resources | See the bootstrap table below | Applied by the owner with MFA |

### Bootstrap change (the first slice)

| File | Change | Design reference |
|------|--------|------------------|
| `infra/bootstrap/services.tf` | New service `dashboards`: sid `Dashboard`, kind `dashboard`, `conditioned = false`, read `cloudwatch:GetDashboard`, create `cloudwatch:PutDashboard`, manage `cloudwatch:PutDashboard` and `cloudwatch:DeleteDashboards`, no tag actions. New local `no_resource_level_writes = ["cloudwatch:PutCompositeAlarm"]` | D-S1, D-S2 |
| `infra/bootstrap/locals.tf` | `names.dashboard` (staging prefix `${e.name}*`, production exact `[e.name]`), `arns.dashboard` = `arn:aws:cloudwatch::<account>:dashboard/<name>` (empty region field), and `unknown` and `not-healthy` added to production's exact alarm list | D-S3, D-S4 |
| `infra/bootstrap/apply.tf` | New statement `CompositeAlarmWrite` (Allow, `no_resource_level_writes`, resource `*`, no conditions); `apply_group_of` entries `CompositeAlarmWrite = "access"` and `WritesWithoutTagConditions` moved from `writes` to `access` to balance the groups | D-S1, D-S5 |
| `infra/bootstrap/tests/apply_roles.tftest.hcl` | `CompositeAlarmWrite` added to the sid exemption lists of `the_staging_role_names_only_staging_resources` and `the_production_role_uses_no_prefix_pattern`; new runs for the dashboard patterns, the single `*`-scoped write, and the size budget | D-S6 |
| `infra/bootstrap/tests/plan_roles.tftest.hcl` | New run: plan roles hold `GetDashboard` on both dashboards and no write action | D-S6 |

No change to `plan_roles.tf`: the new service's read reaches the plan roles through the existing loop.

### Policy sizes (measured)

An upper-bound proxy for the rendered IAM JSON (compact, no whitespace), calibrated against `apply.tf`'s documented production figures (about 3.4, 3.8 and 4.5 KB), which it reproduces within 4%:

| Policy | Before | After, `CompositeAlarmWrite` in `writes` | After, regrouped as designed | Limit |
|--------|--------|------------------------------------------|------------------------------|-------|
| production access | 3,268 | 3,513 | **4,171** | 6,144 |
| production roles-tags | 3,820 | 4,039 | **4,039** | 6,144 |
| production writes | 4,532 | **5,095** | **4,437** | 6,144 |
| staging access / roles-tags / writes | 2,518 / 2,914 / 3,416 | 2,616 / 2,986 / 3,676 | 3,145 / 2,986 / 3,147 | 6,144 |
| plan read (one inline policy, both environments) | 4,038 | 4,420 | 4,420 | 10,240 |

The unregrouped change would put production `writes` at 5,095, over the 5,000 budget NFR Design promised before measuring, so the regrouping is part of the design. After it the tightest group is 4,437 (72% of the limit), which leaves room for about ten more production alarm names across U4 and U5. The test budget is 5,000 characters per group by the same proxy.

### Verification run in this stage (scratch copy only)

| Check | Result |
|-------|--------|
| Bootstrap prototype with the changes above against the existing four bootstrap test files | 31 of 31 existing tests pass **after** the two sid exemptions are added |
| The same prototype without the exemptions | `the_staging_role_names_only_staging_resources` goes red; Terraform 1.16.6 then **crashes while printing** the failed assertion (a Terraform bug on marked values) instead of showing a message, so a red run here looks like a crash |
| Dashboard builders (tiles with both `fill` settings, charts, rows with computed x and y, null `dimensions`, `jsonencode`) in a provider-free scratch configuration | Builds and encodes; layout comes out `0,0,24,5`, `0,5,12,4`, `12,5,12,4`, `0,9,12,6`, `12,9,12,6`; the earlier conditional-of-tuples shape does not type-check and is replaced by rows with a use flag and a merged options object |

## Shared Infrastructure

| Shared Resource | Owner Unit | Consumer Units | Access Boundary |
|-----------------|------------|----------------|-----------------|
| `infra/dashboard.tf` (signal list, rule lists, row list) | U3 | U5 (appends and inserts at the extension points) | Edited only at the extension points (D-C1) |
| The five existing alarms | existing `monitoring.tf` | U3 reads; U4 recreates some; U5 adds two | U3 references and never edits them |
| Apply-role policy size | bootstrap stack | U4, U5 | 5,000 characters per group by the proxy; test fails above it |
| The `*`-scoped `PutCompositeAlarm` statement | bootstrap stack | U3 only today | Display-only effect; drift visible in `terraform plan`; owner checks for other composite alarms and topics |

## Owner checks before the bootstrap apply

1. Confirm no composite alarms exist other than U3's (the `readonly` session had expired, so this was not listed here): `aws cloudwatch describe-alarms --alarm-types CompositeAlarm --profile readonly`.
2. Confirm the account holds no custom dashboards beyond the two this unit adds, so the free allowance holds (NFR1.4).
3. Read the `*` scope for `PutCompositeAlarm` (the correction recorded in `security-design.md`) and accept it.
4. Review `mise run bootstrap-plan`; an agent never runs `bootstrap-deploy`.
