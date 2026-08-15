## Purpose

Provide a repeatable AWS deployment for the multi-office-ready Weather Story bot, its durable story/image history, and monitoring without requiring manually created infrastructure.

## ADDED Requirements

### Requirement: Provision service infrastructure with AWS SAM
The system SHALL define all AWS resources required to run the Weather Story bot, retain its story and image history, and monitor failures in an AWS SAM template that deploys through CloudFormation.

#### Scenario: New environment deployment
- **WHEN** an operator deploys the AWS SAM application with required environment settings
- **THEN** AWS provisions the scheduled processing service, durable story/image history store, and monitoring resources needed by the bot

### Requirement: Build reproducible Lambda artifacts
The deployment SHALL use the managed `python3.13` Lambda runtime on `arm64` for every Python Lambda. Application dependencies SHALL be declared in the project package manifest and resolved into a committed `uv.lock` file; deployment SHALL use the pinned `uv` version with `uv sync --locked` and SHALL fail if the lock is stale or dependency resolution changes. The `uv` version, Python toolchain version, and lockfile SHALL be reviewed as supply-chain inputs.

SAM builds SHALL run with `--use-container` using the matching Python 3.13 arm64 SAM build image pinned by immutable image digest, not a floating tag. The build container SHALL use a pinned `uv` executable and `uv sync --locked` to install the production dependency set. The publisher's JPEG/PNG validation SHALL use the pinned Pillow dependency packaged inside the Lambda ZIP artifact from that build; it SHALL not rely on host-installed native libraries, ad hoc binaries, an unpinned Lambda layer, or an unreviewed container image. The build SHALL verify that native wheels and imports execute under the same Python/runtime/architecture combination used by Lambda.

CI SHALL generate a machine-readable SBOM from the resolved artifact and run dependency vulnerability and license scans against the lockfile and packaged artifact. The deployment pipeline SHALL fail on configured unacceptable vulnerability or license findings and SHALL retain the SBOM and scan results with the release/change-set evidence.

#### Scenario: A dependency lock is stale
- **WHEN** the build detects that `uv.lock` is stale, missing, or would change under `uv sync --locked`
- **THEN** the build fails before packaging or deployment

#### Scenario: Native image validation is packaged
- **WHEN** the Lambda artifact is built in CI
- **THEN** Pillow and its compatible arm64 native components are included in the ZIP, import successfully in the pinned SAM build image, and do not depend on the developer workstation

#### Scenario: A dependency scan fails
- **WHEN** SBOM or vulnerability/license scanning reports a configured blocking finding
- **THEN** the release cannot proceed to CloudFormation change-set execution until the finding is remediated or formally approved under the documented exception process

### Requirement: Provision the on-demand office-info manager
The deployment SHALL provision a separate protected office-info Lambda with no Scheduler trigger. It SHALL be invocable only by authorized operators through the documented on-demand path, use the exact environment-specific Telegram secret at `AWSCURRENT`, query NWS office and region data, create or reuse the configured channel invite link, create or edit and pin the one managed office-information message, and persist its message/invite references in the environment's office record. It SHALL have no permission to publish Weather Stories, create publication attempts, or access unrelated environments. Dev SHALL use mock Telegram operations; staging and prod SHALL use their dedicated real channels. The Lambda SHALL not log or expose invite links or bot tokens.

#### Scenario: The office-info manager is deployed
- **WHEN** an environment stack is deployed
- **THEN** the separate office-info Lambda and least-privilege role exist without an automatic schedule, and its operator invocation path is protected

#### Scenario: The office-info manager fails
- **WHEN** required NWS data, invite-link management, message update, or pin verification fails
- **THEN** the deployment emits the existing operational alert and the office schedule remains disabled until a successful pin verification

### Requirement: Isolate deployment environments and control promotion
The deployment SHALL support exactly `dev`, `staging`, and `prod` environment values in AWS region `us-east-2` within one AWS account and derive a unique CloudFormation stack name and resource names from the application name and environment (for example, `weather-story-bot-dev`). Every resource SHALL carry mandatory `Application`, `Environment`, and `Owner` tags, with `Owner` set to the single service owner, Andrew Hoffmann (`@hamdrew`). Each environment SHALL have separate DynamoDB, S3, CloudWatch, SNS, IAM, Scheduler, and Lambda resources; exact environment-specific Secrets Manager secret ARN; and non-overlapping Telegram channel and private-alert recipient configuration. No environment may reference another environment's table, bucket, secret, channel, or alert recipient.

Dev SHALL use mock Telegram delivery for every send, edit, and private-alert operation and SHALL make no Telegram message API call. It MAY use its own exact secret only for the protected `getMe` credential check. Staging SHALL use its own bot secret and send real messages only to its dedicated test channel and private alert recipient. Prod SHALL use only its own bot secret, production channel, and private alert recipient.

