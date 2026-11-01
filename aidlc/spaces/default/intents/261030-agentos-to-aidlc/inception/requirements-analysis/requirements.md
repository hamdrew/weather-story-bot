# Requirements: agent-os to AI-DLC

## Intent Analysis

- **Goal:** remove agent-os from weather-story-bot completely and keep working in a pure AI-DLC workflow, with AI-DLC going in blind rather than inheriting agent-os's standards or ways of working [desc] [Q1] [Q3].
- **Type:** migration of planning tooling and documentation. The bot's runtime behaviour, infrastructure and alarms do not change.
- **Scope:** system-wide but shallow. About 60 comment and doc lines across 34 tracked files cite agent-os or its standards, plus the `agent-os/` folder, `.claude/commands/agent-os/`, `CLAUDE.md` and the code knowledge base (`aidlc/spaces/default/codekb/weather-story-bot/code-quality-assessment.md`, "Agent OS Coupling").
- **Complexity:** simple. The risk is collateral: a comment sweep that touches an alarm-contract log string, a Checkov skip reason, or a test.

## Functional Requirements

### FR1 Remove agent-os

- **FR1.1** The whole `agent-os/` folder is deleted: `product/`, `notes/`, `specs/` and `standards/` [desc]. The roadmap and mission are carried over first (FR3). Pass: `git ls-files agent-os` prints nothing.
- **FR1.2** agent-os's own slash commands in `.claude/commands/agent-os/` (`discover-standards`, `index-standards`, `inject-standards`, `plan-product`, `shape-spec`) are deleted [desc]. Pass: `git ls-files .claude/commands/agent-os` prints nothing.
- **FR1.3** No tracked file outside this workflow's own record mentions agent-os, in any spelling ("agent-os", "agentos", "agent_os", "Agent OS"). That includes the moved roadmap and mission under `aidlc/spaces/default/knowledge/` and AI-DLC's committed setup (FR8). Pass: `git grep -n -I -i -E 'agent[ _-]?os' -- ':!aidlc/spaces/default/intents'` prints nothing once FR6 is done. Before FR6, the same check with `':!aidlc/spaces/default/codekb'` added prints nothing. The `aidlc/spaces/default/intents` exclusion is deliberate: this workflow's record documents the removal, so it names agent-os by design. `inception/practices-discovery/team-practices.md` sits inside that record. What FR7.2 governs is what reaches `team.md` and `project.md`, which this check does cover.

### FR2 Delete the standards and their citations

- **FR2.1** The 27 standards and `index.yml` are deleted with no replacement. Nothing reproduces them in AI-DLC's project rules, its knowledge, a `docs/` folder, or anywhere else [Q1].
- **FR2.2** Every citation of a standard by short name is removed, for example `backend/side-effect-order`, `infra/iam` or `testing/terraform-tests` [Q4]. That covers about 70 lines in `src/`, `scripts/`, `tests/`, `infra/` (main and bootstrap stacks and both test folders), `mise-tasks/`, `mise.toml`, `.github/`, `README.md` and `CLAUDE.md`. The 27 short names are:
  - `backend/`: `archive-layout`, `cli`, `client-errors`, `dynamodb-schema`, `env-config`, `injected-clients`, `retries`, `run-outcomes`, `secrets-in-errors`, `side-effect-order`, `story-identity`, `structured-logging`, `untrusted-nws-data`
  - `global/`: `launch-configs`, `principles`, `tooling`
  - `infra/`: `alarms`, `budget`, `data-retention`, `environments`, `iam`, `pipeline`
  - `testing/`: `handler-tests`, `log-contracts`, `offline-tests`, `terraform-tests`, `test-data`

  Pass: `git grep -n -I -E '(backend/(archive-layout|cli|client-errors|dynamodb-schema|env-config|injected-clients|retries|run-outcomes|secrets-in-errors|side-effect-order|story-identity|structured-logging|untrusted-nws-data)|global/(launch-configs|principles|tooling)|infra/(alarms|budget|data-retention|environments|iam|pipeline)|testing/(handler-tests|log-contracts|offline-tests|terraform-tests|test-data))' -- ':!aidlc' ':!.claude'` prints only lines naming a real file, and today that is one line: `infra/bootstrap/apply.tf`'s "mirroring infra/iam.tf's role" (the file `infra/iam.tf`). A match is a false positive only when it names a file that exists in the repo; every other match is a missed citation.
- **FR2.3** A comment that is only a pointer to a standard is replaced by a one-line reason in plain words. An example is `src/weather_story_bot/planner.py:4`: "See `agent-os/standards/global/principles.md`." A comment that already explains itself just loses its citation [Q4]. Pass: no comment is left empty or reduced to a dangling "see".
- **FR2.4** Every Checkov skip and zizmor ignore that cited a standard keeps a non-empty reason once the citation is gone. Six Checkov skips do this today, in `infra/lambda.tf` and `infra/storage.tf`. Pass: `mise run scan` and `mise run lint` pass.

