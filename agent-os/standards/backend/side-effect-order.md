# Side-Effect Order

`handler._apply_post_or_update` runs its side effects (S3 writes, Telegram posts and deletes, DynamoDB writes) in a fixed order, behind a read-only gate that now sits upstream in `planner.decide` (`global/principles.md`: decide purely, then act). `run` reads `store.find_story` for every downloaded story before deciding; `decide` is what turns "fingerprint unchanged" into an `unchanged` `Decision` that `_apply_decisions` skips before any side effect runs. Each side effect below can still fail and leave the channel and archive safe for the next run.

0. `lease.take` (`state.OfficeLease`), before anything else for the office, released in a `finally` after step 5. If another run holds it, the office is `skipped` with no NWS call and no write; if DynamoDB errors, it's `failed` (`backend/run-outcomes`). This is what keeps two overlapping runs from both posting the same story
1. `store.find_story`, read by `run` before `decide`: if the fingerprint is unchanged, `decide` returns `unchanged` and nothing below runs
2. `archive.save`: if S3 fails, nothing is posted. Every image that reaches the channel is archived. A leftover pair from a failed send is harmless (same revision, same keys)
3. `telegram.send_photo`
4. `store.record_posted`, only after Telegram accepts: the current-story record and its `posted`/`updated` ledger event, in one `TransactWriteItems`. If it fails (including a cancelled event-key collision), neither is written, the story counts `failed`, the next run reposts, and the old message is **not** deleted
5. `telegram.delete_message` for the replaced message, last

- Never delete before the new post is recorded. A crash at any step leaves the old message, or both, never zero
- A failed delete (Telegram refuses after 48h) logs `"Telegram delete failed, old message kept"` as a WARNING. It doesn't count as failed, doesn't raise and doesn't repost
- A new side effect (another channel, a notification and so on) needs its place in this order and a test that fails at that step (`testing/handler-tests`)

## The ledger event, inside the chain

A recorded post always has its event, and an event never describes a post that wasn't recorded: `record_posted` writes both or neither. It passes no `ClientRequestToken`: botocore fills one in for every call and reuses it on its own retries, so a retry after a lost response is a no-op rather than a cancelled event write. Those retries are the only re-send (`backend/retries`: the next run is the real retry, with a new message), so a token of our own would add nothing. A code-level retry would get a fresh token and a new event time, so after a lost success it would write a second event for the same message: don't add one without reusing the first attempt's `posted_at`. The orphaned message a failed record leaves (sent, never recorded) stays in the channel beside the repost: a repost, never a missed story.

## History writes, outside the chain

`history.StoryHistory`'s other writes are best effort (`backend/dynamodb-schema`): each failure logs WARNING `"History write failed"`, never blocks a post and never counts as `failed`. They sit around the chain, never between its steps, so a history outage can't change what reaches the channel:

- **Rejected events**: after the `"Ambiguous stories from NWS"` line, before any post
- **`last_seen_at`**: on each `unchanged` decision, in place of steps 2–5. Never on a post or update: `record_posted` has just replaced the item
- **Deleted/delete-failed event**: after the old message's delete, timed at the delete. It is about the replaced revision only (`history.record_deletion`)
- **Run record**: after the lease is released, only for a run that held it. A lost or failed lease leaves no `RUN#` item