The template SHALL validate non-secret deployment parameters, including the enumerated environment, exact environment-specific secret ARN, deployment mode, and active-office configuration; it SHALL reject empty, malformed, cross-environment, or secret-value parameters and SHALL not expose secrets in parameters, change sets, logs, or outputs. Every staging and prod deployment SHALL first create and review a CloudFormation change set. Dev and staging promotion MAY be automated after the change-set checks; prod execution SHALL require a human approval after its change-set review. The deployment role SHALL have authority only for the selected environment's stack and tagged resources.

The deployment SHALL configure one account-level application budget covering resources tagged with this application, with a monthly limit of `$100`. Budget notifications SHALL occur at 80% forecasted spend, 100% actual spend, and 120% actual spend; the 120% notification SHALL escalate to the owner without automatically deleting or disabling resources. Monthly budget review SHALL verify attribution by the required tags.

Schedules SHALL be `DISABLED` whenever created or updated. The deployment runbook SHALL require successful environment-specific smoke checks before an authorized operator enables them: mocked delivery in dev, a real dedicated-test-channel photo delivery in staging, and non-publishing configuration/authentication checks in prod. No production scheduler may be enabled until its production-only resource and configuration isolation has been verified. The system SHALL perform and record drift detection at least monthly and before every prod deployment; unresolved drift SHALL block promotion.

CloudFormation SHALL use normal rollback behavior for failed create or update operations. Stateful DynamoDB and S3 resources SHALL have retain-on-delete and retain-on-replacement protections. A CloudFormation rollback, scheduler disablement, or function-version rollback SHALL not claim to retract an already accepted Telegram send or edit; operators SHALL use durable attempt history to assess partial external effects, keep schedules disabled, and either roll forward or invoke the existing reconciliation/recovery process before re-enabling.

#### Scenario: A staging deployment is promoted
- **WHEN** a reviewed staging change set is executed
- **THEN** it can affect only staging-named/tagged resources and its dedicated Telegram test configuration, and its schedules remain disabled until staging smoke checks succeed

#### Scenario: A production deployment is proposed
- **WHEN** a production deployment is prepared
- **THEN** a valid prod-only parameter set and reviewed change set are required, unresolved drift blocks execution, and a human approval is required before the change set is executed

#### Scenario: A deployment fails after an external send
- **WHEN** CloudFormation rolls back after a publisher invocation may already have sent or edited a Telegram message
- **THEN** the rollback does not represent the message as undone, schedules remain disabled, and the operator uses durable attempt history and the established reconciliation or recovery procedure before re-enabling

### Requirement: Verify deployed integration and control-plane behavior
The deployment verification plan SHALL use an ephemeral, uniquely named `dev` CloudFormation stack for real AWS control-plane tests. The stack SHALL use dev-only tables, buckets, topics, roles, schedules, and mock Telegram delivery; it SHALL never publish a Telegram message. Verification SHALL exercise SAM build and validation, create and review a change set, create/update the stack, invoke a deployed Scheduler target, verify Scheduler retry and maximum-event-age behavior, exercise S3 staging upload/orphan reconciliation/object retrieval, verify SNS subscription confirmation and fallback delivery, and exercise CloudFormation rollback and drift detection. The test SHALL destroy the ephemeral stack and record evidence after completion; failures SHALL block the deployment pipeline.

#### Scenario: A deployed integration test runs
- **WHEN** CI creates the ephemeral dev stack and runs its control-plane suite
- **THEN** the suite verifies the deployed service behavior and AWS resource policies without using staging or production resources or sending a Telegram message

#### Scenario: A control-plane test fails
- **WHEN** change-set, deployment, Scheduler, S3, SNS, rollback, or drift verification fails
- **THEN** the release is blocked and the ephemeral stack is retained only long enough to collect bounded diagnostic evidence before cleanup

### Requirement: Secure and retain the image bucket
The image bucket SHALL enable all S3 Block Public Access settings, `BucketOwnerEnforced` object ownership, and S3 Versioning. Its bucket policy SHALL deny any request where `aws:SecureTransport` is `false`, SHALL not permit public read or write access, and SHALL not expose bucket or object URLs as public deployment outputs. The bucket SHALL use SSE-S3 encryption; object ACLs SHALL not be used. Lambda IAM roles SHALL be restricted to the required bucket prefixes and actions.

The lifecycle configuration SHALL never expire current retained image objects. It SHALL transition retained images to S3 Glacier Instant Retrieval after 365 days and to S3 Glacier Deep Archive after 730 days. It SHALL expire noncurrent object versions after 30 days and expire uncommitted `staging/` objects after 7 days. Restoring an archived retained object is an explicit operator action; the publisher SHALL not treat an archived object as immediately usable.

