# Approval & Handoff — Questions

Inputs: the intent statement and stakeholder map, the scope document and intent backlog, and the wireframes.
There is no market research, feasibility assessment or team plan for this work: the owner is the only
stakeholder and the only person building it, so those questions don't apply. The intent, scope and mockups
are already approved, so they are not asked again.

## Q1. [Delivery] Do you accept these risks going into requirements?

1. **"None missed" depends on looking.** Nothing notifies you of warnings or errors, so one that happens is only seen when you open the dashboard. A stale or broken view is still an open item.
2. **The logging review is open-ended.** A full review of all logging, plus a broader tidy-up, are both must-haves and could grow larger than the dashboard work itself.
3. **The cost cap is untested.** The dashboard, any new metrics and alarms must fit within about $5 a month; requirements and design have to check this.
4. **Changing the signals can break alarms that work today.** Making alarms independent of log wording means changing what they watch, which is the risk the sturdy-alarms test is meant to cover.

A. Accept all four as they are; requirements and design handle them
B. Accept, but cap the logging review (say how) before requirements
C. Not yet decided
X. Other (please specify)

[Answer]: X. Add an alarm if there are any warnings. (Clarified: the alarm emails the owner like the current alerts; recorded as Q17 in Intent Capture and written into the intent, scope, backlog and user flow. The other three risks are accepted.)

## Q2. [Delivery] Go or no-go into Inception?

A. Go: start requirements
B. Hold: something needs settling first (say what)
X. Other (please specify)

[Answer]: B. Hold for the warning alarm only (clarified); once it was written in, go into Inception.

## Consolidated Summary Confirmation

- Any warning trips an alarm that emails you, like the current alerts. This replaces "never notifies" for warnings; the dashboard stays where you review warnings and errors (Q1, recorded as Q17 in Intent Capture).
- The other risks are accepted as they are: the open-ended logging review, the untested $5 cost cap, and changing what today's alarms watch (Q1).
- With the warning alarm written into the intent, scope, backlog and user flow, the work goes into Inception (Q2).

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
