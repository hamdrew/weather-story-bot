# Principles

The four rules the other standards are specific cases of. When a standard and a principle seem to
disagree, the principle is what the standard was trying to say.

## Local tools are read-only

Anything that writes — Telegram, AWS, anything outside stdout and stderr — runs in a deployed
environment or a `scripts/` tool whose name says so. The dev CLI previews and never acts.

- A preview that could act is a preview you stop trusting, and a flag away from posting to a live
  channel from a laptop
- A `scripts/` tool that writes is dry-run by default and needs `--apply` (`backend/dynamodb-schema`)
- To watch real behaviour, use a deployed environment, not a local flag
- Adding a write mode to a local tool needs a spec that changes `backend/cli` first

## Decide purely, then act

Choosing what to do is a pure function of its inputs: the listing, the images, `now`, and the
stored records. Side effects happen afterwards, in a thin apply step with a fixed order
(`backend/side-effect-order`).

- The planner returns data. It does no I/O, reads no clock of its own, and **does not log** —
  log lines are a side effect, and some of them are alarm contracts (`testing/log-contracts`)
- The Lambda and the CLI call the same planner, so a preview cannot drift from what runs
- Decision edge cases get table-driven tests with no moto and no respx
- A decision that needs a new input takes it as an argument, never by reaching for it

## Sources of truth vs derived data

The S3 archive (raw NWS) and the ledger (what we did) are sources of truth: protected, kept
forever, never rewritten. Everything else — analytics tables, indexes, reports, labels — is
derived: rebuildable, unprotected, deletable.

- Never add derived fields to a source of truth. Derived fields belong in the derived dataset
- Analytics reads the derived dataset, never the live archive or the state table
- Losing derived data costs a rebuild. Losing a source of truth costs the data forever, and NWS
  lists only *active* stories, so nothing can be re-fetched
- Retention is a deliberate decision per dataset, not a default

## The office is the unit of isolation

Concurrency, failure, configuration, and onboarding are all per office.

- One office's failure never affects another's posts
- `story_key` alone is not a global identity; `(office_id, story_key)` is
- Checks that compare stories to each other stay inside one office's listing — neighbouring
  offices can legitimately share a regional graphic (`backend/untrusted-nws-data`)
- Per-office *visibility* comes from queries and reports, never from per-office alarms or
  custom metrics, whose fixed cost grows with the office count
