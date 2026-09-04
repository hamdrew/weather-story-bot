# U-01 Deployment Architecture

1. A read-only exact GitHub revision passes local validation, packaging, SBOM/scanning, and evidence
   generation in the governed delivery control plane.
2. SAM/CloudFormation creates an exact isolated staging change set in `us-east-2`.
3. Every staging change pauses for explicit owner approval; only that exact approved change set can
   execute. Build, agent, and runtime roles cannot approve or directly mutate resources.
4. CloudFormation maps roles, functions, subscriptions, alarms, dashboard, log retention, secret
   references, and DynamoDB grants. Failed/mismatched plans fail closed.

`Authorized operator` → `Office Lambda` → `NWS/Telegram/current record` → `safe metrics/logs` →
`CloudWatch alarm` → `SNS trigger` → `Alert Lambda` → `private Telegram` → `SNS/email fallback only
after definitive failure`.

No edge returns to the trigger topic. No custom alert-state store, queue, public API, or public
notification path is provisioned. `sam validate` plus deterministic mocked unit/property tests are
required before any separately authorized staging action.
