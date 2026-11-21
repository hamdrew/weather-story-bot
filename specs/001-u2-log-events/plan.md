# Implementation Plan: U2 Log Events

**Branch**: `001-u2-log-events` | **Date**: 2026-11-09 (revised) | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-u2-log-events/spec.md`

## Summary

Give every warning and error, and the "Telegram message sent" line, a stable `event` name that U4 (alarms) and U5
(digest) can filter on. Let Lambda's JSON log format write the lines instead of the bot's own formatter. The bot keeps
only an `office` stamp and its `httpx` log caps. Rename three field names, prove the Telegram token never reaches a
log record, and add a simple drift check that keeps the code and `docs/logging-review.md` table 1 in step. The slow-run
warning becomes a `Duration` alarm in U4, so U2 adds no slow-run code. The design decisions are in
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (Lambda arm64); Terraform for `infra/`

**Primary Dependencies**: standard-library `logging`, `ast` (tests); httpx (unchanged, the only runtime dependency);
the Lambda runtime's JSON log format

**Storage**: none new. The `RUN#` history items keep `aws_request_id`, now passed in as an argument (research R3)

**Testing**: pytest with respx and moto (offline); `terraform test` with the mock AWS provider

**Target Platform**: AWS Lambda, Python 3.13, arm64

**Project Type**: single project, a scheduled Lambda plus a CLI dry run

**Performance Goals**: none. Logging volume and run time are unchanged

**Constraints**: no log message, level or stack-trace change (constitution Principle V, FR-006); no new dependency
(Principle VI); tests offline (Principle IV); the only infrastructure change is `logging_config` (FR-019)

**Scale/Scope**: 19 log calls in 4 modules (`handler`, `telegram`, `nws`, `history`); 15 events

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan meets it | Before | After |
|-----------|------------------------|--------|-------|
| I. Distrust Upstream Data | No change to parsing, identity or rejection. `nws.ambiguous_stories` labels the existing rejection line. | Pass | Pass |
| II. A Repost Beats a Missed Story | No change to the post-then-record order. The message-sent line still logs right after Telegram accepts. | Pass | Pass |
| III. Decide Purely, Act Thinly | No planner change. The dry run makes no writes and its output is unchanged (SC-008). | Pass | Pass |
| IV. Offline, Contract-Pinned Tests | Every new check is offline. The two signal events are pinned on their real paths with names written out. The log format is pinned by `terraform test`. | Pass | Pass |
| V. Out-of-Band Observability | "Telegram message sent" and "Ambiguous stories from NWS" keep their text, and the runtime keeps the `message` key, so `infra/monitoring.tf` is untouched. The staging check (FR-020) confirms the posts metric still counts. | Pass | Pass |
| VI. Personal Scope, Minimal Surface | Removes the custom formatter and the request-id context; adds no dependency. | Pass | Pass |
| Security & Infrastructure | The token stays in SSM. The new token-leak test covers every handled Telegram failure. The infrastructure change goes through the saved-plan pipeline, staging first. | Pass | Pass |
| Workflow & Quality Gates | The tooling pull request first (FR-018), then the spec documents in their own pull request, then one pull request for the unit's code (FR-017). `mise run lint ::: test ::: tftest ::: scan` before review. No commit without the owner's go-ahead. Production approval waits on the staging check. | Pass | Pass |

No violations. Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-u2-log-events/
├── spec.md              # the feature spec (revised)
├── plan.md              # this file
├── research.md          # Phase 0: decisions R1 to R11
├── data-model.md        # Phase 1: log line, event, call, office context
├── quickstart.md        # Phase 1: offline gates and the staging check
├── contracts/
│   └── log-line.md      # Phase 1: the line and event catalogue U4 and U5 read
├── checklists/
│   ├── requirements.md  # spec quality checklist
│   └── platform-logging.md  # reviewer checklist for this design
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
infra/
├── lambda.tf            # logging_config: log_format JSON, application and system levels INFO; new comment (R1)
└── tests/
    └── lambda.tftest.hcl  # asserts the three logging_config values (R1)

src/weather_story_bot/
├── handler.py           # delete JsonFormatter, _STANDARD_LOG_ATTRS, _aws_request_id, _invocation_context;
│                        #   record factory stamps office only (R4); configure_logging sets levels only (R2);
│                        #   run(..., aws_request_id=None) (R3); events on L01, L03-L09, L11
├── telegram.py          # L13 error=repr and event; L14 event; L15 telegram_message_id; L16 event
├── nws.py               # L17 event; L18 event and http_status
└── history.py           # L19 event, error=repr, image_id in the literal instead of a **extra spread (R6)

tests/
├── test_logging_review.py  # drift check extended (R6)
├── test_log_secrets.py     # new: token-leak test and httpx caps (R7)
├── test_handler.py      # per-call events, ambiguous signal; formatter and request-id tests changed (R8)
├── test_telegram.py     # L13/L15/L16 fields and events; message-sent signal
├── test_nws.py          # L17/L18 events, http_status
└── test_history.py      # L19 event, error as repr

