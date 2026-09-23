# Local CLI

`uv run weather-story-bot --dry-run` is a developer tool. It fetches live NWS data and prints, for every story, the same decision the Lambda would make beside its caption — and it can never write anything (`global/principles.md`: local tools are read-only).

- `--dry-run` is `required=True`. Any future mode that writes real state is a new, deliberate flag, never the default, and needs a spec change first
- No `--send-telegram`. The CLI never imports `TelegramClient` or reads `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` — there is no write path left to gate
- Never uses AWS (DynamoDB, S3, SSM) either. Anything touching AWS is a `scripts/` tool with a dry run and `--apply` (`backend/dynamodb-schema`)
- Calls the same `planner.select_active` + `planner.decide` the Lambda calls, so a preview can't drift from what actually runs. Don't fork that logic
- `--office` is validated against `config.is_valid_office_id` (the same regex `OFFICES_JSON` parsing uses) before any HTTP call, so a malformed value — `--office ../x` — exits 2, not a request to a mangled URL
- Without DynamoDB, `decide()` is always given empty records, so every accepted story looks like a first post: printed as `new-or-updated (state not read)`, never `post`/`update`/`unchanged`. `expired` and `rejected (reasons)` print as-is, both with their caption, same as the Lambda would see them
- Only the CLI reads `.env`, through `load_dotenv()`, which never overrides the shell. `python-dotenv` is dev-only, so the import has a no-op fallback
- One story's download failure prints `error: ...` to stderr and the rest continue

| Exit | Meaning |
|---|---|
| 0 | success, or no active stories |
| 1 | NWS list failed, or a story's image download failed |
| 2 | usage error (argparse: missing `--dry-run`, invalid `--office`) |
