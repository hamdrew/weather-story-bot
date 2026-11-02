# User Flow: checking on the bot

Inputs: the intent statement, scope document and intent backlog. The owner is the only user. They look at the
dashboard on a regular basis (their own cadence); in addition, any warning trips an alarm that emails them, which
is another way into this flow. Each
environment has its own dashboard.

## Core flow (happy path)

```
Owner opens the dashboard
        |
        v
Reads the verdict box at the top
(verdict, signals that are off, error and warning totals)
        |
   +----+--------------------+----------------------+
   |                         |                      |
 HEALTHY                NOT HEALTHY              UNKNOWN
   |                         |                      |
   v                         v                      v
Warning total zero?    Reads every signal        No data came in:
   |       |           that is off, and any      checks whether the
  yes      no          error kinds               bot is running
   |       |                 |                      |
   v       v                 v                      v
 Done    Reads the       Opens errors, warnings  Opens the detail
         warnings list   and detail to dig in    to see when data stopped
```

## Steps

1. The owner opens the dashboard for the environment they care about.
2. The verdict box tells them in one look whether the bot is healthy, not healthy, or unknown, and shows the total errors and warnings.
3. If healthy with no warnings, they are done in under a minute.
4. If healthy but the warning total is not zero, they read the warnings in the recent list.
5. If not healthy, the verdict names every signal that is off and any error kinds; they read the errors, warnings and detail charts to see why.
6. If unknown, no data came in when the bot should have run; they look at the detail to see when data stopped.

## Branches and edge cases

- Quiet period: zero counts and an empty recent list are shown in words.
- More entries than the recent list holds: the list says how many more there are in the window.
- Warning alarm email: the owner opens the dashboard from the email and follows the same flow.
- Stale or broken view: nothing notifies the owner if the dashboard itself stops updating. The "unknown" state covers missing data; a "last updated" time is a proposal for requirements, which also decide whether anything more is needed.
