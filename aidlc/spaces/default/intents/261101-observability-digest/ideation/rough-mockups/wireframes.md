# Wireframes: the bot dashboard

Inputs: the intent statement (`ideation/intent-capture/intent-statement.md`), the scope document and the
intent backlog (`ideation/scope-definition/`). These are rough sketches to settle layout and hierarchy; the
signals, warning and error kinds, list lengths and time windows shown are placeholders that requirements will fix.

## Screen: the bot dashboard (one page, top to bottom)

The only screen. It is a CloudWatch dashboard, read by the owner alone, on a computer or at phone width.
Each environment (staging, production) has its own dashboard, so the page carries no environment label (Q8).

```
+--------------------------------------------------------------+
| Weather Story Bot                     [proposal: last updated]|
+--------------------------------------------------------------+
| 1. HEALTH                                                    |
|   +--------------------------------------------------------+ |
|   |  HEALTHY | NOT HEALTHY | UNKNOWN                        | |
|   |  off: <every signal that is off>                       | |
|   |  errors seen: <error kinds that caused not healthy>    | |
|   |  errors: <total>   warnings: <total>   (same window)   | |
|   +--------------------------------------------------------+ |
|   [signal 1] [signal 2] [signal 3] [signal 4]               |
|    value      value      value      value                    |
|    trend      trend      trend      trend                    |
+--------------------------------------------------------------+
| 2. ERRORS AND WARNINGS                    window: <period>   |
|   Count by kind                                              |
|   +--------------------+----------+--------+                 |
|   | kind               | level    | count  |                 |
|   +--------------------+----------+--------+                 |
|   | <error kind A>     | error    |   1    |                 |
|   | <warning kind B>   | warning  |   2    |                 |
|   +--------------------+----------+--------+                 |
|   Most recent (newest first, up to <N>, same window)         |
|   +-----------------------+----------+--------+-----------+  |
|   | time (America/Chicago)| level    | kind   | detail    |  |
|   +-----------------------+----------+--------+-----------+  |
|   | <time>                | error    | <kind> | <detail>  |  |
|   +-----------------------+----------+--------+-----------+  |
+--------------------------------------------------------------+
| 3. DETAIL                                                    |
|   Longer-range charts behind the signals above               |
+--------------------------------------------------------------+
```

At phone width the same order holds in a single column: the verdict box, the signal tiles stacked, the count
table, the recent list, then the detail charts. In the recent list, time, level and kind stay visible; detail
wraps below them.

### Information hierarchy

1. The verdict: healthy, not healthy or unknown, with every signal that is off, and the total error and warning counts.
2. The signals behind the verdict.
3. Errors and warnings: counts by kind, then the most recent list.
4. Detail charts for digging in.

### Verdict rules (sketch)

- **Healthy**: all health signals are fine and there are no errors in the window. Warnings never change the verdict (Q6), but their total is always shown in the verdict box, so a healthy owner sees it without scrolling.
- **Not healthy**: a health signal is off or an error happened in the window (Q6). The verdict lists every signal that is off, not just the first.
- **Unknown**: the bot should have run but no data came in (Q7). This is its own state, worded and styled so it cannot be read as healthy.
- **Precedence**: unknown wins over not healthy and healthy, because missing data means the other signals can't be trusted. Any signals that are off or errors already seen are still listed in the box. Requirements fix the exact rule.

### Errors and warnings area (sketch)

- Errors and warnings share one area and get the same treatment: named kinds, a count by kind, and a recent list (Q16 in Intent Capture).
- The counts and the recent list cover the same window, so a count never refers to entries the list has dropped. The window and the list length `<N>` are placeholders for requirements; if the window holds more than `<N>` entries, the list says how many more there are.

### States

- Healthy, nothing logged: verdict says healthy with zero totals; the count table shows zeros; the recent list says "no errors or warnings in this window".
- Not healthy: the verdict names every signal that is off, and any error kinds that caused it.
- Unknown: the verdict says unknown; each area below says there is no data in words, rather than showing an empty chart.

### Proposals for requirements

- **Last updated**: a time at the top showing when data last arrived, to help with the open item on spotting a stale or broken view. It was not in the answers and CloudWatch may not offer it directly; requirements accept or drop it.

### Accessibility note

No requirements beyond the standard CloudWatch look (Q5). Sketch assumption, not a requirement: the dashboard
title reads as the top heading, and Health, Errors and warnings, and Detail as the headings below it; landmarks
and keyboard use are whatever CloudWatch provides.
