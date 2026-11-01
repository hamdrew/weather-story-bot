# Requirements Analysis Questions: agent-os to AI-DLC

Context: the scan found that agent-os goes beyond the `agent-os/` folder. Comments across `src/`, `infra/`, `tests/`, `scripts/`, `mise-tasks/` and `.github/` cite its 27 standards by short name (for example `backend/side-effect-order`). Several invariants are written down only in those standards. `CLAUDE.md` builds its workflow around agent-os. The Phase 2.2 plan is half built. Some things are already settled and are not asked again here: `agent-os/` and `.claude/commands/agent-os/` are removed, Claude's private notes are already deleted, and four setup facts (the read-only AWS profile, MFA admin work, the boto3 MFA workaround, reporting times in Chicago) move into AI-DLC's project rules.

## Q1. [Product owner] Where should the 27 agent-os standards live in AI-DLC?

The standards hold the project's binding technical rules and the reasons behind them, such as the frozen story hash encoding, the side-effect order, the log-message alarm contracts, IAM shape and data retention. AI-DLC has two homes for this. Project rules (`aidlc/spaces/default/memory/project.md`) are loaded into every stage automatically, so they need to be short. Knowledge (`aidlc/spaces/default/knowledge/`) is reference material that agents read in full.

A. Both: the binding rules go into project rules as short lines, and the full text with its rationale moves into knowledge
B. Project rules only: condense every standard into project rules and drop the long-form rationale
C. Knowledge only: move the standards as they are into knowledge, with no project-rule lines
D. A `docs/standards/` folder in the repo, outside AI-DLC, with AI-DLC pointed at it
X. Other (please specify)

[Answer]: X. Delete the standards; AI-DLC goes in blind (changed from A after discussion: "yes, switch it to blind"). The load-bearing invariants are already enforced by tests, Terraform and IAM, and the code comments carry their own reasoning.

## Q2. [Product owner] What happens to the roadmap, mission, idea notes and the six specs?

`agent-os/product/` holds the mission, roadmap and tech stack. `agent-os/notes/` holds four idea notes that the roadmap cites (monitoring and digest, Year in Review, word cloud and custom model, standards review). `agent-os/specs/` holds five finished specs and the in-flight Phase 2.2 spec, where Task 5 onward is still pending.

A. Roadmap, mission and idea notes move into knowledge. All six specs are deleted (git history keeps them). Phase 2.2's remaining work becomes the next AI-DLC piece of work, planned fresh, with its spec moved into knowledge as input
B. Everything moves into knowledge as history, specs included. Phase 2.2 continues from its existing plan
C. Only the roadmap and mission move into knowledge. Notes and all specs are deleted, and Phase 2.2 is re-planned from its roadmap entry alone
D. Finish Phase 2.2 under its agent-os plan first, then migrate
X. Other (please specify)

[Answer]: A (narrowed by Q5: only the roadmap and mission move; the idea notes and the Phase 2.2 spec are dropped)

## Q3. [Product owner] How should ways of working be set from now on?

`CLAUDE.md` mandates superpowers process skills (test-driven development, code review, verification), stopping points and spec gates. You want a pure AI-DLC workflow. AI-DLC records a team's ways of working (testing approach, branching, deploy practice, code style) in `team.md` through its Practices Discovery stage, which reads the repo and asks you to affirm what it finds. That stage is not in this workflow today.

A. Remove the workflow rules from `CLAUDE.md` and add Practices Discovery to this workflow, so the practices are discovered from the repo and you affirm them
B. Remove the workflow rules from `CLAUDE.md` and run on AI-DLC's defaults (test-after, trunk-based, deploy on merge to staging with a production approval)
C. Keep the superpowers rules in `CLAUDE.md` and only swap agent-os for AI-DLC
X. Other (please specify)

[Answer]: A

## Q4. [Developer] What happens to the roughly 60 code and config comments that cite standards by short name?

Examples: `# See backend/side-effect-order` in `src/`, `infra/iam` in Terraform comments, `testing/terraform-tests` in `CLAUDE.md`. The answer depends on Q1.

A. Keep the short names. The new home keeps the same names and folder layout, so every citation still resolves, and one line in `CLAUDE.md` says where they live
B. Rewrite every citation to the full new path
C. Inline the rationale into each comment and drop the citations
D. Remove the citations and leave the code as it reads
X. Other (please specify)

