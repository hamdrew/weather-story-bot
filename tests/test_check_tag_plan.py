from __future__ import annotations

import io
import json
from typing import Any

import pytest

from scripts import check_tag_plan
from scripts.check_tag_plan import ABAC_ADDRESS, offenders

TAGS = {"Project": "weather-story-bot", "ManagedBy": "terraform"}
TAGGED = {**TAGS, "Environment": "production"}


def change(
    address: str,
    actions: list[str],
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    after_unknown: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "address": address,
        "mode": "managed",
        "change": {
            "actions": actions,
            "before": before,
            "after": after,
            "after_unknown": after_unknown or {},
        },
        **extra,
    }


def tag_update(address: str = "aws_sns_topic.alerts", **extra: Any) -> dict[str, Any]:
    return change(
        address,
        ["update"],
        before={"name": "weather-story-bot", "tags": None, "tags_all": TAGS},
        after={"name": "weather-story-bot", "tags": None, "tags_all": TAGGED},
        **extra,
    )


def abac_create() -> dict[str, Any]:
    return change(
        ABAC_ADDRESS,
        ["create"],
        after={"abac_status": [{"status": "Enabled"}]},
        after_unknown={"bucket": True},
    )


def plan(*changes: dict[str, Any]) -> dict[str, Any]:
    return {
        "format_version": "1.2",
        "complete": True,
        "planned_values": {},
        "resource_changes": list(changes),
    }


def check(plan: dict[str, Any], environment: str = "production") -> list[tuple[str, str]]:
    return offenders(plan, environment)


def test_unchanged_resource_passes() -> None:
    assert check(plan(change("aws_sns_topic.alerts", ["no-op"]))) == []


def test_move_passes() -> None:
    moved = change(
        "aws_budgets_budget.monthly[0]",
        ["no-op"],
        previous_address="aws_budgets_budget.monthly",
    )

    assert check(plan(moved)) == []


def test_tag_only_update_adding_environment_passes() -> None:
    assert check(plan(tag_update())) == []


def test_moved_tag_only_update_passes() -> None:
    moved = tag_update("aws_dynamodb_table.posted[0]", previous_address="aws_dynamodb_table.posted")

    assert check(plan(moved)) == []


def test_single_abac_create_passes() -> None:
    assert check(plan(abac_create(), tag_update())) == []


def test_data_sources_are_skipped() -> None:
    read = change("data.aws_caller_identity.current", ["read"], mode="data")

    assert check(plan(read)) == []


def test_empty_plan_passes() -> None:
    # Terraform omits resource_changes when nothing changes.
    assert check({"format_version": "1.2", "complete": True, "planned_values": {}}) == []


@pytest.mark.parametrize(
    "actions", [["delete", "create"], ["create", "delete"]], ids=["replace", "create-first"]
)
def test_replace_fails(actions: list[str]) -> None:
    replaced = change("aws_dynamodb_table.state", actions, before={}, after={})

    assert [address for address, _ in check(plan(replaced))] == ["aws_dynamodb_table.state"]


def test_delete_fails() -> None:
    deleted = change("aws_dynamodb_table.posted", ["delete"], before={})

    assert [address for address, _ in check(plan(deleted))] == ["aws_dynamodb_table.posted"]


def test_import_fails() -> None:
    imported = change("aws_sns_topic.alerts", ["no-op"])
    imported["change"]["importing"] = {"id": "arn"}

    assert len(check(plan(imported))) == 1


def test_non_tag_attribute_change_fails() -> None:
    update = tag_update()
    update["change"]["after"]["name"] = "weather-story-bot-production"

    [(address, reason)] = check(plan(update))

    assert address == "aws_sns_topic.alerts"
    assert "name" in reason


def test_unknown_non_tag_attribute_fails() -> None:
    update = tag_update(after_unknown={"last_modified": True})

    [(_, reason)] = check(plan(update))

    assert "last_modified" in reason


def test_unknown_nested_attribute_fails() -> None:
    update = tag_update(after_unknown={"environment": [{"variables": True}]})

    assert len(check(plan(update))) == 1


def test_empty_after_unknown_structure_is_not_a_change() -> None:
    # after_unknown mirrors nested blocks with empty lists and objects when nothing is unknown.
    update = tag_update(after_unknown={"environment": [{}], "tags": {}})

    assert check(plan(update)) == []


def test_changed_project_tag_fails() -> None:
    update = tag_update()
    update["change"]["after"]["tags_all"] = {**TAGGED, "Project": "weather-story-bot-production"}

    [(_, reason)] = check(plan(update))

    assert "Project" in reason


