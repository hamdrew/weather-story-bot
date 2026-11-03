## Review

**Verdict:** READY
**Reviewer:** aidlc-architecture-reviewer-agent
**Date:** 2026-11-02
**Iteration:** 1
**Verdict Dictated:** no

### Findings

| ID | Severity | Location | Finding | Required action | Status |
|---|---|---|---|---|---|
| R-01 | Minor | infra/bootstrap/apply.tf > comment above `apply_group_of` (about line 233-234) | The rewritten comment runs the sentence "A statement that pushes one over fails at apply, so move it to a lighter group (apply_group_of is ..." onto one very long line, unlike the wrapped lines around it. `terraform fmt` does not care, but it is the only unwrapped comment in the file. | Re-wrap the comment to the file's usual width. | New |
| R-02 | Minor | infra/bootstrap/tests/apply_roles.tftest.hcl > runs `the_staging_role_names_only_staging_resources` and `the_production_role_uses_no_prefix_pattern` | Adding `CompositeAlarmWrite` to both sid exemption lists means those two guards no longer prove anything about that statement. The new run `put_composite_alarm_is_the_only_write_on_star` does replace the protection: exactly one statement per role holds the action, its resources equal `["*"]`, it has no conditions, and no other Allow on `*` carries any action except `NoResourceLevelReads`. I read it and I believe it fails if someone adds a second write on `*`. It does not stop someone widening the `CompositeAlarmWrite` statement's own actions list, because the third assertion fires only when the action list differs from exactly `PutCompositeAlarm` (it does, so that case is caught). Net: adequate. | No change required. Optionally assert that the `CompositeAlarmWrite` sid's action list is exactly `["cloudwatch:PutCompositeAlarm"]` so the intent is explicit. | New |
| R-03 | Minor | infra/tests/dashboard.tftest.hcl > run `each_tile_shows_its_value_filled_with_zero_and_a_sparkline` (comment near line 336) and infra/dashboard.tf > `tile_widgets` | The `fill = false` tile shape is never built by any test, because a local cannot be overridden. The test comment says so openly. The plan asked for "both `fill` settings build". Only the `fill = true` shape is exercised. Reading the expression, the `fill = false` path yields `[row]` with no id or visible keys, which looks well-formed, but that is unverified. | Accept, or add a tiny helper local or variable that lets a test flip `fill`. Otherwise record the gap in `unit-test-instructions.md`. | New |
| R-04 | Minor | aidlc/spaces/default/intents/261101-observability-digest/construction/u3-health-dashboard/code-generation/traceability.json > NFR6.10 (target `.github/workflows/pipeline.yml`) and NFR6.5 (target `infra/bootstrap/apply.tf`) | These two `OK` rows point at things that are not tests. NFR6.10 points at an unchanged workflow that is not in `source-manifest.json`; the note in `code-summary.md` explains that both are process rules. The other targets I checked really implement or test the id they name (BR1.x/BR2.x rules, grid, FILL tiles, threshold annotations, alarm lists, sorts and the no-timezone/no-token checks in `dashboard.tftest.hcl`; NFR6.2/6.3/6.4/6.6 in the bootstrap tests). | None needed beyond the existing note. Do not add `pipeline.yml` to the manifest, because it is not changed. | New |
| R-05 | Minor | infra/bootstrap/tests/apply_roles.tftest.hcl > run `each_apply_policy_group_stays_under_the_size_budget`, with infra/bootstrap/apply.tf > comment | Production's largest group measures 4,437 characters against the 5,000 test budget and IAM's 6,144 limit, so there is about 560 characters of headroom in the test. The test uses a compact-JSON upper-bound proxy because the mock returns `{}` for `.json`. The proxy is honest and says so. A later unit that adds statements to the `writes` or `access` group can trip it, which is what it is for. | None. When a later unit trips it, regroup before raising the budget. | New |
| R-06 | Minor | infra/dashboard.tf > `rule_term_format`, widgets | Verified offline: the rule strings and their ordering, name-by-reference (so destroy order is right), widget grid arithmetic (13 widgets, y 0/5/8/11/15/18/21/27, no overflow), null `dimensions` handling, and the merged-options pattern (no conditional between tuples). Not verifiable offline, and left to the first staging apply: whether CloudWatch accepts the quoted `ALARM("name")` form (an unquoted fallback is documented in a comment), whether `PutDashboard` accepts the alarm-widget `states` and `sortBy` properties and `FILL(m1, 0)` on a `singleValue` tile with a hidden `m1`, and whether the console draws the layout as intended. Also unverified live: that `PutCompositeAlarm` with the provider's `default_tags` is authorized by `Tags` (TagResource) on the alarm ARNs. The tests prove the composites are inside each role's `Creates`, `Changes` and `Tags` patterns, but only a real CI-role apply proves the tagging condition passes. | Watch the first staging pipeline run, as D-R1 and D-R6 already say. No code change. | New |

### Validation Tool Results

| Tool | Result | Interpretation |
|---|---|---|
| `TF_DATA_DIR=.terraform-test terraform -chdir=infra test` | Success! 44 passed, 0 failed | Matches the expected count; the 14 new dashboard runs pass |
| `TF_DATA_DIR=.terraform-test terraform -chdir=infra/bootstrap test` | Success! 37 passed, 0 failed | Matches the expected count; the 4 new apply and 2 new plan runs pass |
| `terraform fmt -recursive -check` | exit 0, no files listed | Formatting clean |
| `git status --short infra` | `infra/monitoring.tf` not listed as changed; only the 7 manifest files are touched | `monitoring.tf` is unchanged, and the manifest has no unrelated claims |

Security checks (item 3), all by reading the diff and tests:
- The only new broad grant is `CompositeAlarmWrite` (`cloudwatch:PutCompositeAlarm` on `*`), and it is present exactly once per role.
- The dashboard patterns are staging-prefix (`weather-story-bot-staging*`) and production-exact (`weather-story-bot`), in an ARN with an empty region field. The new run `each_environment_manages_only_its_own_dashboard` checks Put, Delete and Get against both names for both roles.
- The plan roles gain only `cloudwatch:GetDashboard` in `DashboardRead`, and a test forbids any `cloudwatch:Put*` or `cloudwatch:Delete*` in the read policy.
- The composite alarm names (`unknown`, `not-healthy`) are added to production's exact alarm list, so `Creates`, `Changes` and `Tags` cover them.
- No Telegram or secret parameter name reaches the dashboard body; a test checks this for both environments.
- The accepted residual risk is that staging's role can rewrite production's two composites through the `*` grant. The code comments document it, and the tests pin that the dashboard's composites carry no actions and stay out of `alarm_names`, so `start` and `pause` have nothing to toggle.

Carried-forward points from the plan (item 2): the tile use-flag with a merged options object, null-safe dimensions, both sid exemptions, the 5,000-character budget test, and the comments (PutCompositeAlarm on `*`, a failed first apply leaving one composite, revert slice 2 before slice 1, run `bootstrap-deploy` when no pipeline run is active) are all present. The charts use the alarm's own metric plus a threshold annotation (D-P4).

### Summary

I found no Critical or Major defects. Both suites pass at the expected counts, the formatting is clean, `monitoring.tf` is untouched, and the one broad IAM grant is documented, unconditioned, and guarded by a meaningful "only write on `*`" test. What remains are minor gaps (the `fill = false` shape is not built by a test, and an unwrapped comment) plus the live-only checks listed above, which the first staging apply must confirm.
