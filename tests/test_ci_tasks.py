"""The CI-only mise tasks (infra/pipeline), run for real with fake terraform and aws on PATH."""

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

TASKS = Path(__file__).parent.parent / "mise-tasks"


def fake(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/usr/bin/env bash\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def sandbox(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "infra" / "envs").mkdir(parents=True)
    return tmp_path


def run(sandbox: Path, task: str, **env: str) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items() if k not in {"GITHUB_ACTIONS", "BREAK_GLASS"}}
    base["PATH"] = f"{sandbox / 'bin'}{os.pathsep}{base['PATH']}"
    return subprocess.run(
        [str(TASKS / task)],
        env={**base, **env},
        cwd=sandbox,
        capture_output=True,
        text=True,
        check=False,
    )


# plan-changes: does the saved plan change anything?


def plan_json(resource_actions=(), output_actions=(), drift_actions=(), importing=()) -> str:
    return json.dumps(
        {
            "resource_changes": [
                {"change": {"actions": a, **({"importing": {"id": "x"}} if i else {})}}
                for a, i in zip(
                    resource_actions, [*importing, *[False] * len(resource_actions)], strict=False
                )
            ],
            "output_changes": {f"o{i}": {"actions": a} for i, a in enumerate(output_actions)},
            "resource_drift": [{"change": {"actions": a}} for a in drift_actions],
        }
    )


@pytest.mark.parametrize(
    ("resources", "outputs", "expected"),
    [
        ([], [], "false"),
        ([["no-op"], ["read"]], [["no-op"]], "false"),
        ([["no-op"], ["update"]], [], "true"),
        ([["create"]], [], "true"),
        ([["delete", "create"]], [], "true"),
        ([["no-op"]], [["update"]], "true"),
    ],
)
def test_plan_changes(sandbox, resources, outputs, expected):
    (sandbox / "plan.json").write_text(plan_json(resources, outputs))
    fake(sandbox / "bin", "terraform", f'cat "{sandbox}/plan.json"')
    result = run(sandbox, "plan-changes", usage_environment="staging")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def planned(sandbox: Path, **kwargs) -> str:
    (sandbox / "plan.json").write_text(plan_json(**kwargs))
    fake(sandbox / "bin", "terraform", f'cat "{sandbox}/plan.json"')
    result = run(sandbox, "plan-changes", usage_environment="staging")
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_drift_counts_as_a_change(sandbox):
    # Refreshed state differs from the last apply (something changed outside Terraform).
    assert planned(sandbox, resource_actions=[["no-op"]], drift_actions=[["update"]]) == "true"


def test_drift_of_a_deleted_resource_counts_as_a_change(sandbox):
    assert planned(sandbox, drift_actions=[["delete"]]) == "true"


def test_an_import_counts_as_a_change(sandbox):
    # An import's action is no-op; only change.importing says state is about to gain a resource.
    assert planned(sandbox, resource_actions=[["no-op"]], importing=[True]) == "true"


def test_no_drift_no_import_is_still_no_change(sandbox):
    assert planned(sandbox, resource_actions=[["no-op"]], drift_actions=[["no-op"]]) == "false"


def test_plan_changes_fails_closed_when_terraform_fails(sandbox):
    fake(sandbox / "bin", "terraform", "exit 1")
    result = run(sandbox, "plan-changes", usage_environment="staging")
    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_plan_changes_writes_the_github_output(sandbox):
    (sandbox / "plan.json").write_text(plan_json([["update"]]))
    fake(sandbox / "bin", "terraform", f'cat "{sandbox}/plan.json"')
    out = sandbox / "github_output"
    result = run(
        sandbox,
        "plan-changes",
        usage_environment="staging",
        usage_github_output="true",
        GITHUB_OUTPUT=str(out),
    )
    assert result.returncode == 0, result.stderr
    assert out.read_text() == "changed=true\n"


def test_plan_changes_writes_nothing_and_fails_when_terraform_fails(sandbox):
    # The step must go red, not write an empty changed= that reads as "no changes".
    fake(sandbox / "bin", "terraform", "exit 1")
    out = sandbox / "github_output"
    out.write_text("")
    result = run(
        sandbox,
        "plan-changes",
        usage_environment="staging",
        usage_github_output="true",
        GITHUB_OUTPUT=str(out),
    )
    assert result.returncode != 0
    assert out.read_text() == ""