#### Scenario: Bucket access is attempted without TLS
- **WHEN** a principal attempts to access the image bucket without secure transport
- **THEN** the bucket policy denies the request

#### Scenario: A retained image becomes old
- **WHEN** a current retained image reaches 365 days and later 730 days of age
- **THEN** S3 transitions it to Glacier Instant Retrieval and then Glacier Deep Archive without expiring it

#### Scenario: A staging upload is not committed
- **WHEN** an object remains under the `staging/` prefix without a committed retained reference for 7 days
- **THEN** lifecycle management expires the staging object

### Requirement: Provision same-Region history recovery controls
The deployment SHALL enable DynamoDB point-in-time recovery with `RecoveryPeriodInDays` set to 35 and configure AWS Backup to create one monthly DynamoDB backup retained for one year. The deployment SHALL preserve S3 Versioning for the image bucket and SHALL NOT configure cross-Region replication for MVP. Runtime roles SHALL not delete committed history or retained image objects; the documented deployment/operator recovery authority SHALL perform only authorized recovery and permanent-purge procedures.

The recovery runbook SHALL restore DynamoDB only to a new isolated table, reapply required IAM policies, tags, TTL, PITR, alarms, and other non-data configuration before a controlled cutover, and verify sampled history against retained S3 image versions and checksums. It SHALL disable schedules before a production recovery cutover, retain the source table until validation completes, and document rollback to the source table. The system SHALL perform and record this same-Region restore exercise quarterly.

#### Scenario: Recovery controls are deployed
- **WHEN** the AWS SAM application is deployed
- **THEN** the history table has a 35-day PITR window, monthly one-year backup policy, and the image bucket has versioning without cross-Region replication

#### Scenario: Production history is restored
- **WHEN** an operator performs a production history recovery
- **THEN** the runbook restores to a new table, verifies it before cutover, and does not direct runtime traffic to the restored table until its required configuration is reapplied

### Requirement: Run one office invocation every fifteen minutes
The deployment SHALL configure one SAM `ScheduleV2`/EventBridge Scheduler schedule per active office. Each schedule SHALL invoke the publisher Lambda every 15 minutes using UTC, `FlexibleTimeWindow: OFF`, an explicit Scheduler execution role, `MaximumRetryAttempts: 0`, a maximum event age of 60 seconds, and an input payload containing exactly that active `office_id`. One publisher invocation SHALL process only its supplied office ID and SHALL NOT batch offices.

#### Scenario: Polling schedule is deployed
- **WHEN** the AWS SAM application is deployed
- **THEN** each active office has one Scheduler target that invokes the publisher at a 15-minute UTC rate with that office ID as input, flexible windows disabled, and the specified retry/age policy

#### Scenario: Scheduler invocation fails
- **WHEN** an asynchronous poller invocation fails or times out
- **THEN** EventBridge Scheduler does not automatically invoke that same scheduled event again, and the next 15-minute poll handles recovery subject to the DynamoDB reservation state machine

### Requirement: Isolate scheduler retries from publication retries
The deployment SHALL not use Scheduler-level retries as a substitute for publication retries. Permitted in-run Telegram retries SHALL use new reservations under the bounded publication retry policy; work deferred for time or capacity SHALL be reconsidered on a later scheduled poll. Ambiguous attempts SHALL remain non-retryable until operator reconciliation.

#### Scenario: Lambda times out after an uncertain Telegram outcome
- **WHEN** the poller times out after Telegram may have accepted a message
- **THEN** the next run's stale `send_started` recovery records an `ambiguous` transition, no Scheduler retry sends the story again, and monitoring alerts the operator

### Requirement: Bound poller execution and preserve partial-run outcomes
The SAM poller Lambda SHALL set `Timeout` to 900 seconds and `MemorySize` to 1024 MB, with memory tuning based on production duration and maximum-memory metrics. It SHALL use a 14-minute processing deadline and reserve the final 60 seconds for durable outcome writes and shutdown. It SHALL apply deadlines of 10 seconds for each NWS collection or Telegram request, 20 seconds for an image download, and 15 seconds for S3 upload plus verification. One invocation SHALL select at most 25 eligible story revisions, ordered by source `priority` and then `order`.