def test_unknown_tags_fail() -> None:
    update = tag_update(after_unknown={"tags_all": True})

    assert len(check(plan(update))) == 1


def test_second_abac_create_fails() -> None:
    assert [address for address, _ in check(plan(abac_create(), abac_create()))] == [ABAC_ADDRESS]


def test_other_create_fails() -> None:
    created = change("aws_s3_bucket_abac.other", ["create"], after={})

    assert [address for address, _ in check(plan(created))] == ["aws_s3_bucket_abac.other"]


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"format_version": "1.2", "errored": True, "planned_values": {}},
        {"format_version": "1.2", "complete": False, "planned_values": {}},
        {"format_version": "1.2", "values": {}},  # a state, not a plan
    ],
    ids=["empty", "errored", "incomplete", "state"],
)
def test_anything_but_a_complete_plan_fails(document: dict[str, Any]) -> None:
    assert len(check(document)) == 1


def test_removing_environment_tag_fails() -> None:
    update = tag_update()
    update["change"]["before"]["tags_all"] = TAGGED
    update["change"]["after"]["tags_all"] = TAGS

    assert len(check(plan(update))) == 1


def test_environment_tag_for_another_environment_fails() -> None:
    [(_, reason)] = check(plan(tag_update()), environment="staging")

    assert "Environment" in reason


def test_disabled_abac_create_fails() -> None:
    disabled = abac_create()
    disabled["change"]["after"]["abac_status"] = [{"status": "Disabled"}]

    assert [address for address, _ in check(plan(disabled))] == [ABAC_ADDRESS]


def run_main(monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]) -> int | str | None:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(document)))
    monkeypatch.setattr("sys.argv", ["check_tag_plan.py", "--environment", "production", "-"])
    with pytest.raises(SystemExit) as exit_info:
        check_tag_plan.main()
    return exit_info.value.code


