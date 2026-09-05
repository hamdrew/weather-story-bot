"""Repository-policy tests for the baseline GitHub security and PR workflows."""

import re
from pathlib import Path
from typing import Any, cast

import yaml


class TemplateLoader(yaml.SafeLoader):
    """Safe intrinsic preservation for assertions; never execute YAML constructors."""


def intrinsic(loader: TemplateLoader, tag: str, node: yaml.Node) -> dict[str, object]:
    name = tag if tag == "Ref" else "Fn::" + tag
    if isinstance(node, yaml.ScalarNode):
        value: object = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        raise ValueError("unsupported intrinsic node")
    return {name: value}


TemplateLoader.add_multi_constructor("!", intrinsic)


def template() -> dict[str, Any]:
    return cast(
        dict[str, Any], yaml.load(read_repository_file("template.yaml"), Loader=TemplateLoader)
    )


def test_operations_template_has_no_schedule_public_endpoint_or_custom_state() -> None:
    document = template()
    resources = document["Resources"]
    forbidden = {
        "AWS::SQS::Queue",
        "AWS::DynamoDB::Table",
        "AWS::Scheduler::Schedule",
        "AWS::Lambda::Url",
        "AWS::Serverless::Api",
        "AWS::ApiGateway::RestApi",
    }
    assert not {resource["Type"] for resource in resources.values()} & forbidden
    for name in ("OfficeFunction", "AlertFunction"):
        function = resources[name]["Properties"]
        assert "Events" not in function
        assert "Policies" not in function
    assert document["Globals"]["Function"]["Runtime"] == "python3.13"
    assert document["Globals"]["Function"]["Architectures"] == ["arm64"]
    assert document["Parameters"]["Environment"]["AllowedValues"] == ["staging"]


