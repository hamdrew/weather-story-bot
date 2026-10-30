# Test Data

Build stories from NWS-shaped data so tests use the same parsing path as production.

- One story: `make_story(**overrides)` from `tests.conftest`. Overrides use the NWS camelCase keys (`startTime`, `updateTime`, `download`), not `Story` attributes
- A real listing: `office_payload(office_id)` (raw JSON) or `office_stories(office_id)` (parsed), over `tests/fixtures/<office>_weatherstories.json`. Use them in new tests; `mkx_payload` / `mkx_stories` are pytest-fixture aliases for `office_payload("MKX")` / `office_stories("MKX")` that stay for existing ones
- Each call re-reads the file, and `mkx_payload` is function-scoped, so mutate a payload in place (`.reverse()`, `.append()`, `story.update(...)`). Never cache one or widen the fixture's scope
- A new office's listing is captured once with a live `curl` (the only network use), saved as `json.tool` formats it, and its capture date goes in `office_payload`'s docstring (JSON has no comments)

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

- Capture a new file in `tests/fixtures/` only when overrides can't express the quirk (a new office's listing is the other reason)
