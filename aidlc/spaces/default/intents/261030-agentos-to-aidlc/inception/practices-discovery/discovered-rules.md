# Discovered Rules

> Hard constraints affirmed by the owner at the practices-discovery interview (Q5: all 16 affirmed
> as written). Each rule is one line; the evidence it was found in is in `evidence.md`.

## Mandated

- ALWAYS land a change on `main` through a pull request whose `checks` job passes.
- ALWAYS deploy production through the pipeline, after the owner approves the saved plan; a laptop production deploy needs `BREAK_GLASS=1` on the command line.
- ALWAYS keep the test suites offline: HTTP through respx, AWS through moto, Terraform through the mock provider, with no real credentials reachable.
- ALWAYS give a Checkov skip or a zizmor ignore an inline reason (`#checkov:skip=<ID>:<reason>`, `# zizmor: ignore[<audit>] <reason>`).
- ALWAYS pin a GitHub Action to a full commit SHA.
- ALWAYS keep each environment's Telegram token in its own SSM parameter.
- ALWAYS record a story as posted only after Telegram accepts it.
- ALWAYS ask the owner before running `deploy`, `start`, `pause` or `bootstrap-deploy`.

## Forbidden

- NEVER force-push to or delete `main`.
- NEVER put the Telegram token in Terraform variables or state.
- NEVER add boto3 to the runtime `dependencies`; it is dev-only because the Lambda runtime provides it.
- NEVER grant AWS credentials (`id-token: write`) to a job that runs project tests or linters.
- NEVER apply the bootstrap stack from the pipeline; it is applied by hand with MFA.
- NEVER upload a saved Terraform plan as a GitHub artifact; plans hold sensitive values and the repository is public.
- NEVER put `--cov` in pytest `addopts`.
- NEVER silence a type error with `# ty: ignore`; fix it.
