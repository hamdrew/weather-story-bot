# Intent Statement: Wisconsin Office Coverage

## Problem Statement

The bot posts Weather Stories for one NWS office today. Coverage should grow to every NWS office covering Wisconsin counties: GRB, ARX, MPX and DLH, alongside the existing MKX. [desc]

Two needs drive it. Weather Stories for the other places the owner and people close to them care about are not delivered, so they have to visit the NWS site for them. Full Wisconsin coverage is also a step toward a wider public audience later. [Q1]

## Target Customer

- The channels are public from day one: anyone who finds a channel is a reader. [Q2]
- Each channel's name, photo and pinned office-information message is written for strangers. It says clearly that the feed is unofficial, carries no NWS or NOAA logos or seal, links to the source, and says what the office covers. [Q7] [desc]
- The owner is also a reader, and the person who runs and pays for the bot. [Q1] [Q8]

## Success Metrics

| Metric | Pass when | Source |
|--------|-----------|--------|
| Correct routing | Each of GRB, ARX, MPX and DLH posts its new Weather Stories to its own production channel, and no story is posted to another office's channel | [Q3] [desc] |
| Reader freshness | A new story for each office appears in its channel within the same window as MKX stories appear today | [Q11] [Q2] |
| Multi-office staging | The staging channel carries both MKX and MPX stories, and each post shows which office it came from | [Q3] [desc] |
| One-command setup | Setting up a channel (creating it, its name, photo, description, pinned message and directory entry) takes one command instead of a list of hand steps | [Q3] [Q6] [desc] |
| Cost ceiling | Monthly AWS spend stays at or under $20, checked against cost estimates produced as part of the work; the first estimate establishes today's monthly spend so the headroom is known | [Q3] [Q5] [Q11] [desc] |
| Alarm coverage | An induced failure for one new office trips a general alarm | [Q9] [Q11] |

## Initiative Trigger

This is the next phase on the roadmap, and the per-office groundwork it builds on has already landed. [Q4]

## Initial Scope Signal

- Workflow-selected scope: `feature` (workflow-selected). [scope]

### What this first version does (user-confirmed product boundary)

- Adds GRB, ARX, MPX and DLH, each with a single production Telegram channel. [desc]
- Adds MPX to the existing staging channel to test multi-office behaviour without cluttering it, and renames that channel so it is no longer MKX-specific. [desc]
- Generates an avatar for each channel and adds a pinned message with office information. [desc]
- Automates channel provisioning end to end, including creating the channel through a script that signs in as the owner's Telegram user account. [Q6] [desc]
- Keeps an internal directory of channels, stored persistently, to keep track of them (a record for the owner and the bot, not a public listing). [desc]
- Reworks the alarms where that helps, so a problem in any office, new ones included, is caught reliably and the office it came from is easy to identify. The mechanism is left to design. [Q9] [Q11]
- Adds the channels' links to the README. [Q10]

### What this first version leaves out (user-confirmed)

- Offices beyond these five. [Q9]
- Any publishing beyond the README links: no public channel directories or catalogs, forums or other promotion. [Q9] [Q10]
- Per-office alerts; the alarms stay general. [Q9]
- Changes to how stories are detected, decided and posted beyond what multiple offices need. [Q9]

### Still to decide before channel creation is built

- Open decision: the risk to the owner's personal Telegram account from automating it (rate limits, account restrictions, a cap on public channels per account) has not been assessed. It must be assessed and decided before channel creation is built. [Q11] [Q6]

## Assumptions & Open Questions

- [assumption] How the Telegram user-account login used for channel creation is stored and protected is not decided yet. The project rules cover the bot token only: it never goes in Terraform variables or state [memory:M1], and each environment keeps it in its own SSM parameter [memory:M2]. The user-account session is a far more powerful credential than a bot token and needs its own decision in a later stage.
- [assumption] The $20 limit is read as the account's total monthly AWS spend, not $20 on top of today's spend.
