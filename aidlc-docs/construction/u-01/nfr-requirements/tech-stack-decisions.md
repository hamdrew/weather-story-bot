# U-01 Technology Decisions

## Selected Technologies

| Area                        | Decision                                                                                 | Rationale                                                                                                                                      |
| --------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Language/runtime            | Python 3.13 in the existing Lambda service                                               | Preserves the approved runtime and avoids an unapproved service split.                                                                         |
| Domain validation           | Pydantic 2 typed models                                                                  | Validates bounded commands, profiles, alarm transitions, results, and configuration at trust boundaries.                                       |
| Application boundaries      | Existing typed protocols/ports and composition root                                      | Keeps handlers thin and prevents domain logic from constructing AWS clients or resolving secrets.                                              |
| AWS integrations            | boto3-backed adapters for DynamoDB, SNS, CloudWatch, Secrets Manager, and Lambda context | Matches the architecture; CloudWatch/SNS supply alarm transitions while concrete resources/IAM remain Infrastructure Design work.              |
| Observability               | Structured allowlisted logs, CloudWatch metrics, alarms, and alarm history               | Provides safe correlation, bounded evidence, and platform-managed noise reduction without custom alert state.                                  |
| Runtime secret stop-gap     | `detect-secrets` 1.5 structured plugin set                                               | Rejects credential-shaped observation/alert text before logging or delivery while excluding high-entropy/keyword plugins that over-flag prose. |
| Property testing            | Hypothesis 6 with pytest                                                                 | Supports custom strategies, automatic shrinking, seed-based reproduction, and stateful tests in the existing runner.                           |
| Example/integration testing | pytest and pytest-cov with deterministic mocked adapters                                 | Preserves network-independent critical-path coverage and the repository coverage gate.                                                         |

## PBT-09 Framework Decision

Hypothesis is selected and declared as a development dependency in `pyproject.toml`, with its
resolved version in `uv.lock`. It integrates with pytest and supports custom structured strategies,
automatic shrinking, seed-based reproduction, and stateful testing for the one-current-record refresh
model and single-notification dispatch lifecycle.

Code Generation shall centralize reusable U-01 strategies when more than one test uses them. Property
tests remain distinct from focused example tests and run through `make test` and `make check`.

## Technology Constraints

- Do not add a queue, alert microservice, second property-testing framework, raw print logging,
  untyped unbounded event mappings, or custom alert persistence.
- Do not use the stack to bypass dev mock-only behavior, protected-operation validation,
  CloudWatch-only notification triggering, environment isolation, or remote-action authorization.
- Infrastructure Design must specify resource names, IAM, retention, timeouts, alarm treatment, and
  concrete AWS configuration. Code Generation must add the required tests and no secret-bearing
  fixtures.

## PBT Compliance

| Rule                          | Status                   | Evidence                                                                                                                                                                      |
| ----------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PBT-09                        | Compliant                | Hypothesis is selected, declared, locked, pytest-integrated, and supports custom strategies, shrinking, and seed-based reproduction.                                          |
| PBT-01                        | Carried forward          | Functional Design properties for sanitizer/schema, alarm validation/rendering/lifecycle, office refresh, and Telegram entities must become Code Generation test requirements. |
| PBT-02 through PBT-08, PBT-10 | Deferred by stage matrix | They become enforceable during Code Generation and Build and Test as applicable.                                                                                              |
