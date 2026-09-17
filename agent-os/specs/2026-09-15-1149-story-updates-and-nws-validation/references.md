# References for Story Updates and NWS Validation

## Similar Implementations

### MVP content fingerprint (Task 12)

- **Location:** `agent-os/specs/2026-09-13-0026-weather-story-mvp/plan.md` Task 12; `content_fingerprint` in `src/weather_story_bot/state.py`
- **Relevance:** The first dedupe across image UUIDs. This spec narrows the fingerprint to image + description and stores it per story instead of per fingerprint.
- **Key patterns:** Canonical JSON hashing, with fields listed explicitly.

### Undeployed edit-in-place fix (2026-09-15)

- **Location:** Uncommitted work on `main` before branch `story-updates-and-nws-validation`, reviewed with `/code-review high`
- **Relevance:** Introduced `story_key` (title + start) and the `story#` item, which this spec keeps.
- **Review findings that shaped this spec:**
  - Two listed stories sharing a key could make an edit land on the wrong message. Now an ambiguity rejection.
  - Edits didn't count toward `StoriesPosted`. Reposts do.
  - `record_duplicate` overwrote a posted story's own item. Removed.

### Telegram client send path

- **Location:** `TelegramClient.send_photo` / `_call` in `src/weather_story_bot/telegram.py`
- **Relevance:** `delete_message` reuses `_call` for 429 handling and token-safe errors, and follows the `_PhotoRejectedError` pattern for a private "not found" subclass.

## External

### Telegram Bot API `deleteMessage`

- **Location:** https://core.telegram.org/bots/api#deletemessage (checked 2026-09-15)
- **Key points:** Returns `True`. A message can only be deleted if it was sent less than 48 hours ago. Bots with `can_post_messages` can delete their own outgoing channel messages.