Before beginning collection, story revision, or retry, the poller SHALL check the remaining processing time. It SHALL retrieve its one active office's complete collection before selecting that office's stories for work. If capacity or remaining time prevents work from starting, it SHALL persist a `deferred` run outcome with reason `story_cap` or `run_budget`; a later invocation for that office SHALL re-fetch the source collection and make a new deduplication/reservation decision. A run is `success` only when its office collection succeeds and every selected eligible revision reaches a successful or explicitly skipped terminal outcome with no unresolved required work. A run with only controlled deferrals for unstarted work is `success_with_deferred` and emits a metric without an operator alert. A valid collection that quarantines malformed items while processing its valid selected items is `success_with_quarantined_items`, emits a metric and deduplicated operational error alert, and returns Lambda success. Collection failure, required-outcome persistence failure, or any selected required revision ending rejected, ambiguous, or image-invalid without approved terminal handling makes that office's run `failed`; the handler returns normally after persisting that failed result unless persistence itself fails.

#### Scenario: Story work reaches the invocation cap
- **WHEN** more than 25 eligible story revisions are available after collections are retrieved
- **THEN** the poller selects the highest-priority revisions in source order, records `story_cap` deferrals for the remainder, and completes as `success_with_deferred` unless another failure occurs

#### Scenario: Time remaining is insufficient
- **WHEN** beginning additional office or story work could consume the 60-second shutdown reserve
- **THEN** the poller does not start that work, records a `run_budget` deferral, and a later scheduled poll re-fetches and reconsiders it

#### Scenario: An office collection fails
- **WHEN** an active office's NWS collection request fails or exceeds its deadline
- **THEN** the poller records the office failure, marks the run `failed`, and triggers the private operator alert workflow

### Requirement: Secure runtime configuration
The system SHALL obtain Telegram credentials through a pre-created, exact-ARN Secrets Manager secret rather than embedding them in source code, deployment configuration, or CloudFormation outputs. The secret `SecretString` SHALL be JSON with exactly `schema_version` (integer `1`) and non-empty `telegram_bot_token` (string); Telegram channel and private alert-recipient identifiers SHALL remain non-secret runtime configuration. Publisher and alert-dispatcher roles SHALL have only `secretsmanager:GetSecretValue` permission on that exact secret ARN, restricted to `AWSCURRENT`, and SHALL not receive secret listing, write, rotation, or access to other secrets. If a customer-managed KMS key encrypts the secret, each role SHALL receive `kms:Decrypt` only for that key.

#### Scenario: Service starts in a deployed environment
- **WHEN** the scheduled service is invoked
- **THEN** it can access its required Telegram configuration without exposing the bot token in application source or operational logs

### Requirement: Isolate runtime and deployment IAM roles
The deployment SHALL define separate publisher, alert-dispatcher, reconciliation, rotation-smoke, office-info, Scheduler execution, and deployment roles. Runtime roles SHALL not assume one another or the deployment role. Each role's trust policy and permissions policy SHALL name only the required service principal, exact resource ARNs, and supported condition keys; `*` resources SHALL be prohibited except where an AWS action cannot be resource-scoped, in which case the policy SHALL constrain the action by its supported condition keys. No runtime role SHALL receive `secretsmanager:ListSecrets`, secret write/rotation permissions, DynamoDB `Scan`, wildcard S3 object access, or IAM administration permissions.

The publisher role SHALL access only this application's DynamoDB story, attempt, transition, run, current-projection, and quarantine key families; it SHALL use `dynamodb:LeadingKeys` conditions on those explicit partition-key prefixes wherever supported. It SHALL have only the required `GetItem`, `PutItem`, `UpdateItem`, `Query`, and conditional/transactional write actions on the table and required indexes. It SHALL access only this bucket's `staging/` and retained-image prefixes: list only those prefixes, read/write/copy objects as needed, and delete only `staging/` objects. It SHALL read only the exact Telegram secret at `AWSCURRENT`, publish application failure events only to the alert-trigger SNS topic, and write only its own logs and metrics.

The alert-dispatcher role SHALL access only the DynamoDB alert-state key family, enforced with its explicit partition-key prefix and `dynamodb:LeadingKeys` where supported; read the exact Telegram secret at `AWSCURRENT`; publish only to the fallback SNS topic; and write only its own logs and metrics. The reconciliation role SHALL read ambiguous publisher attempt/transition records and append authorized reconciliation transition events only to the relevant DynamoDB key families; it SHALL not access Secrets Manager, S3, or SNS. The dedicated rotation-smoke Lambda role SHALL read only the exact Telegram secret at `AWSPENDING`, with the associated scoped KMS decrypt permission when applicable, and write only its own logs and metrics; it SHALL call only Telegram `getMe` and SHALL not access DynamoDB, S3, or SNS or publish to Telegram chats.

The office-info role SHALL read/write only this environment's `OFFICE#` records, read the exact `AWSCURRENT` secret, call the NWS office/region endpoints, and use only the Telegram channel-management actions required to get/create/revoke the configured invite link, send/edit/pin the one managed information message, and verify the chat. It SHALL not access story, attempt, transition, run, projection, quarantine, alert, S3, or SNS resources and SHALL not invoke the publisher. Invite links, tokens, and raw Telegram payloads SHALL be excluded from logs.

