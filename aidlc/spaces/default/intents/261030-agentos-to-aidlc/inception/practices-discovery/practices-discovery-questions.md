# Practices Discovery Questions

Context: these practices were discovered blind, from the repo's history, CI, tooling and tests. Nothing came from agent-os or the old `CLAUDE.md` workflow rules. The evidence already settles most of how you work: one short-lived branch and pull request per change, squash-merged into `main` behind the `checks` job; staging deploys on every merge, production only from the pipeline after you approve the saved plan; code style enforced by ruff, ty, terraform fmt, actionlint, zizmor and Checkov. The questions below cover only what the evidence can't settle.

## Q1. [Developer] Build a thin end-to-end slice first?

A walking skeleton is a minimal version that runs the whole way through, built first to prove the pieces connect before the real features go in. Nothing in the history settles whether you want one for new work.

A. Yes, for new capabilities that add a new path through the system (for example a new scheduled job or a new output channel)
B. No, deliver slice by slice without a skeleton step
C. Yes, always
X. Other (please specify)

[Answer]: A

## Q2. [Quality engineer] Do tests come before the code or after it?

Tests always land in the same squashed commit as the code, so the history can't show the order. The only explicit signal is one review finding "fixed test-first" (#27).

A. Test-driven: write a failing test first, then the code that passes it
B. Test-after: write the code, then its tests, in the same change
C. A mix: test-first for bug fixes, test-after for new code
X. Other (please specify)

[Answer]: C

## Q3. [Quality engineer] Should test coverage have a floor?

Coverage runs only when asked (`mise run coverage`, branch coverage) and has no minimum. It is kept out of the default test run so debugger breakpoints work. AI-DLC's default for feature, mvp and infra work is an 80% line-coverage floor enforced in CI.

A. Keep it opt-in with no floor
B. Adopt an 80% line-coverage floor, checked in CI by a separate coverage step
C. Adopt a floor at today's measured coverage, so it can only go up
X. Other (please specify)

[Answer]: B

## Q4. [Release engineer] Should a change go to staging before it merges?

Staging deploys automatically on every merge to `main`. Before the pipeline existed you deployed staging from the laptop, and you still did that before merging #29.

A. Yes, for every behaviour change: deploy the branch to staging from the laptop and check it before merging
B. Only when the risk shows up only against live AWS (IAM, data, new resources)
C. No: staging deploys only on merge
X. Other (please specify)

[Answer]: B

## Q5. [Release engineer] Which hard rules should AI-DLC enforce?

The draft lists 16 candidate rules in `discovered-rules.md`. Examples: every change lands through a pull request with passing checks; production deploys only through the pipeline; tests stay offline; Checkov skips carry a reason; Actions are pinned to a commit SHA; the Telegram token stays out of Terraform; a story is recorded only after Telegram accepts it; ask before `deploy`, `start`, `pause` or `bootstrap-deploy`; boto3 never becomes a runtime dependency; credentials never reach jobs that run tests. Affirmed rules are written into the project rules as ALWAYS and NEVER lines.

A. Affirm all 16 as written
B. Affirm only the ones tooling, IAM or the repo ruleset already enforce, and drop the ones that came only from `CLAUDE.md` notes
C. Affirm none: the tooling enforces them anyway
X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Settled by evidence, not asked: one short-lived branch and pull request per change, squash-merged into `main` behind the `checks` job, with plain-sentence titles; staging deploys on every merge, and production deploys only from the pipeline after you approve the saved plan (`BREAK_GLASS=1` for a laptop deploy); code style is whatever ruff, ty, terraform fmt, actionlint, zizmor and Checkov enforce
- Thin slice first (Q1): yes, for new capabilities that add a new path through the system; no skeleton step for changes to paths that already work
- Test order (Q2): a mix, test-first for bug fixes and test-after for new code
- Coverage (Q3): an 80% line-coverage floor, checked in CI by a separate coverage step (today's suite is at 99% branch coverage of `src/`); wiring that step into CI is later work, not part of this change
- Staging before merge (Q4): only when the risk shows up only against live AWS (IAM, data migrations, new resources); everything else merges, gets checked on staging, then goes to production with your approval
- Hard rules (Q5): all 16 candidates in `discovered-rules.md` are affirmed as written

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
