# U-01 Technology Decisions

## Selected Technologies

| Area                        | Decision                                                                                 | Rationale                                                                                                                 |
| --------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Language/runtime            | Python 3.13 in the existing Lambda service                                               | Preserves the approved runtime and avoids an unapproved service split.                                                    |
| Domain validation           | Pydantic 2 typed models                                                                  | Validates bounded commands, profiles, events, results, and configuration at trust boundaries.                             |
| Application boundaries      | Existing typed protocols/ports and composition root                                      | Keeps handlers thin and prevents domain logic from constructing AWS clients or resolving secrets.                         |
| AWS integrations            | boto3-backed adapters for DynamoDB, SNS, CloudWatch, Secrets Manager, and Lambda context | Matches the existing AWS service architecture; concrete resource/IAM details remain Infrastructure Design.                |
| Observability               | Structured allowlisted application logs and CloudWatch metrics                           | Supports safe correlation and measurable outcomes without raw diagnostics.                                                |
| Property testing            | Hypothesis 6 with pytest                                                                 | Supports custom strategies, automatic shrinking, seed-based reproduction, and stateful tests in the existing test runner. |
| Example/integration testing | pytest and pytest-cov with deterministic mocked adapters                                 | Preserves network-independent critical-path coverage and the repository coverage gate.                                    |

## PBT-09 Framework Decision

Hypothesis is selected and already declared as a development dependency in `pyproject.toml` with its
resolved version in `uv.lock`. It integrates with pytest and supports all required U-01 capabilities:

- Custom structured strategies for safe operational events, office commands, timestamps, and valid
  stateful command sequences.
- Automatic shrinking without disabling the framework.
- Seed-based failure reproduction; failing examples and seed information are retained by normal
  Hypothesis/pytest output and CI logs.
- Stateful model testing for cooldown and idempotent refresh behavior.

Code Generation shall place reusable U-01 strategies in a test utility module when more than one
test uses them. Property tests must remain distinct from focused example tests and run through the
normal `make test`/`make check` gates.

## Technology Constraints

- Do not add a queue, alert microservice, second property-testing framework, raw print logging, or
  untyped unbounded event mappings.
- Do not use the technology stack to bypass dev mock-only behavior, protected-operation validation,
  cooldown/fallback policy, environment isolation, or remote-action authorization.
- Infrastructure Design must specify resource names, IAM, retention, timeouts, alarms, and concrete
  AWS configuration; Code Generation must add the required tests and no secret-bearing fixtures.

## PBT Compliance

| Rule                          | Status                   | Evidence                                                                                                                         |
| ----------------------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| PBT-09                        | Compliant                | Hypothesis is selected, declared, locked, pytest-integrated, supports custom strategies, shrinking, and seed-based reproduction. |
| PBT-01                        | Carried forward          | Six U-01 properties are specified in Functional Design and must become Code Generation test requirements.                        |
| PBT-02 through PBT-08, PBT-10 | Deferred by stage matrix | They become enforceable during Code Generation and Build and Test as applicable.                                                 |