The Scheduler execution role SHALL trust only `scheduler.amazonaws.com` and invoke only the qualified publisher Lambda ARN. Its trust and invoke policies SHALL use `aws:SourceArn` and `aws:SourceAccount` conditions where supported, binding the role to this application's office schedules and account. The separately documented, pre-created deployment role SHALL be trusted only by the authorized deployment CI identity or operators, may pass only the named application roles, and SHALL not be assumed by runtime functions. It SHALL deploy and manage only this application's named/tagged CloudFormation resources and SHALL not be granted runtime secret-read access.

#### Scenario: Alert dispatcher is compromised
- **WHEN** the alert-dispatcher execution role is used outside its intended workflow
- **THEN** it cannot read story/run/attempt history, access image objects, invoke the publisher, publish to the alert-trigger topic, or retrieve a pending secret version

#### Scenario: Scheduler attempts an unapproved invocation
- **WHEN** a principal or schedule outside the configured account and office schedules attempts to use the Scheduler execution role
- **THEN** the role trust or invocation policy denies the request

#### Scenario: Rotation smoke test runs
- **WHEN** the protected rotation-smoke Lambda validates an `AWSPENDING` token with Telegram `getMe`
- **THEN** it can read only that pending version and cannot publish a message or access application history, images, or alert topics

### Requirement: Rotate the Telegram bot token safely
The publisher and alert dispatcher SHALL retrieve only the `AWSCURRENT` secret version and cache the parsed token for no more than 60 seconds. Rotation SHALL be an operator-run procedure: generate a replacement token in BotFather; store it as a new `AWSPENDING` secret version; invoke the dedicated protected rotation-smoke Lambda that retrieves `AWSPENDING` and calls Telegram `getMe`; move that version to `AWSCURRENT`; wait at least 60 seconds; and invoke the normal runtime smoke path. `AWSPREVIOUS` SHALL be retained only for rollback and forensics. The rotation procedure SHALL not log or return either token.

#### Scenario: A token is rotated
- **WHEN** an operator completes the documented rotation procedure
- **THEN** both publisher and alert-dispatcher retrieve the new `AWSCURRENT` token within 60 seconds and the protected runtime smoke test confirms Telegram authentication

#### Scenario: Token retrieval fails after rotation
- **WHEN** the new `AWSCURRENT` token cannot authenticate with Telegram
- **THEN** the operator may restore `AWSPREVIOUS` to `AWSCURRENT`, the runtime re-fetches it within 60 seconds, and the failure context contains no token value

### Requirement: Redact Telegram tokens
The system SHALL redact the raw Telegram token and any URL, header, body, error, trace, fixture, or log field containing it before persistence or emission.

#### Scenario: An external-call error includes a request URL
- **WHEN** a Telegram request fails and its error context contains a token-bearing URL
- **THEN** the recorded and alerted error context excludes the token

### Requirement: Emit allowlisted, non-sensitive CloudWatch Logs
Each Lambda SHALL emit structured CloudWatch log events using only this allowlisted schema: event timestamp, log level, event type, component, `office_id`, `run_id`, `attempt_id`, revision hash, outcome/status, HTTP status, stable error class/code, sanitizer-produced error summary of at most 256 characters, latency, retry ordinal, retry/defer decision, and aggregate outcome counts. Fields that do not apply to an event MAY be omitted. The system SHALL NOT emit raw or token-bearing URLs; Telegram chat or message IDs; story IDs; S3 keys; story text, titles, descriptions, alt text, or image metadata; secret values; request or response bodies; headers; raw exception objects or stack traces; or unbounded upstream error text. Sensitive identifiers SHALL be omitted rather than hashed; authorized operators SHALL use the durable history store, correlated through the logged `run_id`, `attempt_id`, or revision hash, when raw references are needed for investigation.

The non-secret environment-scoped `log_level` SHALL be one of `DEBUG`, `INFO`, `WARNING`, or `ERROR`. Dev and staging SHALL default to `DEBUG`; prod SHALL default to `INFO` and reject `DEBUG`. At DEBUG, each Lambda SHALL additionally emit only allowlisted lifecycle and decision events for request start/completion and latency, validation stage and stable code, retry-budget decisions, and deduplication/reservation decisions. DEBUG SHALL NOT widen the log schema or permit raw tracing, arbitrary context, or sensitive data.

CloudWatch Logs groups for the publisher, alert dispatcher, reconciliation, and rotation-smoke Lambdas SHALL retain events for 90 days.

#### Scenario: A Telegram request fails with sensitive context
- **WHEN** a Telegram request or exception contains a token-bearing URL, request payload, chat ID, or raw response body
- **THEN** the emitted log event contains only applicable allowlisted fields and no sensitive value or raw exception content

