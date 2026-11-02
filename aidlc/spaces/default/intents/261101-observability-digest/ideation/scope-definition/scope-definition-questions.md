# Scope Definition — Questions

Input: the approved intent statement (`ideation/intent-capture/intent-statement.md`). No feasibility
assessment or constraint register exists for this work.

The weekly digest was removed from the intent (warnings now live on the dashboard and never notify the
owner), so the questions below were rewritten. The one answer that still stands is Q3.

The intent statement names three capabilities, used below:

- **Warnings view**: warnings of the named kinds shown on the dashboard, which the owner reviews on a regular basis.
- **Health view**: one place to tell in under a minute whether the bot is healthy.
- **Sturdy alarms**: alarms that keep their signal when a log message is reworded, proven by an automated test.

## Q1. [Product owner] Which capability, on its own, would be worth having first?

This sets the minimum that delivers value if the work stopped after one piece.

A. Warnings view
B. Health view
C. Sturdy alarms
D. None alone; all three together are the minimum
X. Other (please specify)

[Answer]: B

## Q2. [Product owner] Which are must-haves for this piece of work? (select all that apply)

Anything not selected becomes nice-to-have: done if time allows, or left for later.

A. Warnings view
B. Health view
C. Sturdy alarms
D. A broader tidy-up of how the bot records what happens (consistent levels and fields), beyond what the three capabilities need
X. Other (please specify)

[Answer]: A, B, C, D

## Q3. [Product owner] How far should the review of the bot's logging go?

Earlier you asked to look at the logging strategy in general. This draws its edge.

A. Only as far as the warnings view, health view and sturdy alarms need
B. Also fix other logging problems found along the way, when they're small
C. A full review of all logging, as its own deliverable
D. Not yet defined
X. Other (please specify)

[Answer]: C

## Q4. [Product owner] In what order should the capabilities be delivered?

A. Risk first: sturdy alarms first, since the other two will likely read the same signals
B. Value first: the warnings view first, since it surfaces warnings you never see today
C. Learning first: whatever teaches the most about observability on AWS
D. No preference; order them by what each depends on
X. Other (please specify)

[Answer]: B (clarified: the Health view is delivered first, since it was named worth having on its own; the Warnings view follows)

## Q5. [Product owner] Are there hard deadlines for any capability?

A. None
B. Yes, before a specific date (say which and why)
C. Not yet defined
X. Other (please specify)

[Answer]: A

## Q6. [Operations] When is this piece of work done?

A. Running in production, with the dashboard showing real warnings and health signals
B. Running in staging only; production can follow later
C. Not yet defined
X. Other (please specify)

[Answer]: A

## Q7. [Product owner] What else stays out of this piece of work? (select all that apply)

A. Dashboard views for offices the bot doesn't cover yet
B. New alarms, other than those needed to keep the existing ones sturdy
C. Tracking AWS spend on the dashboard (the existing budget alert stays as is)
D. None of these
X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- First piece worth having on its own: the Health view (Q1); it is also delivered first, with the Warnings view after it (Q4).
- Must-haves: Warnings view, Health view, Sturdy alarms and the broader logging tidy-up (Q2).
- Logging review: a full review of all logging, as its own deliverable (Q3).
- No hard deadlines (Q5).
- Done when it is running in production with the dashboard showing real warnings and health signals (Q6).
- Left out: dashboard views for offices the bot doesn't cover yet (Q7).

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
