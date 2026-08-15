# Code Review Prompt

Review the current changes for this Weather Story Bot project. Treat the OpenSpec change artifacts as the source of truth and verify the implementation fully satisfies the relevant tasks without adding unrelated scope.

Prioritize correctness, safety, security, resilience, and maintainability. Check for:

- Contract compliance with NWS APIs, Telegram, AWS, and OpenSpec requirements.
- No secret, token, private identifier, raw payload, or sensitive operational data exposure in code, logs, tests, docs, outputs, or errors.
- Correct validation, error handling, retry and defer behavior, state transitions, idempotency, and duplicate-publication protection.
- Strict environment isolation: dev is mock-only; staging and prod use distinct credentials and destinations.
- Least-privilege AWS design and safe handling of durable DynamoDB and S3 history.
- Deterministic behavior, Unicode-safe Telegram formatting, and appropriate limits on external data, retries, media, logging, and alerts.
- Adequate tests for expected behavior and failure cases.
- The generated coverage reports in `coverage/`, including the HTML report,
  LCOV data, Cobertura XML, and JSON output. Look for important untested lines
  and branches, especially validation failures, security boundaries, retries,
  partial or ambiguous external outcomes, persistence failures, and recovery
  paths. Assess coverage by risk and behavior rather than automatically aiming
  for 100 percent; do not flag low-value defensive or unreachable code solely
  because it is uncovered.

Report only actionable findings, ordered by severity. For each finding, include severity, explanation, concrete impact, and file and line reference. If no issues are found, state that clearly and list any residual risks or untested assumptions.
