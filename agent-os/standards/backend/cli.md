# Local CLI

`uv run weather-story-bot --dry-run` is a developer tool. It fetches live NWS data and prints captions, and it must never touch production.

- `--dry-run` is `required=True`. Any future mode that writes real state is a new, deliberate flag, never the default
- Posting needs a second explicit flag (`--send-telegram`) **and** `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` for a test channel. Missing creds exit 2 before any HTTP call
- Never uses AWS (DynamoDB, S3, SSM). Anything touching AWS is a `scripts/` tool with a dry run and `--apply` (`backend/dynamodb-schema`)
- Posts go through `handler.post_story`, so captions and uploads match the Lambda. Don't fork that logic
- Only the CLI reads `.env`, through `load_dotenv()`, which never overrides the shell. `python-dotenv` is dev-only, so the import has a no-op fallback
- One story's failure prints `error: ...` to stderr and the rest continue

| Exit | Meaning |
|---|---|
| 0 | success, or no active stories |
| 1 | NWS list failed, or any story failed |
| 2 | usage error (argparse, missing creds) |