docs/
└── logging-review.md    # fields column, L20 and D5 moved to U4, "What U2 must build" (R9)

CLAUDE.md                # point U2 at specs/001-u2-log-events/spec.md (R9)
```

**Structure Decision**: single project, existing layout. One test module is added. No source module is added, and
`log_format.py` from the old `u2-log-events` branch does not ship.

## Implementation Approach

The owner's rule: new code first, with its tests in the same change.

0. **Branch split (FR-018)**: the tooling pull request goes first (see "Delivery"). U2 starts from the updated `main`.
1. **Platform format**: change `logging_config` in `infra/lambda.tf` and assert it in `lambda.tftest.hcl` (R1).
2. **Shrink the bot's logging**: in `handler.py`, delete the formatter and the request-id context, keep the office
   factory, cut `configure_logging()` to levels, and pass the request id to `run()`. Update the R8 tests.
3. **Events and fields**: add the events and field changes to L01 to L19, exactly as in table 1 and decisions D1 to D3.
   Update the comments that say "this exact message" so they also name the event. Add per-call event tests beside each
   module, including the two signals on their real paths.
4. **Token leak**: `tests/test_log_secrets.py` (R7).
5. **Drift check**: extend `tests/test_logging_review.py` (R6).
6. **Docs in step**: `docs/logging-review.md` and `CLAUDE.md` (R9).
7. **Gates**: `mise run format`, then `mise run lint ::: test ::: tftest ::: scan`, then `mise run coverage`.
8. **Pull request**: its body includes the staging query and steps from [quickstart.md](quickstart.md) section 4, and
   says that `run.slow` moved to U4.

### Delivery (FR-018)

The branch `u2-log-events` holds six commits that are not on `main`:

| Commit | Content | Goes to |
|--------|---------|---------|
| `856fb04` | AI-DLC removal, project docs moved into `docs/` | tooling pull request |
| `09e89b5` | the `__init__.py` import-time install | nowhere (this design does not use it) |
| `b96bb46` | Spec Kit initialisation **and** `log_format.py` | tooling pull request, without `log_format.py` |
| `5882d78` | constitution v1.0.0 | tooling pull request |
| `1349a3d` | Spec Kit git and bug extensions | nowhere (removed on 2026-11-09) |
| `37274c5` | `specs/001-u2-log-events/` | U2 |

1. **Tooling branch**: a new branch from `origin/main` (the local `main` is behind it) takes `856fb04`, `b96bb46` and
   `5882d78` by cherry-pick, removing `src/weather_story_bot/log_format.py` during the `b96bb46` pick. Conflicts with
   the newer `main` are resolved there. Its `checks` job must pass, and it merges before U2's pull request opens.
   It merged as #55.
2. **Spec branch**: the old branch keeps its name, `u2-log-events`, and is kept as the saved copy of the pre-split work.
   A fresh `001-u2-log-events`, named after the spec, starts from the updated `origin/main` and takes only
   `specs/001-u2-log-events/` from it, as files. Those documents go to `main` in their own pull request (FR-017).
3. **Code**: once the spec pull request has merged, the unit's code is built on a branch from the updated `origin/main`
   and ships as one pull request.
4. The old `u2-log-events` branch is deleted only when the owner says so, after U2 merges. It has never been pushed,
   so no force-push is needed.

Each commit, branch rename, push and pull request needs the owner's go-ahead.

## Risks

| Risk | Mitigation |
|------|------------|
| The runtime's formatter does not write the `office` attribute or an `extra` key as documented. | The owner accepted the documented behaviour (spec Clarifications). The staging check (FR-020) runs before production. A failed check means declining the approval and a revert pull request for staging. |
| The runtime writes `WARN` rather than `WARNING`. | Nothing reads `level` until U4 and U5, which confirm the spelling from a real WARNING line first (spec Assumptions). |
| The code's root level and `application_log_level` drift apart. | FR-002 ties them together; a comment beside each names the other. |
| The posts metric stops counting after the format change. | The filters read `$.message`, which keeps its key and text under the JSON format. The staging check confirms the count before production. |
| A test relied on the custom formatter or the request-id stamp. | R8 lists them. The suite runs offline before review. |
| A future change re-adds a formatter on the root handler and silently undoes R1. | `configure_logging()` only sets levels, with a comment saying why; the token-leak test calls it as production does. |

## Notes

- `checklists/event-contract.md` was written for the first design and was deleted on 2026-11-09;
  `checklists/platform-logging.md` replaces it.
- `tasks.md` was regenerated for this design on 2026-11-10 and revised after review on 2026-11-11. Its step S0 saves
  the revised documents in a local commit before the branch split, so S3 carries this design over and not the first.
- `docs/handoff/u2-log-events/` and `docs/handoff-u2-log-events.md` describe the first design. The spec lists the
  differences; the handoff stays as a record.

## Complexity Tracking

No constitution violations. Nothing to justify.
