"""The break-glass guard that keeps production pipeline-only (infra/pipeline)."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "mise-tasks" / "check-break-glass"


def run(environment: str, **env: str) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items() if k not in {"BREAK_GLASS", "GITHUB_ACTIONS"}}
    return subprocess.run(
        [str(SCRIPT)],
        env={**base, "usage_environment": environment, **env},
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_refused_from_a_laptop():
    result = run("production")
    assert result.returncode == 1
    assert "BREAK_GLASS=1" in result.stderr


@pytest.mark.parametrize("env", [{"BREAK_GLASS": "1"}, {"GITHUB_ACTIONS": "true"}])
def test_production_allowed_deliberately_or_from_the_pipeline(env):
    assert run("production", **env).returncode == 0


@pytest.mark.parametrize("value", ["0", "true", "yes", ""])
def test_only_break_glass_one_counts(value):
    assert run("production", BREAK_GLASS=value).returncode == 1


def test_staging_never_needs_it():
    assert run("staging").returncode == 0
