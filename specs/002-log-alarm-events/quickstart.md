# Quickstart: validating Log Alarms on Event Names

Steps 3 onward touch live AWS. Steps that change anything are the owner's, with the MFA profile.

## 1. Offline gates

```sh
mise run lint ::: test ::: tftest ::: scan
```

Expected: all pass, with no credentials.

## 2. Drift check

Rename `telegram.message_sent` on one side only (in `src/` or in `infra/monitoring.tf`), run `mise run test`, and
confirm the failure names the event. Repeat for `nws.ambiguous_stories`, then undo each edit.

## 3. Filter proof before merge (FR-006)

With the `readonly` profile, run CloudWatch's `TestMetricFilter` once for each pattern against the sample lines in
[contracts/alarm-signals.md](contracts/alarm-signals.md). Use the real JSON line shape. Record each case's expected and
actual result in the pull request.

## 4. Bootstrap before merge (owner)

```sh
mise run bootstrap-plan
mise run bootstrap-deploy
```

Expected plan: the policies that use production's alarm ARNs replace the 8 exact names with `weather-story-bot-*`, and
nothing else changes.

## 5. Review the plan

Expected for each environment: 2 filters and 2 alarm descriptions updated in place, the dashboard updated in place,
**1 alarm added**, and nothing replaced or deleted (SC-006).

## 6. Staging, after the merge deploys it (owner)

The new alarm's actions are on at this point, and it is expected to send one OK email.

1. Set `weather-story-bot-staging-slow-runs` to `ALARM` by hand. Expected: one alert email.
2. Set it to `OK`. Expected: one recovery email.
3. Run `mise run pause staging`. Expected: only the slow-run alarm's actions change, and the schedule stays disabled.

## 7. Production, after approval

1. Expected: one OK email from the new alarm, and no other alarm email during the next 24 hours (SC-003).
2. After the first post, compare `StoriesPosted` with the count of `telegram.message_sent` lines over the same period.
   Expected difference: 0 (SC-002).
3. On the dashboard, confirm the posts charts are continuous across the deploy, the duration chart shows runs far below
   the 60-second line, and the verdict is unchanged.
4. Expected over the first 7 days: no slow-run alert email (SC-008).

## Rollback

Reverting to code from before U2 **also requires reverting this change**. Otherwise `quiet` raises a false alert while
`repost-loop` and `nws-ambiguous` go blind.
