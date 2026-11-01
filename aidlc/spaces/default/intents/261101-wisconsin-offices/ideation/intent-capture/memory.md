<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-11-01T20:27:08Z — read "Maximum $20/month" as total account spend; kept as an accepted [assumption]. Owner widened the cost limit from $5 more to $20 max at the summary, and added README links as the only publishing (Q10) at the assumption confirmation.
- 2026-11-01T20:27:08Z — Q9 picked "per-office alerts" out but the owner put alarm mechanics in scope; recorded as general alarms that must cover new offices, with an office dimension allowed, not per-office alarms.

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
- 2026-11-01T20:27:08Z — the Bot API cannot create channels; "automated provisioning" may mean user-account (MTProto) login or bot-side setup after a hand-made channel. Asked as Q6 so the owner settles it before scope hardens.