def test_notification_graph_cannot_return_to_trigger_or_retry_on_function_error() -> None:
    resources = template()["Resources"]
    subscriptions = [
        r["Properties"] for r in resources.values() if r["Type"] == "AWS::SNS::Subscription"
    ]
    assert {(str(s["TopicArn"]), s["Protocol"]) for s in subscriptions} == {
        (str({"Ref": "TriggerTopic"}), "lambda"),
        (str({"Ref": "FallbackTopic"}), "email"),
    }
    role = resources["AlertRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    allowed = [s for s in role if s["Effect"] == "Allow"]
    publications = [s["Resource"] for s in allowed if s["Action"] == "sns:Publish"]
    assert publications == [{"Ref": "FallbackTopic"}]
    assert not any("dynamodb" in str(s["Action"]) for s in allowed)
    assert "AlarmActions" not in resources["AlertFailureAlarm"]["Properties"]
    assert (
        resources["AlertFunction"]["Properties"]["EventInvokeConfig"]["MaximumRetryAttempts"] == 0
    )
    source = resources["AlertInvokePermission"]["Properties"]
    assert source["Principal"] == "sns.amazonaws.com"
    assert source["SourceArn"] == {"Ref": "TriggerTopic"}
    assert source["SourceAccount"] == {"Ref": "AWS::AccountId"}


def test_office_role_can_only_read_and_write_its_office_partition() -> None:
    statements = template()["Resources"]["OfficeRole"]["Properties"]["Policies"][0][
        "PolicyDocument"
    ]["Statement"]
    dynamo = [s for s in statements if str(s["Action"]).startswith("dynamodb:")]
    assert {s["Action"] for s in dynamo} == {"dynamodb:GetItem", "dynamodb:PutItem"}
    for statement in dynamo:
        assert statement["Condition"]["ForAllValues:StringEquals"]["dynamodb:LeadingKeys"] == {
            "Ref": "ActiveOfficeKeys"
        }
    assert template()["Parameters"]["ActiveOfficeKeys"]["AllowedPattern"] == "OFFICE#[A-Z]{3}"
    assert not any(
        "sns:" in str(s["Action"]) or "scheduler:" in str(s["Action"]) for s in statements
    )


def test_operation_template_retains_logs_encrypts_topics_and_scopes_secrets() -> None:
    resources = template()["Resources"]
    for name in ("OfficeLogGroup", "AlertLogGroup"):
        assert resources[name]["Properties"]["RetentionInDays"] >= 90
        assert resources[name]["DeletionPolicy"] == "Retain"
        assert resources[name]["UpdateReplacePolicy"] == "Retain"
    for name in ("TriggerTopic", "FallbackTopic"):
        assert resources[name]["Properties"]["KmsMasterKeyId"] == {
            "Fn::GetAtt": "NotificationKey.Arn"
        }
    for role_name in ("OfficeRole", "AlertRole"):
        statements = resources[role_name]["Properties"]["Policies"][0]["PolicyDocument"][
            "Statement"
        ]
        assert not any("Delete" in str(s["Action"]) for s in statements)
        for statement in statements:
            assert statement["Resource"] != "*"
            assert "*" not in str(statement["Action"])
            if statement["Action"] == "secretsmanager:GetSecretValue":
                assert (
                    statement["Condition"]["StringEquals"]["secretsmanager:VersionStage"]
                    == "AWSCURRENT"
                )
    assert template()["Parameters"]["FallbackEmail"]["NoEcho"] is True


def test_office_alarm_has_explicit_noise_and_missing_data_policy() -> None:
    alarm = template()["Resources"]["OfficeFailureAlarm"]["Properties"]
    assert 1 <= alarm["DatapointsToAlarm"] <= alarm["EvaluationPeriods"]
    assert alarm["TreatMissingData"] == "notBreaching"
    assert alarm["AlarmActions"] == [{"Ref": "TriggerTopic"}]


ROOT = Path(__file__).parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
SHA_PIN = re.compile(r"uses: [\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+")


def read_repository_file(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_security_workflow_enables_codeql_and_dependency_license_review() -> None:
    workflow = read_repository_file(".github/workflows/security.yml")

    assert "pull_request:" in workflow
    assert "pull_request_target:" not in workflow
    assert "github/codeql-action/init@" in workflow
    assert "github/codeql-action/analyze@" in workflow
    assert "languages: python" in workflow
    assert "actions/dependency-review-action@" in workflow
    assert "license-check: true" in workflow
    assert "vulnerability-check: true" in workflow
    assert "deny-licenses: AGPL-3.0,GPL-2.0,GPL-3.0" in workflow


def test_pull_request_workflows_are_fork_safe_and_least_privilege() -> None:
    for workflow_name in ("pr-validation.yml", "security.yml"):
        workflow = read_repository_file(f".github/workflows/{workflow_name}")

        assert "pull_request:" in workflow
        assert "pull_request_target:" not in workflow
        assert "permissions:\n  contents: read" in workflow
        assert "secrets." not in workflow
        assert "github.event.pull_request.head.repo.full_name" not in workflow
        assert "concurrency:" in workflow
        assert "cancel-in-progress: true" in workflow


def test_workflows_pin_actions_to_release_annotated_full_commits() -> None:
    for workflow_path in WORKFLOWS.glob("*.yml"):
        workflow = workflow_path.read_text(encoding="utf-8")
        action_references = [line for line in workflow.splitlines() if "uses: " in line]

        assert action_references
        assert all(SHA_PIN.search(line) for line in action_references)


def test_pr_validation_covers_the_baseline_python_checks() -> None:
    workflow = read_repository_file(".github/workflows/pr-validation.yml")

    for command in (
        "uv lock --check",
        "uv sync --locked",
        "ruff format --check src tests",
        "make lint",
        "make typecheck",
        "make test",
    ):
        assert command in workflow

    assert "Run unit and property tests" in workflow


def test_public_reporting_surfaces_exclude_sensitive_operational_data() -> None:
    security_policy = read_repository_file("SECURITY.md")
    bug_template = read_repository_file(".github/ISSUE_TEMPLATE/bug_report.yml")
    feature_template = read_repository_file(".github/ISSUE_TEMPLATE/feature_request.yml")
    pr_template = read_repository_file(".github/pull_request_template.md")

    assert "private GitHub Security Advisories" in security_policy
    assert "Rotate or revoke exposed credentials" in security_policy
    for document in (bug_template, feature_template, pr_template):
        assert "token" in document.lower() or "secret" in document.lower()
        assert "credential" in document.lower() or "private" in document.lower()
        assert "private" in document.lower() or "sensitive" in document.lower()


def test_contribution_guidance_requires_pull_requests_and_redaction() -> None:
    guidance = read_repository_file("CONTRIBUTING.md")

    assert "Fork the repository" in guidance
    assert "Open a pull request" in guidance
    assert "Never commit tokens, AWS credentials" in guidance
