# Data Model: Log Alarms on Event Names

This feature stores no application data. The entities are monitoring configuration.

## Signal event

| Event | Emitted by | Level | Filter |
|-------|------------|-------|--------|
| `telegram.message_sent` | `telegram.py` (L14) | INFO | stories posted |
| `nws.ambiguous_stories` | `handler.py` (L08) | ERROR | NWS ambiguous |

**Validation**: each event is a constant in `src/`, appears in `docs/logging-review.md` table 1, and is named by exactly
one filter.

## Log filter

| Field | Stories posted | NWS ambiguous | Changes? |
|-------|----------------|---------------|----------|
| Name | `<name>-stories-posted` | `<name>-nws-ambiguous` | no |
| Pattern | `{ $.event = "telegram.message_sent" }` | `{ $.event = "nws.ambiguous_stories" }` | **yes** |
| Metric | `StoriesPosted` | `AmbiguousStories` | no |
| Namespace | `WeatherStoryBot` (production), `WeatherStoryBot/staging` | same | no |
| Value | `1` | `1` | no |

## Log-based alarm

| Alarm | Metric | Change |
|-------|--------|--------|
| `quiet` | `StoriesPosted` | none |
| `repost-loop` | `StoriesPosted` | description names `telegram.message_sent` |
| `nws-ambiguous` | `AmbiguousStories` | description names `nws.ambiguous_stories` |

## Slow-run alarm (new, one per environment)

| Field | Value |
|-------|-------|
| Name | `<name>-slow-runs` |
| Metric | `AWS/Lambda` `Duration`, dimension `FunctionName` |
| Statistic, period | `Maximum`, 900 seconds |
| Evaluation | 2 of 2 periods |
| Comparison, threshold | `GreaterThanThreshold`, `60000` milliseconds |
| Missing data | `notBreaching` |
| Actions | alarm and OK to the environment's alerts topic |
| Start and pause | member of `local.alarm_names` |
| Verdict | not a member of `health_signals` or `not_healthy_alarms` |

### State transitions

```text
INSUFFICIENT_DATA -> OK      first evaluation; expected to send one OK email if actions are on
OK                -> ALARM   maximum above 60 s in 2 consecutive periods; one alert email
ALARM             -> OK      a period at or under 60 s, or with no runs; one recovery email
```

## Duration chart (new)

| Field | Value |
|-------|-------|
| Position | new last dashboard row, width 12, height 6 |
| Series | hidden alarm metric `m1`, visible expression `m1/1000` (seconds) |
| Period, statistic | read from the alarm |
| Threshold line | `alarm.threshold / 1000`, shaded above |

## CI role alarm names

| Role | Before | After |
|------|--------|-------|
| Production apply | 8 exact names | `weather-story-bot-*` (also matches staging's names, accepted in research R5) |
| Staging apply | `weather-story-bot-staging*` | unchanged |