#### Scenario: An operator investigates a logged event
- **WHEN** an operator needs a raw operational reference omitted from a log event
- **THEN** the operator uses the logged `run_id`, `attempt_id`, or revision hash to retrieve the authorized durable-history record rather than relying on a reversible logged identifier

#### Scenario: Development tracing is enabled
- **WHEN** a dev or staging Lambda uses its default `DEBUG` log level
- **THEN** it emits the additional allowlisted lifecycle and decision events without emitting a raw request, response, exception, URL, header, or sensitive identifier

#### Scenario: Production debug logging is requested
- **WHEN** prod configuration specifies `DEBUG` as its log level
- **THEN** configuration validation rejects the deployment or invocation before the Lambda emits application logs

#### Scenario: Log retention is configured
- **WHEN** the AWS SAM application provisions a Lambda log group
- **THEN** the log group has a 90-day retention policy

### Requirement: Monitor scheduled processing
The deployment SHALL monitor scheduled processing failures and trigger the private Telegram alert workflow when an alert condition is met. CloudWatch metric/composite-alarm actions SHALL be used for infrastructure and run-health metrics and shall notify only on alarm state transitions; application-specific alert fingerprints, cooldowns, and aggregation SHALL be handled by the DynamoDB-backed alert dispatcher state.

#### Scenario: Scheduled service invocation fails
- **WHEN** the scheduled AWS workload ends in a failure that meets the configured alert condition
- **THEN** the monitoring system triggers private operator notification

### Requirement: Provide environment-scoped metrics, alarms, and dashboards
The deployment SHALL provision one CloudWatch dashboard and one alarm set per environment. Each dashboard SHALL show the `WeatherStoryBot` metrics by `Environment` and `OfficeId`, with run health (`RunStarted`, `RunSucceeded`, `RunFailed`), retrieval and publication volume (`OfficeRetrievalFailed`, `StoriesDiscovered`, `StoriesPublished`, `StoriesEdited`), ambiguity and delivery failures (`ReservationsAmbiguous`, `ImageUploadFailed`, `Telegram429`, `AlertFallbackUsed`), p50/p90/p99 latency for `RunDurationMs`, `NwsRequestDurationMs`, `ImageDownloadDurationMs`, and `TelegramRequestDurationMs`, Lambda duration/max-memory, and the enabled/disabled schedule state. Dashboard and alarm definitions SHALL omit high-cardinality story, run, attempt, message, and URL dimensions.

For every active office whose schedule is enabled, the deployment SHALL configure these initial alarm thresholds: no `RunStarted` for 20 minutes; `RunFailed >= 1` in a 15-minute window; `ReservationsAmbiguous >= 1` in a 15-minute window; `OfficeRetrievalFailed >= 2` across two consecutive 15-minute windows; `ImageUploadFailed >= 2` across two consecutive 15-minute windows; `Telegram429 >= 1` in each of two consecutive 15-minute windows; and `AlertFallbackUsed >= 1` in a 15-minute window. Alarm actions SHALL publish to the alert-trigger SNS topic only on state transitions. Alarm actions SHALL be disabled while the corresponding schedule is intentionally disabled, including before the smoke-gated enablement of a newly created or updated stack; enabling a schedule SHALL enable its alarm actions as part of the same authorized operational step.

#### Scenario: An enabled office is quiet but healthy
- **WHEN** an office completes an empty collection within the 15-minute schedule interval
- **THEN** its dashboard shows `RunStarted=1`, `RunSucceeded=1`, and `StoriesDiscovered=0`, and no missing-heartbeat alarm fires

#### Scenario: An enabled office stops running
- **WHEN** no `RunStarted` metric is emitted for an enabled office for 20 minutes
- **THEN** the missing-heartbeat alarm enters `ALARM` and publishes one state-transition notification to the alert-trigger SNS topic

#### Scenario: A schedule is intentionally disabled
- **WHEN** an operator disables an environment's schedule during deployment, rollback, or maintenance
- **THEN** the corresponding alarm actions are disabled and the dashboard identifies the schedule as disabled rather than paging on absent runs

### Requirement: Connect alarms through SNS
The deployment SHALL configure CloudWatch alarms to publish to an alert-trigger SNS topic that invokes the alert-dispatch Lambda through an SNS subscription, with the required Lambda resource policy and retry configuration.

#### Scenario: Alarm notification is delivered
- **WHEN** a configured CloudWatch alarm changes into its alert state
- **THEN** CloudWatch publishes to the alert-trigger SNS topic and SNS invokes the alert-dispatch Lambda

