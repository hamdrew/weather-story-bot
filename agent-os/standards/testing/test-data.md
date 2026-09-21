# Test Data

Build stories from NWS-shaped data so tests use the same parsing path as production.

- One story: `make_story(**overrides)` from `tests.conftest`. Overrides use the NWS camelCase keys (`startTime`, `updateTime`, `download`), not `Story` attributes
- A real listing: `mkx_payload` (raw JSON) or `mkx_stories` (parsed)
- `mkx_payload` is function-scoped and re-read from disk each test, so mutate it in place (`.reverse()`, `.append()`, `story.update(...)`). Never widen its scope

## Production quirks become cases

When NWS does something unexpected, add a case to the closest parametrized test and date the comment:

```python
@pytest.mark.parametrize(
    "overrides",
    [
        # NWS re-issued "High Swim Risk" on 2026-09-15 under a new UUID, updateTime at the epoch.
        {"download": REISSUED_DOWNLOAD, "updateTime": EPOCH, "altText": ""},
    ],
)
```

- Capture a new file in `tests/fixtures/` only when overrides can't express the quirk