def test_plan_changes_refuses_an_answer_that_is_not_true_or_false(sandbox):
    fake(sandbox / "bin", "terraform", "echo '{}' ; echo noise >&2")
    fake(sandbox / "bin", "uv", "echo maybe")
    out = sandbox / "github_output"
    out.write_text("")
    result = run(
        sandbox,
        "plan-changes",
        usage_environment="staging",
        usage_github_output="true",
        GITHUB_OUTPUT=str(out),
    )
    assert result.returncode != 0
    assert out.read_text() == ""


# plan-summary: the plan on the workflow run's summary page

PLAN_TEXT = (
    "Terraform will perform the following actions:\n"
    "  # aws_lambda_function.bot will be updated\n\n"
    "Plan: 0 to add, 1 to change, 0 to destroy.\n"
)


def summary(sandbox: Path, text: str, **env: str):
    fake(sandbox / "bin", "terraform", f"cat <<'EOF'\n{text}\nEOF")
    out = sandbox / "summary.md"
    result = run(
        sandbox,
        "plan-summary",
        usage_environment="staging",
        GITHUB_STEP_SUMMARY=str(out),
        **env,
    )
    return result, out


def test_plan_summary_has_the_counts_and_the_full_plan(sandbox):
    result, out = summary(sandbox, PLAN_TEXT)
    assert result.returncode == 0, result.stderr
    text = out.read_text()
    assert "staging" in text.splitlines()[0]
    assert "Plan: 0 to add, 1 to change, 0 to destroy." in text.splitlines()[0]
    assert "<details>" in text
    assert "aws_lambda_function.bot will be updated" in text


def test_plan_summary_with_no_changes(sandbox):
    result, out = summary(sandbox, "No changes. Your infrastructure matches the configuration.")
    assert result.returncode == 0, result.stderr
    assert "No changes." in out.read_text().splitlines()[0]


def test_plan_summary_truncates_a_huge_plan(sandbox):
    # A step summary is capped at 1 MiB; a plan that fills it must not fail the step.
    result, out = summary(sandbox, PLAN_TEXT + "x" * 2_000_000)
    assert result.returncode == 0, result.stderr
    assert out.stat().st_size < 1_000_000
    assert "truncated" in out.read_text()


def test_plan_summary_needs_a_summary_file(sandbox):
    fake(sandbox / "bin", "terraform", "echo plan")
    result = run(sandbox, "plan-summary", usage_environment="staging")
    assert result.returncode == 1


# plan-store: production's saved plan in the artifacts bucket


def fake_aws(sandbox: Path) -> None:
    fake(sandbox / "bin", "aws", f'echo "$@" >> "{sandbox}/aws.log"')


KEY = "plans/production/1-1.tfplan"


def store(sandbox: Path, action: str, key: str = KEY, **env: str):
    return run(sandbox, "plan-store", usage_action=action, usage_key=key, **env)


def write_tfvars(sandbox: Path, text: str) -> None:
    (sandbox / "infra" / "envs" / "production.tfvars").write_text(text)


def test_plan_store_upload(sandbox):
    write_tfvars(sandbox, 'alert_email = "a@b.c"\nartifacts_bucket = "my-artifacts-1"\n')
    fake_aws(sandbox)
    result = store(sandbox, "upload", GITHUB_ACTIONS="true")
    assert result.returncode == 0, result.stderr
    line = (sandbox / "aws.log").read_text().strip()
    assert "put-object" in line
    assert "--bucket my-artifacts-1" in line
    assert f"--key {KEY}" in line
    assert "--if-none-match *" in line


def test_plan_store_download(sandbox):
    write_tfvars(sandbox, 'artifacts_bucket = "my-artifacts-1"\n')
    fake_aws(sandbox)
    result = store(sandbox, "download", GITHUB_ACTIONS="true")
    assert result.returncode == 0, result.stderr
    line = (sandbox / "aws.log").read_text().strip()
    assert "get-object" in line
    assert line.endswith("infra/deploy-production.tfplan")


