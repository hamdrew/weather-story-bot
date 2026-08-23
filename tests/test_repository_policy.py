"""Repository-policy tests for the baseline GitHub security and PR workflows."""

import re
from pathlib import Path

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


def test_living_data_model_documents_exist_and_are_linked_from_readme() -> None:
    readme = read_repository_file("README.md")

    for document in ("docs/data-model.md", "docs/state-diagram.md"):
        content = read_repository_file(document)

        assert content.startswith("# ")
        assert f"]({document})" in readme