[Answer]: X. Remove the citations; where a comment is only a pointer to a standard, leave a one-line reason in its place ("yes, switch it to blind")

## Q5. [Product owner] With the standards deleted, how should the docs moving into knowledge handle their references to them?

Follow-up: Q1 now deletes the standards, but the docs Q2 moves into knowledge lean on them. The roadmap cites standards 22 times. The Phase 2.2 spec cites them over 100 times, and its `standards.md` is nothing but a list of them. The note `2026-09-16-standards-review.md` exists only to review the standards. Left as written, these references point at nothing.

A. Reword: drop the standards-review note and the spec's `standards.md`; in everything else, replace standard names and agent-os paths with plain wording
B. As written: move everything chosen in Q2 unchanged, and treat the references as history
C. Trim: move only the roadmap and mission, reworded; drop the notes and the Phase 2.2 spec, and re-plan 2.2 from its roadmap entry
X. Other (please specify)

[Answer]: C

## Consolidated Summary Confirmation

- Already settled before these questions: `agent-os/` and `.claude/commands/agent-os/` are removed; Claude's private notes are already deleted; four setup facts (read-only AWS profile, MFA admin work, the boto3 MFA workaround, reporting times in Chicago) move into AI-DLC's project rules
- Standards (Q1): all 27 are deleted with no replacement; AI-DLC goes in blind, relying on the tests, Terraform and IAM that already enforce the load-bearing invariants
- Citations (Q4): the roughly 60 short-name citations are removed; where a comment is only a pointer to a standard, a one-line reason replaces it
- Docs (Q2, narrowed by Q5): only the roadmap and mission move into AI-DLC knowledge, reworded so they mention no standard or agent-os path; the tech stack, the four idea notes and all six specs (Phase 2.2's included) are deleted, and git history keeps them
- Phase 2.2 (Q2, Q5): its remaining work becomes the next AI-DLC piece of work, re-planned from its roadmap entry alone
- Ways of working (Q3): the agent-os and superpowers workflow rules leave `CLAUDE.md`, and Practices Discovery is added to this workflow so you affirm the practices it finds in the repo
- Code knowledge base (from the requested change below): the Reverse Engineering output in `aidlc/spaces/default/codekb/weather-story-bot/` also cites agent-os and its standards, so it is rebuilt by a fresh Reverse Engineering scan once the cleanup lands, and the rebuilt store mentions no agent-os path or standard
- AI-DLC's setup (Q6): the `.claude/` AI-DLC files and the `aidlc/` workspace (minus what its `.gitignore` block excludes) are committed in the same pull request as the cleanup, so the whole move is one change to revert; this becomes a confirmed requirement, not an assumption
- Review fixes carried into the requirements: the agent-os check matches every spelling (`agent[ _-]?os`, so "Agent OS" too) and covers the moved roadmap and mission; the 27 standard names are listed for the citation check, with `infra/iam.tf` named as the one expected real-path match; a before baseline (test and run counts) is recorded ahead of any edit; you run the staging plan check, since it needs your MFA session; the roadmap and mission go to `aidlc/spaces/default/knowledge/aidlc-shared/`, and the Phase 2.2 entry names #29, #30 and #31 as merged and lists the pending items; the user-level `agent-os:*` plugin skills are noted as yours to remove, outside the repo

Does this all look correct before I generate the requirements artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

## Requested Changes Feedback

What should change in the summary?

[Answer]: The prior stage, reverse engineering, also cites agentos standards

## Q6. [Developer] When does AI-DLC's own setup get committed?

Follow-up from the requirements review (its major finding on assumption A2). AI-DLC's setup is untracked today: the `.claude/` agents, protocols, stages, hooks and settings, and the `aidlc/` workspace (this workflow's record, the code knowledge base, memory and knowledge). It has to be committed to continue in AI-DLC from a fresh clone or in CI. The requirements currently assume it rides in the same pull request as the agent-os cleanup, which turns a small deletion-and-comment change into a very large one and makes "one revertible pull request" (NFR5) much harder to review.

A. Its own pull request first: commit the AI-DLC setup before the cleanup, so the cleanup pull request is only the deletion and comment sweep
B. Same pull request: commit it together with the cleanup, as one change to revert
C. Its own pull request after: land the cleanup first, then commit the AI-DLC setup
D. Not committed: AI-DLC stays local to this laptop
X. Other (please specify)

[Answer]: B