@pytest.mark.parametrize(
    "tfvars",
    [
        '  artifacts_bucket   =   "my-artifacts-1"  # from bootstrap\n',
        'artifacts_bucket = "stale-one"\nartifacts_bucket = "my-artifacts-1"\n',
    ],
    ids=["indented-with-comment", "last-assignment-wins"],
)
def test_plan_store_reads_the_bucket_the_way_terraform_does(sandbox, tfvars):
    write_tfvars(sandbox, tfvars)
    fake_aws(sandbox)
    result = store(sandbox, "upload", GITHUB_ACTIONS="true")
    assert result.returncode == 0, result.stderr
    assert "--bucket my-artifacts-1 " in (sandbox / "aws.log").read_text()


BAD_BUCKETS = ["", 'artifacts_bucket = "Not A Bucket"\n', "artifacts_bucket = unquoted\n"]


@pytest.mark.parametrize("tfvars", BAD_BUCKETS)
def test_plan_store_refuses_a_missing_or_malformed_bucket(sandbox, tfvars):
    write_tfvars(sandbox, tfvars)
    fake_aws(sandbox)
    result = store(sandbox, "upload", GITHUB_ACTIONS="true")
    assert result.returncode == 1
    assert not (sandbox / "aws.log").exists()


def test_plan_store_refuses_other_keys_and_laptops(sandbox):
    write_tfvars(sandbox, 'artifacts_bucket = "my-artifacts-1"\n')
    fake_aws(sandbox)
    other = store(sandbox, "upload", "staging/lambda/x.zip", GITHUB_ACTIONS="true")
    laptop = store(sandbox, "upload")
    assert other.returncode == 1
    assert laptop.returncode == 1
    assert not (sandbox / "aws.log").exists()


# write-env-config: backend config and tfvars from CI variables and secrets

GOOD = {
    "GITHUB_ACTIONS": "true",
    "usage_environment": "staging",
    "STATE_BUCKET": "state-bucket",
    "STATE_KEY": "weather-story-bot/staging/terraform.tfstate",
    "REGION": "us-east-2",
    "TFVARS": 'alert_email = "a@b.c"\nartifacts_bucket = "x"',
}


def test_write_env_config_writes_both_files(sandbox):
    result = run(sandbox, "write-env-config", **GOOD)
    assert result.returncode == 0, result.stderr
    backend = (sandbox / "infra/envs/staging.backend.hcl").read_text()
    assert 'bucket       = "state-bucket"' in backend
    assert 'key          = "weather-story-bot/staging/terraform.tfstate"' in backend
    assert 'region       = "us-east-2"' in backend
    assert (sandbox / "infra/envs/staging.tfvars").read_text() == GOOD["TFVARS"] + "\n"


@pytest.mark.parametrize(
    ("missing", "named"),
    [
        ("STATE_BUCKET", "TF_STATE_BUCKET"),
        ("REGION", "AWS_REGION"),
        ("STATE_KEY", "STATE_KEY"),
        ("TFVARS", "STAGING_TFVARS"),
    ],
)
def test_write_env_config_names_what_is_missing(sandbox, missing, named):
    result = run(sandbox, "write-env-config", **{**GOOD, missing: ""})
    assert result.returncode == 1
    assert named in result.stdout + result.stderr
    assert not (sandbox / "infra/envs/staging.backend.hcl").exists()


@pytest.mark.parametrize("field", ["STATE_BUCKET", "STATE_KEY", "REGION"])
@pytest.mark.parametrize("bad", ['x"\ninjected = "1', 'has"quote', "new\nline"])
def test_write_env_config_refuses_values_that_would_break_the_hcl(sandbox, field, bad):
    result = run(sandbox, "write-env-config", **{**GOOD, field: bad})
    assert result.returncode == 1
    assert not (sandbox / "infra/envs/staging.backend.hcl").exists()


def test_write_env_config_refuses_a_laptop(sandbox):
    result = run(sandbox, "write-env-config", **{**GOOD, "GITHUB_ACTIONS": ""})
    assert result.returncode == 1
