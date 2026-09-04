# U-01 Code Generation Plan

U-01 implements protected office information, CloudWatch/SNS private alert notification, safe
observability, and one definitive-failure fallback. It must not add custom alert state, a queue,
public endpoint, or deployment authority.

- [x] Step 1: Add typed bounded command, alarm, observation, and outcome models in `src/`, using
      the locked `detect-secrets` engine as the final rejection stop-gap.
- [x] Step 2: Add office refresh and conditional current-office persistence in existing modules.
- [x] Step 3: Add alarm validation, bounded alert rendering, one fallback, and loop prevention.
- [ ] Step 4: Extend runtime composition and handlers with narrow validated entry points.
- [ ] Step 5: Add deterministic example tests for authorization, refresh, fallback, ambiguity, loops.
- [ ] Step 6: Add Hypothesis properties for sanitizer, alarms, refresh, Telegram entities, lifecycle.
- [ ] Step 7: Add U-01 SAM artifacts per approved infrastructure design; validate locally only.
- [ ] Step 8: Add code summaries/traceability, format, and run `make check`.

Every step modifies brownfield files in place, preserves mock-only dev and no-secret fixtures, and
must be checked off in this plan in the same interaction as completion.
