# Intent Capture & Framing: Questions

## Sources

- [desc] Initial description: "Expand NWS office coverage to all NWS offices covering Wisconsin counties.  GRB,ARX,MPX,DLH  Each office gets a single production Telegram channel.  MPX is added to the existing staging channel to test multi-office behavior without cluttering it.  Staging channel will need to be renamed so it's not MKX-specific.  Avatars will need to be generated.  A pinned message with office information should be added to channels.  Telegram channel provisioning should be automated and a directory of channels stored persistently to keep track.  Cost should be a consideration, as this is a hobby project."
- [scope] Workflow-selected scope: `feature`.
- [memory:M1] `aidlc/spaces/default/memory/project.md#Forbidden`: "NEVER put the Telegram token in Terraform variables or state. (affirmed 2026-10-30)"
- [memory:M2] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS keep each environment's Telegram token in its own SSM parameter. (affirmed 2026-10-30)"
- [memory:M3] `aidlc/spaces/default/memory/project.md#Mandated`: "ALWAYS ask the owner before running `deploy`, `start`, `pause` or `bootstrap-deploy`. (affirmed 2026-10-30)"

## Q1. [Product owner] What problem does adding GRB, ARX, MPX and DLH solve?

Today the bot posts only Milwaukee/Sullivan (MKX) stories. This sets the headline of the intent statement.

A. Stories for the other places I (and people close to me) care about aren't delivered; I'd have to visit the NWS site for them
B. Full Wisconsin coverage as a stepping stone toward a wider public audience later
C. Both A and B
D. Not yet defined
X. Other (please specify)

[Answer]: C

## Q2. [Product owner] Who will read the four new production channels?

This decides whether channel names, descriptions and the pinned message are written for you or for strangers.

A. Just me
B. Me plus family or friends in those areas (for example, in the Twin Cities for MPX)
C. Anyone who finds the channels (public from day one)
D. Not yet defined
X. Other (please specify)

[Answer]: C

## Q3. [Product owner] What tells you this worked? (select all that apply)

These become the measurable success criteria.

A. Each of GRB, ARX, MPX and DLH posts its new Weather Stories to its own production channel, with nothing posted to the wrong channel
B. The staging channel carries both MKX and MPX stories, and each post makes clear which office it came from
C. Setting up a channel (name, photo, description, pinned message, directory entry) is one command rather than a list of hand steps
D. Monthly AWS spend stays within the figure you give in Q5
E. Not yet defined
X. Other (please specify)

[Answer]: A, B, C, D

## Q4. [Product owner] Why now? (select all that apply)

A. It is the next roadmap phase, and the per-office groundwork has already landed
B. Winter weather season is starting, when stories matter most
C. Someone asked for their office
D. Not identified
X. Other (please specify)

[Answer]: A

## Q5. [Product owner] How much more can AWS cost per month after this?

The bot is a hobby project; the cost limit shapes every design choice that follows.

A. Effectively nothing: four more offices must add no fixed monthly cost, only pennies of pay-per-use
B. Up to about $1 a month more
C. Up to about $5 a month more
D. Not yet defined
X. Other (please specify)

[Answer]: X. "Let's not restrict to $5/month more.  Maximum $20/month, and cost estimates should be done as part of the work." (revised at the summary confirmation; first answered C)

## Q6. [Product owner] How far should "automated channel provisioning" go?

A feasibility note to surface early: a Telegram bot can rename a channel, set its photo and description, and post and pin a message once it is an admin, but a bot cannot create a channel. Creating one automatically would mean signing in to Telegram as your own user account from a script.

A. All of it, including creating the channel (accepting a script that logs in as my user account)
B. Everything after I create the channel by hand and make the bot an admin: name, photo, description, pinned message and the directory entry
C. Only the directory and a check that each channel is set up correctly; the rest stays by hand
D. Not yet defined
X. Other (please specify)

[Answer]: A

## Q7. [Product owner] What should each channel's identity say?

Covers the channel name, photo (avatar) and the pinned office-information message.

A. Written for strangers: clearly unofficial, no NWS or NOAA logos or seal, a link to the source, and what the office covers
B. Plain and practical, written for me and people I know
C. Not yet defined
X. Other (please specify)

[Answer]: A

## Q8. [Product owner] Who else has a say, and who needs to hear about progress?

