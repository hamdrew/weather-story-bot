# Log Contracts

Some log messages are an API. CloudWatch metric filters in `infra/monitoring.tf` match `$.message` exactly ("Telegram message sent" -> StoriesPosted, "Ambiguous stories from NWS" -> AmbiguousStories), and runbooks compare "Story posted" against them.

- Pin each one with a test. Add a comment naming the filter, alarm or runbook that depends on it
- Match the whole message and unpack exactly one record:

```python
caplog.set_level(logging.INFO, logger="weather_story_bot")
[rec] = [r for r in caplog.records if r.getMessage() == "Telegram message sent"]
assert vars(rec)["chat_id"] == "-1001"
```

- Check structured fields with `vars(rec)`, not by parsing text
- Also check the message is absent when it shouldn't fire (e.g. a failed send)
- To rename one, change the log call, its test and the `monitoring.tf` pattern or runbook in the same commit
- A test that logs or raises near Telegram asserts `TOKEN not in` the captured text
