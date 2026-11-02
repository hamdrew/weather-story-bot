# Intent Backlog

Proto-units in delivery order. Priority is MoSCoW; all five are Must because the owner chose them all as must-haves.

| # | Proto-unit | Priority | Depends on | Value |
|---|------------|----------|------------|-------|
| 1 | Health view | Must | none | One place to tell in under a minute whether the bot is healthy |
| 2 | Warnings and errors view | Must | 1 (shares the dashboard) | Warnings and errors of the named kinds are visible on the dashboard |
| 3 | Sturdy alarms | Must | none | Alarms keep their signal when a log message is reworded, proven by an automated test |
| 3a | Warning alarm | Must | 3 (uses the same sturdy signals) | Any warning of the named kinds emails the owner |
| 4 | Logging review | Must | none | A full review of all logging as its own deliverable; its findings feed items 1 to 3 and 5 |
| 5 | Broader logging tidy-up | Must | 4 | Consistent levels and fields beyond what items 1 to 3 need |

## Notes

- Order is Health view first (the owner named it worth having on its own and chose it first), then the Warnings and errors view. Items 3 to 5 are placed by dependency in later stages.
- Items 1 and 2 both read signals the bot records, so the logging review (item 4) may reshape their inputs; requirements decide the exact order.
- Out of this backlog: other offices' dashboard views, Telegram changes, third-party monitoring, any digest, and any new notification other than the warning alarm email.

## Value Stream

Bot records what happens (logs and metrics), then signals feed the alarms and the dashboard, then the owner looks at the dashboard and sees health, warnings and errors.
