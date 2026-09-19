# Side-Effect Order

`_process_story` runs its side effects (S3 writes, Telegram posts and deletes, DynamoDB writes) in a fixed order behind a read-only gate. Each one can fail and leave the channel and archive safe for the next run.

1. `store.find_story`: if the fingerprint is unchanged, stop
2. `archive.save`: if S3 fails, nothing is posted. Every image that reaches the channel is archived. A leftover pair from a failed send is harmless (same revision, same keys)
3. `telegram.send_photo`
4. `store.record_posted`, only after Telegram accepts. If this fails, the next run reposts, and the old message is **not** deleted
5. `telegram.delete_message` for the replaced message, last

- Never delete before the new post is recorded. A crash at any step leaves the old message, or both, never zero
- A failed delete (Telegram refuses after 48h) logs `"Telegram delete failed, old message kept"` as a WARNING. It doesn't count as failed, doesn't raise and doesn't repost
- A new side effect (another channel, a notification and so on) needs its place in this order and a test that fails at that step (`testing/handler-tests`)
