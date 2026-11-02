# Intent Capture & Framing — Questions

## Sources

- [desc] Initial description: "A CloudWatch dashboard and a weekly digest of any warnings that occur"
- [scope] Workflow-selected scope: `classic`.
- [memory:M1] `aidlc/spaces/default/memory/project.md#Way of Working`: "ALWAYS report times to the owner in America/Chicago."

These questions treat the request as an open idea. Earlier notes about a dashboard and digest
are not taken as settled; each answer here decides it fresh.

## Q1. [Product owner] What problem should this solve? (select all that apply)

Today the bot emails you only when an alarm changes state. This asks what is actually going
wrong for you, before anything is designed.

A. Warnings happen that never trip an alarm, so I never hear about them
B. I can't see how the bot is doing at a glance without digging through logs
C. Some alarms depend on the exact wording of a log message, so a reworded message can silently break an alarm
D. Not yet defined
X. Other (please specify)

[Answer]: A, B, C

## Q2. [Product owner] Who will read the dashboard and the digest?

This decides whether the result is written for you alone or for someone without your context.

A. Just me
B. Me, plus someone else who may need to understand the bot's health
C. Not identified yet
X. Other (please specify)

[Answer]: A

## Q3. [Product owner] What would tell you this worked? (select all that apply)

These become the measurable success criteria for the work.

A. Every warning from a week shows up in that week's digest; none are missed
B. I can tell whether the bot is healthy in under a minute, from one place
C. Rewording or refactoring a log message can no longer silently stop an alarm from working
D. Not yet defined
X. Other (please specify)

[Answer]: A, B, C (option A now reads as "every warning of the named kinds shows up on the dashboard", because Q15 removed the digest)

## Q4. [Product owner] Why now?

The trigger shapes how much to take on in this first version.

A. It's the next item now that the office expansion was dropped
B. Something went wrong recently and I didn't notice soon enough
C. I want to learn more about observability on AWS, and this is a good, real place to practise
D. Not identified
X. Other (please specify)

[Answer]: C

## Q5. [Product owner] What should this first version leave out? (select all that apply)

The work follows the plan you approved; this only asks what the first version should not do.

A. No change to what the bot posts to Telegram, or how
B. No change to the existing alert emails (when they fire and what they say)
C. No new third-party or paid monitoring services outside AWS
D. None; nothing is ruled out yet
X. Other (please specify)

[Answer]: A, C

## Q6. [Operations] What should count as a "warning" worth hearing about?

The request says "any warnings that occur". This decides how wide that net is.

A. Anything the bot itself records as a warning or an error
B. Only things that need me to do something
C. Anything unusual, including patterns nothing records as a warning today (for example NWS sending odd data, retries, slow runs)
D. Not yet defined; work it out during requirements
X. Other (please specify)

[Answer]: C

## Q7. [Operations] How often, and when, should the digest reach you?

The request says weekly. This settles what a quiet week looks like.

A. Weekly, and only when there was something to report
B. Weekly, always, with an "all quiet" note when nothing happened
C. Not yet defined
X. Other (please specify)

[Answer]: Superseded by Q15: the weekly digest is removed, so this no longer applies. (The earlier answer, B, came from Q11.)

## Q8. [Operations] Where should the digest reach you?

Today's failure alerts go to email, partly because Telegram itself could be what's broken.

A. Email, like the current alerts
B. Telegram
C. Not yet defined
X. Other (please specify)

[Answer]: Superseded by Q15: there is no digest to deliver, so this no longer applies. (The earlier answer was A, email.)

## Q9. [Operations] How much extra monthly AWS cost is acceptable for this?

Some monitoring features cost money past the free tier (for example, extra dashboards or alarms).

A. Stay within the free tier
B. Up to about $1 a month
C. Up to about $5 a month
D. Not yet defined
X. Other (please specify)

[Answer]: C

## Q10. [Product owner] Which warnings does "none missed" cover?

The review pointed out that "every warning shows up in the digest" can't be checked while "unusual" is still open.

A. A named list of warning kinds, fixed when the requirements are written; "none missed" means none of those
B. Anything unusual at all, as broad as the design can make it, even if that can't be fully checked
C. Not yet defined
X. Other (please specify)

[Answer]: A (the named list now applies to what the dashboard shows, per Q15)

## Q11. [Product owner] Do you need to tell a quiet week apart from a digest that failed to run?

