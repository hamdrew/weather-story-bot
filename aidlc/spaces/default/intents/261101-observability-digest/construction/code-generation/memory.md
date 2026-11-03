<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-11-03T01:55:49Z — [unit u3-health-dashboard] The `unknown` composite rule lists its terms in tile order (missed-runs ALARM, then INSUFFICIENT_DATA for missed-runs, errors, quiet, repost-loop), not errors-first as the infrastructure specification's example did; D-C2 says tile order and the meaning is identical.
- 2026-11-03T01:55:49Z — [unit u3-health-dashboard] `fill = false` is built from the same rows but cannot be exercised end to end, because a Terraform test cannot flip a local; the extension-point stand-in test likewise checks the rule and layout arithmetic, not a real appended row.

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
- 2026-11-03T01:55:49Z — [unit u3-health-dashboard] Only the first staging apply shows whether CloudWatch accepts the quoted rule terms `ALARM("name")`; the unquoted fallback is the one-line change to `local.rule_term_format`.
- 2026-11-03T01:58:30Z — [unit u3-health-dashboard] Advisory review READY (0 Major, 5 Minor); the work is frozen after the verdict, so these go to the owner at the checkpoint and the pull request notes: (1) one comment above `apply_group_of` in `infra/bootstrap/apply.tf` runs on one long line and could be re-wrapped; (2) the `fill = false` tile shape is built by no test; (3) the NFR6.5 and NFR6.10 traceability rows point at non-test targets because both are process rules; (4) about 560 characters of headroom remain under the 5,000-character policy budget; (5) only the first staging apply shows whether CloudWatch accepts the quoted rule terms, `states`/`sortBy` on the alarm widgets, `FILL(m1, 0)` on a single-value tile with a hidden `m1`, and whether `PutCompositeAlarm` with the provider's default tags passes the `Tags` statement.
- 2026-11-03T01:58:30Z — [unit u3-health-dashboard] An automated security scan flagged the `*`-scoped `PutCompositeAlarm` statement and suggested scoping it to alarm ARNs; AWS accepts no narrower resource for that action (CloudWatch permissions reference, read 2026-11-02), so a scoped grant would fail at apply. The grant was surfaced in the approved plan and stays for the owner to accept.
- 2026-11-03T01:55:49Z — [unit u3-health-dashboard] Production policy headroom is about three more alarm names under the 5,000-character test budget, so Units 4 and 5 will have to regroup the apply policy or raise the budget with a stated margin.
