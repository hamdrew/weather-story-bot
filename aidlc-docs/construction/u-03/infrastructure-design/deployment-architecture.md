# U-03 Deployment Architecture

## Controlled Staging Path

1. A read-only exact GitHub revision enters the future U-04 delivery path.
2. Locked dependencies, local checks, package inputs, SBOM, scans, and SAM validation produce
   bounded U-03 evidence tied to source and artifact identity.
3. SAM/CloudFormation uses the U-03 contract to create an isolated staging change set in `us-east-2`.
4. U-04 classifies the exact change set and pauses every staging mutation for the owner's cloud-native
   approval. Only the reviewed change set may execute; U-03 does not authorize or directly execute it.
5. After separately approved staging smoke checks, the owner may enable selected schedules through
   the controlled path. Production remains inactive.

## Runtime Delivery Flow

`Disabled Scheduler` → `Publisher Lambda` → `validated runtime assembly` → `NWS / current state /
media / public Telegram` → `safe logs and metrics` → `CloudWatch alarm` → `encrypted SNS trigger` →
`U-01 private-alert Lambda` → `independent SNS/email fallback after definitive failure`.

Protected office-information and reconciliation invocations follow their distinct IAM-protected
paths. Neither can publish stories, enable schedules, or return to the alert-trigger topic. No
runtime path can approve, create, or execute a deployment change set.

## Validation and Handoff

Code Generation must extend `template.yaml` and composition code in place, add parsed-template and
runtime contract tests, run `make validate-sam`, `make format`, `make check`, and `git diff --check`.
It must preserve local/mock-only development and make no cloud mutation. U-04 consumes only exact
template/package/evidence references; U-05 later supplies authorized staging smoke and recovery
evidence.
