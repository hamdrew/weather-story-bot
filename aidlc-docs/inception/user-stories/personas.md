# Weather Story Bot Personas

## Persona P-01: Telegram Subscriber

### Profile

The subscriber follows the configured Telegram channel to receive the latest visual National
Weather Service Weather Story for the active office. The subscriber may not know how the bot or
AWS deployment works and judges the service by the timeliness, clarity, and consistency of its
messages.

### Goals and Motivations

- Receive the current MKX Weather Story promptly and in an accessible photo-message format.
- See revisions reflected in the existing story message without confusing duplicates.
- Trust that captions identify the source and do not present the bot as an emergency-alerting
  service.

### Constraints and Concerns

- Telegram delivery can fail or have an ambiguous outcome.
- Captions and images are subject to Telegram and application size limits.
- The subscriber cannot reconcile publication state or diagnose operational failures.

### Trust Boundary

The subscriber receives public channel content only. The persona has no access to private alerts,
operator functions, configuration, secrets, AWS resources, or deployment controls.

### Requirement Areas

FR-02, FR-04, FR-05, FR-06, NFR-01, NFR-02, and NFR-08.

### Primary Stories

US-1.2, US-1.3, US-2.1, US-2.2, US-2.3, US-2.4, and US-4.1.

## Persona P-02: Owner/Operator/Maintainer

### Profile

The project owner is currently the sole operator and maintainer. This persona owns service
outcomes, source maintenance, environment-specific Telegram destinations, AWS delivery, cost and
security review, operational response, production approval, and recovery.

### Goals and Motivations

- Keep publication reliable without causing duplicate or cross-environment Telegram effects.
- Make small, traceable source and infrastructure changes with deterministic feedback.
- Receive bounded, actionable, private operational alerts without secret-bearing diagnostics.
- Review exact CloudFormation plans and approve production or sensitive changes with confidence.
- Recover durable history while retaining a clear audit trail and rollback boundary.

### Constraints and Concerns

- Production and sensitive infrastructure changes require deliberate human approval.
- Accepted Telegram effects cannot be rolled back by CloudFormation.
- Secrets, invite links, chat identifiers, and raw external payloads must remain private.
- Python, uv, quality, testing, security, cost, and delivery requirements remain mandatory even
  when one person performs all human roles.
- Evidence must remain tied to the exact revision, environment, artifact, and change set.

### Trust Boundary

The owner may maintain reviewed repository content, use protected operator functions and private
alerts, inspect pipeline evidence, and use AWS approval controls. Authorization remains
deny-by-default and scoped to the requested environment and object. Human responsibilities may be
held by one person, but automated build, planning, agent execution, approval, and CloudFormation
roles remain technically separated. The owner does not bypass cost, security, provenance, or
change-set gates.

### Requirement Areas

All FRs and NFRs, with sole operational and maintenance responsibility for the current project.

### Primary Stories

US-1.1 through US-1.3, US-2.3, US-3.1 through US-3.3, US-4.1 through US-4.4,
US-5.1 through US-5.3, US-6.1 through US-6.8, US-7.1 through US-7.4, and US-8.1 through US-8.2.

## Persona P-03: Contributor

### Profile

The contributor is a community participant who finds a defect or improvement opportunity in the
public GitHub repository. This persona may open a GitHub Issue or propose a Pull Request but does
not operate the service or hold AWS, Telegram, secret, approval, or deployment authority.

### Goals and Motivations

- Understand contribution expectations and current requirements without relying on retired docs.
- Report a reproducible defect or suggest a clearly motivated improvement through a GitHub Issue.
- Submit a focused Pull Request with tests and receive deterministic, safe CI feedback.
- Participate without gaining access to private identifiers, secrets, or deployment environments.

### Constraints and Concerns

- Issues and Pull Requests are proposals; the owner decides whether they enter AI-DLC scope.
- Pull Requests must follow repository conventions and include focused tests for code changes.
- Fork-originated workflows must not expose credentials or obtain AWS mutation permissions.
- The contributor cannot approve, deploy, reconcile, operate, or access private configuration.

### Trust Boundary

The contributor interacts only through public GitHub Issues and Pull Requests and public-safe CI
results. The persona receives no CodeConnections, CodeBuild, AWS, Telegram, secret, protected
operator, or deployment approval access. Untrusted fork content is treated as untrusted input.

### Requirement Areas

FR-12, FR-13, FR-14, NFR-03, NFR-06, NFR-07, and NFR-08.

### Primary Stories

US-8.3.

## Persona-to-Value Summary

| Persona                        | Primary value received                                                                        | Excluded authority                                              |
| ------------------------------ | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| P-01 Telegram Subscriber       | Timely, clear, non-duplicative Weather Story publication                                      | Operations, private data, and deployment                        |
| P-02 Owner/Operator/Maintainer | Source maintenance, safe operation, approvals, delivery, alerts, reconciliation, and recovery | Bypassing evidence or approval gates                            |
| P-03 Contributor               | Public issue/PR participation and safe CI feedback                                            | Operations, private data, AWS access, approvals, and deployment |
