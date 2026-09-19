# Story Identity

Two hashes in `state.py`:

| | Answers | Inputs |
|---|---|---|
| `story_key` | Which story is this? | `title` + `start_time` in UTC |
| `content_fingerprint` | Did the message change? | image sha256 + `description` |

Both are sha256 of `json.dumps(..., sort_keys=True)`.

- Never use NWS-volatile fields: image UUID (`image_id`), `updateTime` (NWS re-issues with the epoch) or `endTime`
- A field goes in the fingerprint only if changing it changes the Telegram message (caption or image). Identity fields don't count
- If `build_caption` starts showing a different `Story` field, update `content_fingerprint` in the same commit. Fixed text (link wording, the "Updated" prefix) and `office_id` stay out, since adding them would repost every active story
- Compare instants, not strings: `start_time.astimezone(UTC)`
- When NWS edits a title or start time, that's a new story. It posts again and the old message stays. This is on purpose: title + start is the only stable identity NWS gives, and a repost is OK where a missed story is not
- Changing either hash's inputs changes stored values. A fingerprint change reposts every active story as "Updated" on the next run. A `story_key` change needs a migration (see `backend/dynamodb-schema`)
