# Archive Layout

The S3 archive faithfully records every posted revision, laid out so you can browse it in the console.

```
stories/{office}/{YYYY}/{MM}/{DD}/{HHMM}Z-{title-slug}-{story_key[:8]}/{fingerprint[:16]}.{png,json}
```

- The date and time are the story's **start** in UTC. The folder is one story and each file pair is one revision
- The slug is only for reading (ASCII, at most 48 chars, `story` if empty). The `story_key` suffix is what makes the path unique
- Build paths only with `archive_prefix()`. Never assemble keys by hand
- The same revision writes to the same keys (safe to rewrite). New content adds a pair in the same folder
- `.json` is `story.raw`, the NWS payload verbatim. Never add derived fields; compute them at read time
- Never move or rename existing objects except with a tested migration script (`backend/dynamodb-schema`)
- The layout wasn't designed for Athena partition pruning. Future analytics may need its own layout or an index
