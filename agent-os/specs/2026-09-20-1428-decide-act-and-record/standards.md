# Standards for Decide, Act, and Record

## Rewritten or amended by this spec

- **global/principles** (added with this spec) — Local tools are read-only. Decide purely, then
  act. Sources of truth (archive, ledger) are protected; derived data is rebuildable and
  deletable. The office is the unit of isolation for concurrency, failure, config and onboarding.
- **backend/cli** (rewritten) — The CLI makes **no writes of any kind**: no Telegram, no AWS, no
  local state beyond stdout/stderr. `--send-telegram`, the `TELEGRAM_*` handling and the exit-2
  credential path all go. `--dry-run` stays `required=True`; a future write mode is a new flag
  and needs a spec that changes this standard first. `--office` is validated with the same regex
  as `config.py`. The dry run calls the same planner as the Lambda and prints each story's
  decision; without DynamoDB it says `new-or-updated (state not read)` rather than guessing.
  Exit codes: 0 success or no active stories, 1 NWS list or download failed, 2 usage.
- **backend/story-identity** (amended) — The hash encoding is frozen explicitly
  (`sort_keys=True, separators=(", ", ": "), ensure_ascii=True`, `json.dumps`' own defaults, never
  the compact `(",", ":")`) and pinned by a test asserting known literal digests. Global identity
  is `(office_id, story_key)`; `story_key` alone is not unique across offices. Task 7b adds the
  stored `image_sha256`/`description_sha256`, which explain an update and never decide one.
- **backend/side-effect-order** (amended) — Gains **step 0: take the office lease**, in the safety
  chain. The rest of the order is unchanged. The three history writes are **best effort and
  outside the chain**: each failure logs a WARNING, never blocks a post and never counts as
  `failed`. Notes that Phase 2.2 deliberately reverses the latter by making the ledger write atomic
  with the record.
- **backend/run-outcomes** (amended) — Losing the lease is `skipped`, not `failed`; a DynamoDB
  error *taking* the lease is `failed`. Moved here from the unchanged list because the lease adds
  a case to `counts()`.
- **backend/structured-logging** (amended) — `office` and `aws_request_id` are set once per
  invocation by a filter, not passed by each caller.
- **backend/injected-clients** (amended) — The history store takes its DynamoDB client from the
  caller, like every other wrapper. Only `handler._build_services` and `__main__` build clients.
- **backend/dynamodb-schema** (amended) — The new keys replace the MVP design and become
  current: generic `PK`/`SK`, sortable sort-key values, `schema_version` on every item, **no
  TTL**. The migration follows this file's own script pattern.
- **testing/handler-tests** (amended) — Table-driven pure tests of the planner join the
  real-client-over-respx+moto integration tests; they do not replace them.
- **testing/offline-tests** (amended) — `TELEGRAM_*` clearing moves into the autouse fixture, and
  CLI tests assert with an empty respx router that no Telegram host is ever called.

## Constraining, unchanged

- **backend/untrusted-nws-data** — The ambiguity rule moves into the planner with no behaviour
  change: stories sharing an image ID, a title and start time, or image bytes are all rejected,
  the run still succeeds, and the checks never compare across offices.
- **testing/log-contracts** — Three messages are an API and survive word for word, or move in the
  same commit as `infra/monitoring.tf`: `Ambiguous stories from NWS` (→ `nws-ambiguous`),
  `Telegram message sent` (→ `StoriesPosted`, feeding **both** `quiet` and `repost-loop`) and
  `Story posted` (the `repost-loop` runbook). `Run complete` is named in the `quiet` runbook.
- **backend/retries** — At most one in-client retry; the next scheduled run is the real retry;
  platform retries stay off. The concurrency guard does not change this.
- **backend/client-errors** — One public error type per client; `handler.run` stays the only
  catch-all boundary. The planner raises nothing.
- **backend/archive-layout** — Untouched. The archive stays the human-browsable source of truth
  and is never an analytics source.
- **infra/data-retention** — The old table keeps deletion protection and PITR and is **not**
  replaced; it is the rollback. `make plan` must show zero replacements.
- **infra/iam** (amended in Task 11) — Exact actions on the narrowest ARNs, each added with the code
  that calls it. The role gains `GetItem`/`PutItem` (Task 9), `UpdateItem` (Task 10) and
  `DeleteItem` (Task 11, for the lease) on the new table only, and no `Scan`. The "No `Delete*`"
  rule is narrowed to allow exact item-level `DeleteItem`.
- **infra/alarms** — Alarm descriptions are runbooks. Any runbook text naming a renamed log line
  changes in the same commit.

Full text: `agent-os/standards/`.