def test_main_passes_allowed_plan(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(monkeypatch, plan(tag_update(), abac_create())) == 0
    assert "OK" in capsys.readouterr().out


def test_main_lists_offenders_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    deleted = change("aws_dynamodb_table.posted", ["delete"], before={})

    assert run_main(monkeypatch, plan(deleted)) == 1
    assert "aws_dynamodb_table.posted: delete" in capsys.readouterr().err


# A policy document that reads resource ARNs is read at apply when any of those resources has a
# pending change (even tags only), so its role policy shows `policy` as known after apply. Shapes
# below follow `terraform show -json` from Terraform 1.16 / AWS provider 6.66.
POLICY = "aws_iam_role_policy.lambda"
DOCUMENT = "data.aws_iam_policy_document.lambda"
LIVE_STATEMENTS = [
    {
        "Sid": "Logs",
        "Effect": "Allow",
        "Action": ["logs:PutLogEvents", "logs:CreateLogStream"],
        "Resource": "arn:aws:logs:us-east-2:123:log-group:/aws/lambda/weather-story-bot:*",
    },
    {
        "Sid": "Archive",
        "Effect": "Allow",
        "Action": "s3:PutObject",
        "Resource": "arn:aws:s3:::weather-story-bot-archive-123/stories/*",
    },
]


def document_statement(sid: str, actions: list[str], resources: list[str]) -> dict[str, Any]:
    return {
        "sid": sid,
        "effect": None,
        "actions": actions,
        "resources": resources,
        "not_actions": None,
        "not_resources": None,
        "principals": [],
        "not_principals": [],
        "condition": [],
    }


def deferred_document(
    statements: list[dict[str, Any]] | None = None, **after: Any
) -> dict[str, Any]:
    statements = statements or [
        document_statement(
            "Logs",
            ["logs:CreateLogStream", "logs:PutLogEvents"],
            ["arn:aws:logs:us-east-2:123:log-group:/aws/lambda/weather-story-bot:*"],
        ),
        document_statement(
            "Archive", ["s3:PutObject"], ["arn:aws:s3:::weather-story-bot-archive-123/stories/*"]
        ),
    ]
    read = change(
        DOCUMENT,
        ["read"],
        after={
            "statement": statements,
            "version": None,
            "source_policy_documents": None,
            "override_policy_documents": None,
            "policy_id": None,
            **after,
        },
        after_unknown={
            "id": True,
            "json": True,
            "minified_json": True,
            "statement": [{"actions": [False], "condition": []} for _ in statements],
        },
        mode="data",
        type="aws_iam_policy_document",
        action_reason="read_because_dependency_pending",
    )
    return read


def deferred_policy_update() -> dict[str, Any]:
    live = json.dumps({"Version": "2012-10-17", "Statement": LIVE_STATEMENTS})
    fields = {"id": "role:lambda", "name": "weather-story-bot-lambda", "role": "role"}
    return change(
        POLICY,
        ["update"],
        before={**fields, "policy": live},
        after=fields,  # unknown values are left out of `after`
        after_unknown={"policy": True},
        type="aws_iam_role_policy",
    )


def policy_plan(*changes: dict[str, Any], references: list[str] | None = None) -> dict[str, Any]:
    document = plan(*changes)
    document["configuration"] = {
        "root_module": {
            "resources": [
                {
                    "address": POLICY,
                    "mode": "managed",
                    "type": "aws_iam_role_policy",
                    "expressions": {
                        "policy": {"references": references or [f"{DOCUMENT}.json", DOCUMENT]}
                    },
                }
            ]
        }
    }
    return document


def test_deferred_policy_matching_live_policy_passes() -> None:
    assert check(policy_plan(deferred_policy_update(), deferred_document())) == []


def test_deferred_policy_with_different_action_fails() -> None:
    changed = deferred_document(
        [document_statement("Logs", ["logs:*"], ["arn:aws:logs:us-east-2:123:log-group:x:*"])]
    )

    assert [address for address, _ in check(policy_plan(deferred_policy_update(), changed))] == [
        POLICY
    ]


def test_deferred_policy_with_condition_fails() -> None:
    document = deferred_document()
    document["change"]["after"]["statement"][0]["condition"] = [
        {
            "test": "StringEquals",
            "variable": "aws:ResourceTag/Environment",
            "values": ["production"],
        }
    ]

    assert len(check(policy_plan(deferred_policy_update(), document))) == 1


def test_deferred_policy_with_source_documents_fails() -> None:
    document = deferred_document(source_policy_documents=["{}"])

    assert len(check(policy_plan(deferred_policy_update(), document))) == 1


def test_deferred_policy_with_unknown_statement_fails() -> None:
    document = deferred_document()
    document["change"]["after_unknown"]["statement"][0]["resources"] = [True]

    assert len(check(policy_plan(deferred_policy_update(), document))) == 1


def test_policy_document_read_for_another_reason_fails() -> None:
    document = deferred_document()
    del document["action_reason"]

    assert len(check(policy_plan(deferred_policy_update(), document))) == 1


def test_policy_built_from_more_than_one_document_fails() -> None:
    references = [f"{DOCUMENT}.json", DOCUMENT, "local.extra"]

    assert (
        len(
            check(policy_plan(deferred_policy_update(), deferred_document(), references=references))
        )
        == 1
    )


def test_unknown_policy_without_its_document_read_fails() -> None:
    assert len(check(policy_plan(deferred_policy_update()))) == 1


def test_deferred_policy_with_another_changed_attribute_fails() -> None:
    update = deferred_policy_update()
    update["change"]["after"]["name"] = "renamed"

    [(_, reason)] = check(policy_plan(update, deferred_document()))

    assert "name" in reason


def test_live_policy_with_extra_statement_field_fails() -> None:
    update = deferred_policy_update()
    live = json.loads(update["change"]["before"]["policy"])
    live["Statement"][0]["Condition"] = {"StringEquals": {"aws:ResourceTag/Environment": "x"}}
    update["change"]["before"]["policy"] = json.dumps(live)

    assert len(check(policy_plan(update, deferred_document()))) == 1


def test_conditions_on_both_sides_fail() -> None:
    # Conditions aren't compared, so they can't be vouched for even when both sides have one.
    update = deferred_policy_update()
    live = json.loads(update["change"]["before"]["policy"])
    live["Statement"][0]["Condition"] = {"StringEquals": {"aws:ResourceTag/Environment": "x"}}
    update["change"]["before"]["policy"] = json.dumps(live)
    document = deferred_document()
    document["change"]["after"]["statement"][0]["condition"] = [
        {"test": "StringEquals", "variable": "aws:ResourceTag/Environment", "values": ["y"]}
    ]

    assert len(check(policy_plan(update, document))) == 1


def test_deferred_policy_merging_an_unknown_document_fails() -> None:
    document = deferred_document()
    document["change"]["after_unknown"]["source_policy_documents"] = True

    assert len(check(policy_plan(deferred_policy_update(), document))) == 1
