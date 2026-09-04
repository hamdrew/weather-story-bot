# Deployment Governance Clarification Questions

## Context

The approved requirements currently prohibit production deployment and require separate
exact-scope authorization for every remote AWS or GitHub mutation. The user has changed that
boundary: AI-DLC shall include production deployment, may initiate cloud deployment planning, and
may approve safe expected dev/staging changes. A human must approve production application and any
change set that adds or removes resources.

AWS SAM deploys applications through AWS CloudFormation stacks. CloudFormation change sets allow
the proposed stack changes to be reviewed before they are executed. These questions make the
cloud-hosted execution and approval model precise before requirements are amended.

## Questions

### Question 1: Cloud Deployment Control Plane

Which cloud-hosted control plane should be the required path for staging and production?

**Recommendation: A.** AWS CodePipeline with CodeBuild and CloudFormation change sets provides
an AWS-native equivalent to a hosted IaC control plane: it can run SAM build/package and create a
reviewable change set in AWS, pause for approval, and then execute the exact approved change set.
The CloudFormation Console remains suitable for human inspection and an explicitly documented
break-glass procedure, but it should not be the normal reproducible path.

A) **Recommended** - AWS CodePipeline/CodeBuild creates environment-specific CloudFormation
change sets from the reviewed revision; CloudFormation Console is allowed for inspection and
documented break-glass use

B) AWS CloudFormation Console is the normal staging and production deployment interface; the
agent prepares plans and a human creates or executes the stack change set in the console

C) GitHub Actions is the required cloud runner, using OIDC to create and execute CloudFormation
change sets; the AWS Console is inspection-only

D) Other AWS-hosted runner or control plane (describe the service and approval mechanism)

X) Other (please describe after the `[Answer]:` tag below)

### Question 2: Agent-Approved Safe Dev/Staging Changes

What must qualify as a safe change that AI-DLC may approve and apply in dev or staging after all
required validation gates pass?

**Recommendation: A.** Treat only bounded in-place changes as agent-approvable. Resource
additions, removals, replacements, IAM/permission boundary changes, secret access changes, and
environment-target changes are high-impact even if the change set does not label them as an
add/remove, so they should require human approval. This realizes the stated resource guardrail
without leaving a privilege-escalation gap.

A) **Recommended** - Only dev/staging in-place changes with no Add, Remove, or Replacement action
and no IAM, permission-boundary, secret-access, environment-target, or deployment-role change;
all required tests, security, cost, provenance, and change-set gates must pass

B) Any dev/staging change with no Add or Remove action, even if it replaces a resource or changes
IAM, permissions, secrets, or deployment roles

C) AI-DLC may prepare plans but every dev/staging application requires human approval

X) Other (please describe after the `[Answer]:` tag below)

### Question 3: Production Change-Set Approval and Execution

How should an approved production change set be applied?

**Recommendation: A.** A cloud pipeline can create the exact immutable production change set,
wait at a human approval gate, and execute that same change set only after approval. This avoids
the plan/apply mismatch that can occur if a new command rebuilds the deployment after review,
while retaining a human decision before every production mutation.

A) **Recommended** - Cloud pipeline creates and records the production change set; a human
approves it in the cloud control plane; the pipeline executes that exact approved change set

B) Cloud pipeline creates and records the change set; a human inspects and manually executes it
from the CloudFormation Console

C) AI-DLC executes production changes after a human approves an AI-DLC prompt, without a
cloud-native approval gate

X) Other (please describe after the `[Answer]:` tag below)

## Answer Validation

- Questions 1-3 were answered `A, A, A` on 2026-09-02.
- The answers are mutually consistent and require no follow-up clarification.
- GitHub remains the source of truth; the default CodeConnections revision artifact is read-only.
- Infracost remains the selected cost estimator and runs as a blocking CodeBuild step.