### FR3 Move the roadmap and mission into AI-DLC knowledge

- **FR3.1** `agent-os/product/roadmap.md` and `agent-os/product/mission.md` move to `aidlc/spaces/default/knowledge/aidlc-shared/roadmap.md` and `aidlc/spaces/default/knowledge/aidlc-shared/mission.md`, the folder every AI-DLC agent reads, so later stages see the product direction [Q2] [Q5]. They are reworded so they mention no standard, no agent-os path, no spec folder and no idea note. Pass: both files exist, and the FR1.3 and FR2.2 checks run over them, plus `git grep -n -i -E 'specs/|notes/|idea note' -- aidlc/spaces/default/knowledge/aidlc-shared`, print nothing.
- **FR3.2** The rewording keeps the product content: every phase, its status, its settled decisions and its open items. The Phase 2.2 entry states what is already merged and what remains, so the next piece of work can be planned from that entry alone [Q2] [Q5]. Pass: every phase heading in the old roadmap has a matching heading in the new one with the same status. The Phase 2.2 entry has a "Merged" list naming atomic post recording (#29), the bootstrap for per-office schedules and the `misconfigured` alarm (#30), and generalized office test fixtures (#31). It also has a "Remaining" list with one item for each unfinished task in the Phase 2.2 plan (Task 5 onward), taken from that plan before it is deleted.
- **FR3.3** Nothing else from `agent-os/` is carried over. The tech stack, the four idea notes and all six specs, Phase 2.2's included, are deleted, and git history keeps them [Q5].

### FR4 Re-home four setup facts in AI-DLC project rules

- **FR4.1** `aidlc/spaces/default/memory/project.md` gains the four setup facts recorded in this workflow's change request of 2026-10-30T03:28:15Z [memory:M1]:
  - read-only AWS work uses the `readonly` profile, and a denied read is reported, not escalated;
  - Terraform and admin work run through MFA profiles that only the user can run;
  - boto3 scripts under MFA get the CLI's cached session;
  - times are reported to the user in America/Chicago.
  Pass: each fact appears as a rule line under a fitting heading.
- **FR4.2** Nothing else from Claude's deleted private notes is re-created anywhere [memory:M1].

### FR5 Rewrite `CLAUDE.md` for a pure AI-DLC workflow

- **FR5.1** The root `CLAUDE.md` loses the following [Q3]:
  - the line "Specs and roadmap are in `agent-os/`";
  - the Standards section;
  - the Skills section: agent-os planning, the superpowers process skills, stopping points, and "agent-os rules win";
  - every standard citation in Commands and Gotchas.
- **FR5.2** It keeps the project facts: the Commands, the Docs (Context7 library IDs) and the Gotchas. It names AI-DLC (`/aidlc`) as the workflow and says where the roadmap now lives. Pass: `git grep -n -i -E 'agent[ _-]?os|superpowers|brainstorming|writing-plans|executing-plans|subagent-driven-development|dispatching-parallel-agents|test-driven-development|systematic-debugging|verification-before-completion|requesting-code-review' -- CLAUDE.md .claude/commands` prints nothing, and every command `CLAUDE.md` lists still exists in `mise.toml` or `mise-tasks/`. NFR4 uses the same check.

### FR6 Rebuild the code knowledge base

- **FR6.1** Once the cleanup has passed Build and Test, a fresh Reverse Engineering scan rebuilds `aidlc/spaces/default/codekb/weather-story-bot/`, because its current files cite agent-os and its standards [summary change]. Pass: none of the nine rebuilt files mentions agent-os or a standard short name.

### FR7 Add Practices Discovery

- **FR7.1** Practices Discovery is added to this workflow. It is skipped in the refactor plan today. The project's ways of working (testing approach, branching, deploy practice, code style) are discovered from the repo and recorded in `aidlc/spaces/default/memory/team.md` only as the user affirms them [Q3]. Pass: the stage runs and the user approves its gate.
- **FR7.2** No process rule from agent-os, the superpowers skills or Claude's deleted notes reaches `team.md` or `project.md` except through what the user affirms at that stage or the four facts in FR4 [Q3] [memory:M1].

### FR8 Commit AI-DLC's setup with the cleanup

- **FR8.1** AI-DLC's setup lands in the same pull request as the cleanup [Q6]. That covers:
  - its `.claude/` files (`CLAUDE.md`, agents, `aidlc-common/`, skills, scopes, sensors, knowledge, tools, hooks, `settings.json`, `rules/`);
  - the `aidlc/` workspace, minus every path its `.gitignore` block excludes (per-user cursors, clone id, sessions, `.aidlc-engine/` state, runtime graphs);
  - the root `.gitignore` with its AI-DLC block;
  - `.mcp.json`, which declares the MCP servers and holds no key (Context7's key comes from `${CONTEXT7_API_KEY}` in the environment);
  - `aidlc.settings.json`.

  That lets work continue in AI-DLC from a fresh clone or in CI. Pass: on the pull request branch, a whole-tree `git status --porcelain` prints nothing; `git ls-files aidlc/spaces/default/intents/active-intent aidlc/active-space aidlc/.aidlc-clone-id aidlc/.aidlc-sessions` prints nothing; no tracked path contains `.aidlc-engine/`; and `git grep -n -E '"[A-Za-z0-9_]*(KEY|TOKEN|SECRET)[A-Za-z0-9_]*": *"[^$]' -- .mcp.json aidlc.settings.json` prints nothing.

## Non-Functional Requirements

- **NFR1 Behaviour preserved.** `mise run lint ::: test ::: tftest ::: scan` passes before the change and after it, with the same number of tests and test runs: none deleted, skipped or weakened. The before result is captured on the unchanged tree, before any edit, and records the pytest passed, failed and skipped counts, the `terraform test` run count for `infra/tests/` and for `infra/bootstrap/tests/`, and whether lint and scan passed. Pass: the after result matches those numbers.
- **NFR2 Alarm contracts untouched.** The log messages "Telegram message sent" and "Ambiguous stories from NWS", and the metric filters in `infra/monitoring.tf` that count them, are byte-for-byte unchanged. Pass: `git diff` shows no change to either string, and the tests asserting them pass.
- **NFR3 No infrastructure change beyond new code bytes.** `mise run plan staging` shows no change except the Lambda function's code, whose zip hash changes because comments in `src/` change. The owner runs this plan, because it needs their MFA session. Pass: the plan lists no other resource change.
- **NFR4 Nothing steers the work from outside AI-DLC.** After this work, no instruction file in the repo that Claude loads for this project sends work through agent-os or a superpowers process skill. Pass: the FR5.2 grep over `CLAUDE.md` and `.claude/commands/` finds nothing.
- **NFR5 Reversible.** Everything deleted remains in git history at commit `657c6f0`. The change lands as one revertible pull request: the agent-os cleanup and AI-DLC's setup (FR8) together [Q6]. A rollback is a revert of that one squashed commit, which restores agent-os and removes AI-DLC's committed setup in the same step.

## Constraints

- The refactor plan adds no new-test floor, and the existing suite stays green (NFR1).
- Checkov skips must keep a reason, or `mise run scan` fails (FR2.4).
- Nothing is committed until the user says yes.
- Production deploys go through the pipeline: a merge to `main` deploys staging, then production after the user approves. A laptop production deploy needs `BREAK_GLASS=1`. `deploy`, `start`, `pause` and `bootstrap-deploy` need the user's MFA, and only the user runs them.
- The code knowledge base is written only by a Reverse Engineering scan, never by hand (FR6).

## Assumptions

- **A3** The comment-only edits in `src/` change the Lambda zip's bytes, so merging deploys a new, behaviour-identical zip to staging and then production [assumption]. Reason: the build is content-addressed.
- **A4** Practices Discovery is added at this stage's approval and runs before Functional Design [assumption].
- **A5** The knowledge-base rebuild (FR6) runs as a single Reverse Engineering scan after Build and Test, inside this workflow [assumption].

## Out of Scope

- Planning or building Phase 2.2's remaining work. That is the next AI-DLC piece of work, planned from the roadmap entry (FR3.2).
- Any change to runtime behaviour, infrastructure, alarms or tests beyond comment text. One exception: the text of the two `error_message` strings in `infra/tests/iam.tftest.hcl` (lines 98 and 163) that cite `infra/iam` is reworded under FR2.2. Their assertion conditions stay byte-for-byte the same.
- User-level settings outside the repo: `~/.claude/CLAUDE.md` and installed plugins. That includes the agent-os plugin, whose `agent-os:*` skills (`discover-standards`, `index-standards`, `inject-standards`, `plan-product`, `shape-spec`) still appear in Claude's skill list after this change. The owner uninstalls it on their side to finish removing agent-os.
- Re-creating the standards in any form.

## Open Questions

- **OQ1** The superpowers plugin is installed at user level, outside this repo, and announces its process skills at the start of every session. For a pure AI-DLC workflow, the user may want to turn it off for this project. The same holds for the user-level agent-os plugin (see Out of Scope). Both are user settings, not part of this change.

## Sources

- [desc] Initial description: "See roadmap.md for this project's description. I have been implementing it with agentos but want to switch to aidlc.  agentos should be completely removed from the project and we should continue working within aidlc."
- [Q1]–[Q6] Answers in `requirements-analysis-questions.md`. Q1 and Q4 were changed to the blind option after discussion, Q2 was narrowed by Q5, and Q6 confirmed that AI-DLC's setup is committed in the same pull request.
- [summary change] The user's change at the summary confirmation: "The prior stage, reverse engineering, also cites agentos standards".
- [memory:M1] This workflow's change request of 2026-10-30T03:28:15Z, which deleted Claude's private notes and listed the four setup facts to re-home.
- Code knowledge base: `aidlc/spaces/default/codekb/weather-story-bot/business-overview.md`, `architecture.md`, `code-structure.md` and `code-quality-assessment.md` ("Agent OS Coupling").
