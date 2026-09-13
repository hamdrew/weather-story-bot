# Product Roadmap

## Phase 1: MVP

- **Detect new stories:** Check the NWS MKX (Milwaukee/Sullivan) office on a schedule and notice when a new Weather Story is published.
- **Push notification via Telegram:** Post each new story's image and description to Telegram. Telegram handles both the notification and the display.
- **MKX only:** Only one office is needed for launch. The design should still make it easy to add more offices later.
- **Failure alerts:** Watch the Lambda and email me when it fails or stops running on schedule. The Gmail app shows the email as a push notification on my iPhone. Alerts don't go through Telegram, because Telegram could be the thing that's broken. Send a follow-up email when things recover, and don't alert on a single flaky run.
- **Silent-problem alerts:** Email me when the bot runs without errors but something is still wrong:
  - **Gone quiet:** No stories posted for a couple of days (for example, the NWS API changed and now returns nothing).
  - **Repost loop:** Far more posts than normal in a short time.
- **Cost alert:** Email me if monthly AWS spend for the account goes over a small budget.

## Phase 2: Post-Launch

- **Multiple offices:** Support more NWS offices, with a separate Telegram channel for each office.
- **Story archive:** Save past Weather Stories so they can be looked up later.
- **Channel promotion (long-term):** Possibly promote the per-office channels to a wider audience.
