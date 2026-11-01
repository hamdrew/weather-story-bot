# Deployment Execution Questions: agent-os to AI-DLC

The change reaches staging and production only by merging a pull request: a merge to `main`
deploys staging, then production after the owner approves the saved plan (`team.md`, Deployment).
There is no separate deploy command to run. Build and Test is green (`test-results.md`), the
Deployment Pipeline stage was skipped because the pipeline already exists, and the branch
`agentos-to-aidlc` is not on GitHub yet.

Pre-deployment checks already made: the read-only AWS profile sees the account (role `ReadOnly`,
account `********8552`); GitHub CLI is logged in as the repository owner; no pull request is open;
no data migration is involved (comment and doc text only); the staging plan shows only the
Lambda code hash changing.

## Q1. [release] When should the code knowledge base be rebuilt?

The code knowledge base under `aidlc/spaces/default/codekb/weather-story-bot/` still cites
agent-os and its standards (requirement FR6.1). Only a Reverse Engineering scan may rewrite it.
Nothing in the remaining plan runs that scan, so it is either run now, before the pull request, or
left for a follow-up.

A. Run the scan first, then open one pull request with the cleanup, AI-DLC's setup and the rebuilt knowledge base (Recommended: one revertible slice, as NFR5 asks)
B. Open the pull request now and rebuild the knowledge base in a second pull request (the first merge then leaves stale agent-os mentions in the codekb)
C. Do not rebuild it; leave the stale files
X. Other (please specify)

[Answer]: A

## Q2. [release] Who pushes the branch and opens the pull request?

Pushing publishes the branch on GitHub, and the workflow record (state, audit log and this stage's
files) is not committed yet, so a commit comes first. Per `team.md` the pull request title is a plain
sentence naming the slice, and its body records what changed, how it was tested, the review result,
and what to watch after merge with the rollback.

A. I commit the workflow record, push `agentos-to-aidlc`, and open the pull request with the title and body written for you; you review and merge it (Recommended)
B. I only write the title and body; you commit, push and open the pull request yourself
C. Stop at pre-deployment checks and leave the pull request for a later session
X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Looks correct
- Request changes

[Answer]: Looks correct