#### Scenario: Alert-dispatch failure is handled
- **WHEN** the alert-dispatch Lambda cannot process an alert-trigger notification
- **THEN** SNS retries according to the configured policy and the dispatcher publishes delivery-failure context to the separate fallback SNS/email topic without re-triggering the alert-trigger path

#### Scenario: A monitored condition persists
- **WHEN** a CloudWatch alarm remains in `ALARM` across multiple evaluation periods
- **THEN** CloudWatch does not repeat its alarm action until the alarm changes state, while application-originated events remain subject to dispatcher fingerprinting and cooldown

### Requirement: Exclude SQS
The deployment SHALL NOT provision or require Amazon SQS resources for story polling, publication, or alert delivery.

#### Scenario: Infrastructure is reviewed
- **WHEN** the AWS SAM application is inspected after deployment
- **THEN** no SQS queue or SQS event source is part of the deployed architecture

### Requirement: Provide an operator reconciliation Lambda
The deployment SHALL provide a protected Lambda invocation path for an operator to reconcile only ambiguous publication attempts.

#### Scenario: Operator confirms a message was received
- **WHEN** an authorized operator invokes the reconciliation Lambda for an ambiguous attempt and selects `confirmed_received`
- **THEN** the attempt is transitioned to `confirmed_received` without sending another Telegram message

#### Scenario: Operator authorizes a retry
- **WHEN** an authorized operator invokes the reconciliation Lambda for an ambiguous attempt and selects `confirmed_not_received`
- **THEN** the attempt is transitioned to `confirmed_not_received` and the next scheduled poll may create a new reservation

### Requirement: Govern the public source repository