The digest is sent only in weeks with something to report, so no email could mean either.

A. Yes; a failed or missing digest must reach me some other way
B. No; a missing email is fine to read as a quiet week
C. Not yet defined
X. Other (please specify)

[Answer]: Superseded by Q15: the weekly digest is removed, so this no longer applies. (The earlier answer was: "Send the weekly digest, even if there's nothing to report, and there should be an alarm when the digest fails".)

## Q12. [Product owner] What should "healthy" mean when you look at the bot?

"Healthy in under a minute" needs a definition to be checkable.

A. A short list of signals, fixed when the requirements are written, that together say healthy or not
B. Runs are happening on schedule, without errors, and stories are getting posted
C. Not yet defined
X. Other (please specify)

[Answer]: A

## Q13. [Product owner] How should "rewording a log message can't break an alarm" be checked?

The review asked for a way to prove this success metric.

A. An automated test that fails if a change would leave an alarm without its signal
B. A manual check on staging after each change that touches logging
C. Not yet defined
X. Other (please specify)

[Answer]: A

## Q14. [Product owner] Are the existing alert emails open to change?

Earlier you left "no change to the existing alert emails" unselected; this confirms what that meant.

A. Yes, open to change if the work needs it
B. Not ruled out, but change them only when there's a clear reason
C. No, leave them as they are
X. Other (please specify)

[Answer]: A

## Q15. [Product owner] Should the weekly digest stay?

You raised this during the scope step. It is recorded here so one clear answer replaces the earlier digest answers (Q7, Q8 and Q11).

A. Keep the weekly digest
B. Remove it, and show the warnings on the dashboard instead
X. Other (please specify)

[Answer]: X. Let's remove the weekly digest altogether, and the warnings can be part of the dashboard. Something that I review on a regular basis, but I don't need to be notified.

## Q16. [Product owner] Should the dashboard show errors as well as warnings?

You raised this during the mockups step ("We should probably also show errors!"). It is recorded here because it widens the intent.

A. Yes, the same way as warnings: a named list of error kinds fixed in requirements, a count by kind and a recent list, with the same "none missed" target
B. Yes, with errors in their own area above warnings
C. Only in the verdict at the top, with no separate list
X. Other (please specify)

[Answer]: A

## Q17. [Product owner] Should any warning raise an alarm?

You raised this at the approval step ("Add an alarm if there are any warnings"). It changes Q15 for warnings, so it is recorded here.

A. Yes, and the alarm emails me like the current alerts
B. Yes, but the alarm only shows on the dashboard, with no email
C. Yes, for warnings and errors, and it emails me
X. Other (please specify)

[Answer]: A. This replaces the "never notifies" part of Q15 for warnings; the dashboard stays the place to review them.

## Consolidated Summary Confirmation

- Problem: warnings happen that never trip an alarm; there is no at-a-glance view of the bot's health; and some alarms depend on a log message's exact wording, so rewording it can silently break the alarm (Q1).
- Reader: just you (Q2).
- Success: every warning of the named kinds shows up on the dashboard for the week it happened; you can tell whether the bot is healthy in under a minute from one place; rewording a log message can no longer silently stop an alarm working (Q3, Q15).
- Trigger: learning observability on AWS in a real project (Q4).
- Out of this first version: no change to what the bot posts to Telegram or how; no third-party or paid monitoring services outside AWS (Q5). The existing alert emails are open to change if the work needs it (Q14).
- A "warning" means anything unusual, including patterns nothing records as a warning today (Q6); "none missed" covers a named list of warning kinds fixed when the requirements are written (Q10).
- There is no weekly digest and no email for warnings. Warnings are part of the dashboard, which you review on a regular basis and which never notifies you (Q15). This replaces the earlier digest answers (Q7, Q8, Q11).
- "Healthy" is a short list of signals fixed when the requirements are written (Q12).
- An automated test proves that rewording a log message can't leave an alarm without its signal (Q13).
- Extra cost: up to about $5 a month (Q9).

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

## Assumption Confirmation

The answers to Q10 to Q14 settled the intent statement's assumptions. The stakeholder map still carries one:

- The owner, as the only reader, is also the one who decides scope and priority, and nobody else influences those decisions. This was not asked directly. [assumption]

A. Accept assumptions
B. Convert to follow-up questions

[Answer]: A. Accept assumptions
