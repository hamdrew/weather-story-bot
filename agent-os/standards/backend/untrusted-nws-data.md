# Untrusted NWS Data

Treat every NWS listing as untrusted. If it's ambiguous which story is which, post nothing for the stories involved, skip them, and alert.

Ambiguous means active stories in one listing share any of:

| Field | Why it should be unique |
|---|---|
| Image ID (UUID in `download`) | Identifies one image |
| Title + `startTime` | Identifies one story across revisions |
| Image SHA-256 | Two stories shouldn't show the same graphic |

```python
logger.error(
    "Ambiguous stories from NWS",
    extra={"office": office_id, "stories": [{"image_id": ..., "title": ..., "reasons": [...]}]},
)
```

- Reject every story in a collision, not just the later one: we can't tell which is right
- Log one ERROR line per office per run with that exact message; the `nws-ambiguous` alarm's metric filter matches it
- Count them as `rejected`, not `failed`, and don't raise `ProcessingError`: the bot works, NWS doesn't
- Ignore stories past `endTime` before checking; don't act on them at all
- Don't trust `updateTime` (NWS has sent the Unix epoch) or image UUIDs (NWS re-issues stories under new ones) to detect changes; compare content
- A new check follows the same rule: skip, log `Ambiguous stories from NWS` with a reason, and add a test