The service source SHALL be hosted in a public GitHub repository with an explicit open-source license, project documentation, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CODEOWNERS`, issue templates, and pull-request templates. The public remote and baseline pull-request validation SHALL be established before continuing MVP implementation. Squash SHALL be the repository's only enabled pull-request merge method, and the active default-branch ruleset SHALL permit only squash merges. After the documented initial repository-bootstrap push, application code, infrastructure, dependency manifests and lockfiles, workflow definitions, and repository-policy changes from all contributors other than `@hamdrew` SHALL merge through a squash pull request that satisfies required status checks and applicable `CODEOWNERS` review. The active default-branch ruleset SHALL prohibit direct pushes and unreviewed workflow-file changes for all other contributors, while granting only sole maintainer `@hamdrew` an audited always-bypass for self-approval, self-merge, and occasional direct default-branch pushes.

#### Scenario: A change is proposed
- **WHEN** a contributor submits a pull request to the default branch
- **THEN** the repository requires the configured checks and an authorized review before the change can merge by squash only

#### Scenario: A workflow or deployment policy changes
- **WHEN** a pull request changes GitHub Actions, deployment configuration, IAM/OIDC trust, secrets configuration, or release policy
- **THEN** the repository applies the stricter ownership and review requirements for protected delivery controls

#### Scenario: A direct change is attempted after bootstrap
- **WHEN** a contributor other than `@hamdrew` attempts to push application, infrastructure, dependency, workflow, or repository-policy changes directly to the default branch after the repository bootstrap
- **THEN** the active ruleset rejects the push and requires the configured pull-request checks and applicable ownership review

#### Scenario: The sole maintainer needs an exceptional change path
- **WHEN** `@hamdrew` self-approves or self-merges a pull request, or occasionally pushes directly to the default branch
- **THEN** the sole-maintainer ruleset bypass permits the action and GitHub records it as a bypass, while no other actor has bypass permission

### Requirement: Validate changes through GitHub Actions

The repository SHALL provide GitHub Actions workflows that run formatting, static analysis, unit tests, integration tests, SAM/template validation, reproducible packaging checks, dependency/security/license scans, and infrastructure cost checks as applicable. The baseline Python validation workflow SHALL enforce a minimum 75% line-coverage floor through pytest-cov, generate the committed test suite's Cobertura XML and JSON reports, and retain those artifacts for tooling consumption without a pull-request coverage summary. A separate branch-only fail threshold is not required because pytest-cov does not provide one. Deployment workflows SHALL use the reviewed artifact and SHALL publish bounded test, scan, SBOM, cost, and change-set evidence. Workflow permissions SHALL be least-privilege. Every GitHub Action reference SHALL use the full commit hash corresponding to its latest released version and SHALL include an inline comment with that release tag; floating tags, branches, and unannotated commit references are prohibited. Concurrent superseded runs SHALL be cancelled when safe.

#### Scenario: A pull request is opened
- **WHEN** a pull request changes application, infrastructure, dependency, or workflow files
- **THEN** the applicable validation workflows run and the required checks report success or actionable failure before merge

#### Scenario: A validation check fails
- **WHEN** tests, SAM validation, packaging, security/license scans, or required cost checks fail
- **THEN** the pull request cannot satisfy the protected-branch merge gate until the failure is resolved or an authorized exception is recorded

#### Scenario: Line coverage falls below the baseline
- **WHEN** pytest-cov reports line coverage below 75%
- **THEN** the validation workflow fails and the pull request cannot satisfy the protected-branch merge gate

### Requirement: Deploy through protected GitHub environments

The deployment pipeline SHALL authenticate to AWS using GitHub OIDC with a trust policy restricted to this repository, approved workflow/ref or environment claims, and the authorized AWS account. It SHALL use separate protected GitHub environments for `dev`, `staging`, and `prod`; environment secrets and variables SHALL be isolated; production SHALL require an authorized human approval; and deployment jobs SHALL use the environment-specific CloudFormation change-set and smoke-gate procedure. Long-lived AWS access keys SHALL NOT be stored as repository or environment secrets.

Before the GitHub OIDC deployment workflow is available, documented and audited workstation deployment SHALL be permitted only for dev and staging bootstrap: dev SHALL remain mock-only and staging SHALL be limited to its dedicated test-channel smoke procedure. Workstation deployment to prod SHALL NOT be permitted. Once the OIDC workflow is available, every production deployment SHALL originate from the reviewed workflow and protected production environment.

#### Scenario: A staging deployment is requested
- **WHEN** the reviewed deployment workflow targets `staging`
- **THEN** it obtains short-lived AWS credentials through the staging OIDC trust, creates/reviews the environment-scoped change set, and runs the staging smoke gate before schedule enablement

#### Scenario: A production deployment is requested
- **WHEN** the reviewed deployment workflow targets `prod`
- **THEN** GitHub requires the protected production environment approval before execution, and the workflow uses the production change-set and non-publishing pre-enable checks

#### Scenario: An untrusted workflow requests AWS access
- **WHEN** a fork, unapproved branch, or unrelated workflow attempts to assume the deployment role
- **THEN** the OIDC trust policy denies the request

#### Scenario: A bootstrap operator attempts a production deployment
- **WHEN** an operator attempts to deploy to prod from a workstation before or after GitHub OIDC is configured
- **THEN** the documented deployment procedure rejects that path and requires the reviewed GitHub workflow and protected production-environment approval

### Requirement: Automate dependency and action maintenance

The repository SHALL configure Dependabot for the application dependency manifests, lockfiles, GitHub Actions, and other supported package ecosystems used by the service. Dependabot pull requests SHALL run the same relevant validation and security checks as ordinary changes, SHALL preserve lockfile reproducibility, and SHALL require review for production/runtime dependencies, deployment tooling, or workflow changes.

#### Scenario: A dependency update is proposed
- **WHEN** Dependabot opens a pull request for a runtime, development, or workflow dependency
- **THEN** the corresponding tests, lockfile checks, vulnerability/license scans, and ownership review requirements are applied

#### Scenario: A security update is available
- **WHEN** Dependabot identifies a security update
- **THEN** the repository creates or surfaces an update through the configured security workflow without granting Dependabot a protected-branch bypass or bypassing production approval

### Requirement: Produce traceable, integrity-protected releases

The repository SHALL use a documented versioning and release process with protected version tags, changelog or generated release notes, and release artifacts traceable to the source commit, dependency lock, SBOM, scan results, cost result, CloudFormation template, and deployed application version. Releases SHALL use signed tags and/or verifiable build provenance and SHALL not contain Telegram secrets, AWS credentials, or environment-specific secret values.

#### Scenario: A release is created
- **WHEN** an authorized release workflow publishes a version
- **THEN** it creates the approved tag/release metadata, attaches the packaged artifact and SBOM/scan evidence, and records the source commit and deployment identity

#### Scenario: Release verification fails
- **WHEN** tag protection, artifact integrity, provenance, SBOM, or blocking scan requirements cannot be satisfied
- **THEN** the release is not published or promoted to production

### Requirement: Protect public-repository security and collaboration surfaces

The repository SHALL enable available public-repository security controls, including Dependabot alerts/security updates, secret scanning with push protection, code scanning, dependency review, and a documented vulnerability-reporting path. Public issue and discussion surfaces SHALL use templates and labels that prevent secrets, Telegram tokens, personal data, or unbounded operational logs from being requested or published. Repository metadata SHALL identify the license, support path, service owner, and operational documentation.

#### Scenario: A secret is committed or pushed
- **WHEN** GitHub detects a supported credential or token pattern before it reaches the default branch
- **THEN** push protection blocks the push or creates the configured security alert and the response procedure directs immediate credential rotation

#### Scenario: A public issue reports an operational failure
- **WHEN** a user submits an issue using the public template
- **THEN** the template directs them to omit secrets and sensitive logs and provides the appropriate public support or private security-reporting path
