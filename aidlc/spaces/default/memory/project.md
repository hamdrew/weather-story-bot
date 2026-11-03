# Project-Level Rules

> Project-specific specialisation and corrections. Loaded after `org.md` and
> `team.md` as strict-additive guidance; contradictions with broader policy
> are rejected. Populated by practices-discovery and the self-learning loop.
>
> Use sparingly: most teams don't need a project layer. Reach for it
> only when this specific project needs stable, durable guidance beyond the
> team practice (for example, package-specific release checks or an additional
> regression suite for a legacy component).

## Way of Working

- ALWAYS use the `readonly` AWS profile for read-only AWS work; report a denied read to the owner instead of escalating to another profile.

- ALWAYS leave Terraform and admin AWS work to the owner's MFA profiles, which only the owner can run.

- ALWAYS give a boto3 script that runs under an MFA profile the AWS CLI's cached session.

- ALWAYS report times to the owner in America/Chicago.

## Walking Skeleton

<!-- Project-specific specialisation. Example: -->
<!-- The walking skeleton must exercise the legacy service adapter as well -->
<!-- as the new service boundary. -->

## Testing Posture

<!-- Project-specific specialisation. -->

## Guard Policy

<!-- Project-specific. Mode: strict, relaxed, or off. Strict here holds for every intent, whatever one person asks in chat; relaxed or off here applies to every intent whose policy came from its scope, unless the person sets another; changing this line changes it. A section under the retired Change Control heading, written by an earlier release, is still read. -->

## Deployment

<!-- Project-specific specialisation. -->

## Code Style

<!-- Project-specific specialisation. -->

## Tech Stack

<!-- Technology choices locked for this project. -->

## Decided

<!-- Decisions made in earlier stages that should not be re-asked. -->
<!-- Format: DECIDED: [decision] (Stage [slug], [date]) -->

## Scope Overrides

<!-- Custom scope rules for this project. -->

## Forbidden

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: NEVER [behavior] (affirmed [date]) -->
<!-- Example: NEVER throw exceptions across service layer boundaries (affirmed 2026-05-17) -->

- NEVER force-push to or delete `main`. (affirmed 2026-10-30)

- NEVER put the Telegram token in Terraform variables or state. (affirmed 2026-10-30)

- NEVER add boto3 to the runtime `dependencies`; it is dev-only because the Lambda runtime provides it. (affirmed 2026-10-30)

- NEVER grant AWS credentials (`id-token: write`) to a job that runs project tests or linters. (affirmed 2026-10-30)

- NEVER apply the bootstrap stack from the pipeline; it is applied by hand with MFA. (affirmed 2026-10-30)

- NEVER upload a saved Terraform plan as a GitHub artifact; plans hold sensitive values and the repository is public. (affirmed 2026-10-30)

- NEVER put `--cov` in pytest `addopts`. (affirmed 2026-10-30)

- NEVER silence a type error with `# ty: ignore`; fix it. (affirmed 2026-10-30)

## Mandated

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: ALWAYS [behavior] (affirmed [date]) -->
<!-- Example: ALWAYS use Result<T,E> for fallible operations in service layer (affirmed 2026-05-17) -->

- ALWAYS land a change on `main` through a pull request whose `checks` job passes. (affirmed 2026-10-30)

- ALWAYS deploy production through the pipeline, after the owner approves the saved plan; a laptop production deploy needs `BREAK_GLASS=1` on the command line. (affirmed 2026-10-30)

- ALWAYS keep the test suites offline: HTTP through respx, AWS through moto, Terraform through the mock provider, with no real credentials reachable. (affirmed 2026-10-30)

- ALWAYS give a Checkov skip or a zizmor ignore an inline reason (`#checkov:skip=<ID>:<reason>`, `# zizmor: ignore[<audit>] <reason>`). (affirmed 2026-10-30)

- ALWAYS pin a GitHub Action to a full commit SHA. (affirmed 2026-10-30)

- ALWAYS keep each environment's Telegram token in its own SSM parameter. (affirmed 2026-10-30)

- ALWAYS record a story as posted only after Telegram accepts it. (affirmed 2026-10-30)

- ALWAYS ask the owner before running `deploy`, `start`, `pause` or `bootstrap-deploy`. (affirmed 2026-10-30)

## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
- ALWAYS read the job states of a pipeline run that stops at the production approval gate (`gh run view <id> --json jobs`) and NEVER wait on it with `gh run watch`, which does not return until the approval. (learned 2026-11-01) <!-- cid:261030-agentos-to-aidlc:deployment-execution:f483c56db69bba27fdfdef7ce407aa72c494b590f477f5bb4654d8c1984d19f5 -->
- ALWAYS stop with a hard pause when a unit's pull request is ready for review and merge, and end the turn there so the owner can clear context between units; start the next unit only when the owner says that pull request is merged and its staging deploy looks right. If the owner chooses to continue before the merge, a stacked branch is fine: base it on the unmerged branch, open its pull request against that branch, merge bottom-up, and after a squash merge move the next branch with `git rebase --onto main <old tip of the merged branch>`. (learned 2026-11-02) <!-- cid:261101-observability-digest:code-generation:8c3d14219efc275a01c9987b8b2375eeb62cc7677d922dfeb104d117537eed7c -->