A. Only me: I decide and approve everything, and the approvals in this workflow are all the reporting needed
B. I decide, but family gets a say on their channel (for example MPX) and hears when it is ready
C. Not identified
X. Other (please specify)

[Answer]: A

## Q9. [Product owner] What should this first version leave out? (select all that apply)

The workflow plan is already chosen (`feature`); this is only about what the product does not do yet.

A. Offices beyond these five
B. Promoting the channels publicly (directories, forums, the README)
C. Per-office alerts (the existing alarms stay as they are)
D. Changes to how stories are detected, decided and posted beyond what multiple offices need
E. None
X. Other (please specify)

[Answer]: A, B, C, D. Plus, in the owner's words: "The new offices should still cause a general alarm to fire if there is a problem. How alarms work is in-scope, we can change from the risky log-based alarms if it strengthens them and makes office identification easier (e.g. custom metrics and dimensions, cloudwatch integration in the code)"

## Consolidated Summary Confirmation

- Problem (Q1): both — stories for the other places you care about aren't delivered, and full Wisconsin coverage is a step toward a wider audience later
- Readers (Q2): public from day one
- Success (Q3): each of GRB, ARX, MPX, DLH posts to its own production channel with nothing misrouted; staging carries MKX and MPX with each post showing its office; channel setup is one command; monthly AWS spend stays within the Q5 limit
- Trigger (Q4): it is the next roadmap phase and the per-office groundwork has landed
- Cost (Q5): a maximum of $20 a month, with cost estimates done as part of the work
- Provisioning (Q6): fully automated, including creating the channel through a script that signs in as your Telegram user account
- Channel identity (Q7): written for strangers — clearly unofficial, no NWS or NOAA logos or seal, a link to the source, what the office covers
- People (Q8): only you decide and approve; the workflow's approvals are the reporting
- Left out (Q9): offices beyond these five, public promotion, per-office alerts, and detect/decide/post changes beyond multi-office needs — except that the channels' links go in the README, and that is the extent of publishing (Q10) — but the new offices must trip the general alarms, and how alarms work is in scope (moving off log-based alarms to something like custom metrics with an office dimension is allowed if it strengthens them and makes the office easier to identify)
- Review points taken on (Q11): the personal Telegram account's automation risk is unassessed and decided before channel creation is built; today's AWS spend is established first; the alarm scope is stated at the problem level; new stories for each office appear within the same window as MKX today, and an induced failure for one new office must trip an alarm

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

## Requested Changes Feedback

What should change?

[Answer]: Let's not restrict to $5/month more.  Maximum $20/month, and cost estimates should be done as part of the work.

## Assumption Confirmation

The intent statement carries these assumptions:

- [assumption] How the Telegram user-account login used for channel creation is stored and protected is not decided yet. The project rules cover the bot token only: it never goes in Terraform variables or state [memory:M1], and each environment keeps it in its own SSM parameter [memory:M2]. The user-account session is a far more powerful credential than a bot token and needs its own decision in a later stage.
- [assumption] The $20 limit is read as the account's total monthly AWS spend, not $20 on top of today's spend.

A. Accept assumptions
B. Convert to follow-up questions

[Answer]: A. Accept assumptions

## Q10. [Product owner] How much publishing is in this first version?

Follow-up to Q9, raised by the owner with the assumption confirmation: Q9 left public promotion out.

A. None: no links anywhere
B. Add the channels' links to the README, and nothing more
C. Not yet defined
X. Other (please specify)

[Answer]: B. In the owner's words: "We can add the channels' links to the README, but that is the extent of publishing"

## Q11. [Product owner] Which review points should the intent statement take on? (select all that apply)

Follow-up from the approval gate, where the owner asked for changes and picked these.

A. The risk to the owner's personal Telegram account from automating it (rate limits, account restrictions, a cap on public channels per account) is unassessed and must be decided before channel creation is built
B. Establishing today's monthly AWS spend is the first cost-estimate task, so the headroom under $20 is known
C. The alarm scope is stated at the problem level, leaving the mechanism to design
D. A reader-facing metric: new stories for each office appear in its channel within the same window as MKX today; and the alarm coverage metric gets a pass/fail check (an induced failure for one new office trips an alarm)
E. None
X. Other (please specify)

[Answer]: A, B, C, D
