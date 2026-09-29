"""Check that a saved Terraform plan only moves, adds the Environment tag and enables bucket ABAC.

Phase 2.0's Gate 1 plan touches nearly every production resource with a tag-only update. Reading
~30 tag diffs by eye is how a real change slips through, so this reads the plan's JSON and fails,
listing the offenders, on any resource change other than:

- `no-op`: unchanged, or a move (`previous_address` set)
- `update`, moved or not, where only `tags` / `tags_all` differ (counting `after_unknown`) and the
  only tag change is adding `Environment` with this environment's value
- `create` of `aws_s3_bucket_abac.archive` with ABAC enabled, at most once
- `update` of an `aws_iam_role_policy` whose only change is `policy` becoming unknown, because its
  one `aws_iam_policy_document` is read at apply (`read_because_dependency_pending`: the document
  takes ARNs from resources that are only getting tags). Its statements must be known and match the
  live policy exactly, with nothing but Sid, Effect, Action and Resource

Data sources are skipped. Anything that isn't a complete, error-free plan fails. It only reads the
plan, so it's a read-only local tool:

    terraform -chdir=infra show -json deploy-production.tfplan | \\
        uv run python scripts/check_tag_plan.py --environment production -

`make check-plan ENV=production` runs exactly that. Exit 0 on pass, 1 with the offenders listed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from typing import Any

ABAC_ADDRESS = "aws_s3_bucket_abac.archive"
TAG_ATTRIBUTES = frozenset({"tags", "tags_all"})
ALLOWED_TAG_KEY = "Environment"
POLICY_DOCUMENT_PREFIX = "data.aws_iam_policy_document."
# Document and statement fields the deferred-policy comparison doesn't model; any value fails it.
DOCUMENT_EXTRAS = ("source_policy_documents", "override_policy_documents", "policy_id", "version")
STATEMENT_EXTRAS = ("not_actions", "not_resources", "principals", "not_principals", "condition")


def offenders(plan: Mapping[str, Any], environment: str) -> list[tuple[str, str]]:
    """Every resource change the gate doesn't allow, as (address, reason)."""
    # Terraform omits resource_changes when nothing changes, so an empty plan is recognised by
    # planned_values. Anything else (a state, an errored or partial plan) can't be vouched for.
    if "planned_values" not in plan or plan.get("errored") or plan.get("complete") is False:
        return [("(plan)", "not a complete, error-free plan from terraform show -json")]
    found: list[tuple[str, str]] = []
    abac_creates = 0
    for resource in plan.get("resource_changes", []):
        if resource.get("mode") == "data":
            continue
        address = resource["address"]
        change = resource["change"]
        actions = change["actions"]
        if change.get("importing"):
            found.append((address, "import"))
        elif actions == ["no-op"]:
            continue
        elif actions == ["update"]:
            reason = _tag_only_update(change, environment)
            if reason and _is_deferred_policy(resource):
                reason = _deferred_policy_differs(resource, plan)
            if reason:
                found.append((address, reason))
        elif actions == ["create"] and address == ABAC_ADDRESS:
            abac_creates += 1
            if abac_creates > 1:
                found.append((address, "second create"))
            elif _abac_status(change) != "Enabled":
                found.append((address, "creates ABAC not Enabled"))
        else:
            found.append((address, "/".join(actions)))
    return found


def _tag_only_update(change: Mapping[str, Any], environment: str) -> str | None:
    """Why an update isn't just adding the Environment tag, or None if it is."""
    before = change["before"] or {}
    after = change["after"] or {}
    unknown = change.get("after_unknown") or {}
    changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    changed |= {key for key, value in unknown.items() if _has_unknown(value)}
    if other := sorted(changed - TAG_ATTRIBUTES):
        return "changes " + ", ".join(other)
    for attribute in sorted(changed):
        if _has_unknown(unknown.get(attribute)):
            return f"{attribute} unknown until apply"
        old = before.get(attribute) or {}
        new = after.get(attribute) or {}
        keys = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
        if other_tags := sorted(keys - {ALLOWED_TAG_KEY}):
            return f"{attribute} changes " + ", ".join(other_tags)
        if keys and (ALLOWED_TAG_KEY in old or new.get(ALLOWED_TAG_KEY) != environment):
            return f"{attribute} doesn't just add {ALLOWED_TAG_KEY} = {environment}"
    return None


def _is_deferred_policy(resource: Mapping[str, Any]) -> bool:
    """A role policy update whose only change is `policy` becoming unknown."""
    change = resource["change"]
    before = change["before"] or {}
    after = change["after"] or {}
    unknown = change.get("after_unknown") or {}
    changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    return (
        resource.get("type") == "aws_iam_role_policy"
        and changed == {"policy"}
        and {key for key, value in unknown.items() if _has_unknown(value)} == {"policy"}
    )


def _deferred_policy_differs(resource: Mapping[str, Any], plan: Mapping[str, Any]) -> str | None:
    """Why a deferred role policy might not come out as the live one, or None if it will."""
    config = {
        r["address"]: r
        for r in plan.get("configuration", {}).get("root_module", {}).get("resources", [])
    }
    references = (
        config.get(resource["address"], {})
        .get("expressions", {})
        .get("policy", {})
        .get("references", [])
    )
    documents = {ref.removesuffix(".json") for ref in references}
    if len(documents) != 1 or not next(iter(documents)).startswith(POLICY_DOCUMENT_PREFIX):
        return "policy unknown until apply, and not from exactly one policy document"
    [document] = documents
    reads = [r for r in plan.get("resource_changes", []) if r["address"] == document]
    if len(reads) != 1 or reads[0].get("action_reason") != "read_because_dependency_pending":
        return f"policy unknown until apply, and {document} isn't a deferred read"
    read = reads[0]["change"]
    planned = read["after"] or {}
    # Only the rendered JSON may be unknown; an unknown statement or merged document isn't checked.
    unknown = {k for k, v in (read.get("after_unknown") or {}).items() if _has_unknown(v)}
    if unknown - {"id", "json", "minified_json"}:
        return f"{document} has values unknown until apply"
    if any(planned.get(key) for key in DOCUMENT_EXTRAS):
        return f"{document} merges or overrides other documents"
    planned_statements = _document_statements(planned)
    live_statements = _live_statements(json.loads(resource["change"]["before"]["policy"]))
    if planned_statements is None or live_statements is None:
        return f"{document} or the live policy has fields this check doesn't compare"
    if planned_statements != live_statements:
        return f"{document} differs from the live policy"
    return None


def _document_statements(document: Mapping[str, Any]) -> list[tuple[Any, ...]] | None:
    statements = []
    for statement in document.get("statement") or []:
        if any(statement.get(key) for key in STATEMENT_EXTRAS):
            return None
        statements.append(
            (
                statement.get("sid"),
                statement.get("effect") or "Allow",
                sorted(statement.get("actions") or []),
                sorted(statement.get("resources") or []),
            )
        )
    return sorted(statements, key=repr)


def _live_statements(policy: Mapping[str, Any]) -> list[tuple[Any, ...]] | None:
    statements = []
    for statement in policy.get("Statement", []):
        if set(statement) - {"Sid", "Effect", "Action", "Resource"}:
            return None
        statements.append(
            (
                statement.get("Sid"),
                statement.get("Effect"),
                sorted(_as_list(statement.get("Action"))),
                sorted(_as_list(statement.get("Resource"))),
            )
        )
    return sorted(statements, key=repr)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _abac_status(change: Mapping[str, Any]) -> str | None:
    blocks = (change["after"] or {}).get("abac_status") or [{}]
    return blocks[0].get("status")


def _has_unknown(value: Any) -> bool:
    """after_unknown marks unknown values True and mirrors nested structure otherwise."""
    if isinstance(value, Mapping):
        return any(_has_unknown(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_unknown(v) for v in value)
    return value is True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--environment", required=True, help="the Environment tag value the plan must add"
    )
    parser.add_argument("plan", help="`terraform show -json` output, or - for stdin")
    args = parser.parse_args()
    if args.plan == "-":
        plan = json.load(sys.stdin)
    else:
        with open(args.plan) as f:
            plan = json.load(f)
    found = offenders(plan, args.environment)
    for address, reason in found:
        print(f"{address}: {reason}", file=sys.stderr)
    if found:
        print(
            f"{len(found)} change(s) are not moves, tag-only updates or {ABAC_ADDRESS}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        f"OK: only moves, Environment = {args.environment} tag additions, bucket ABAC"
        " and unchanged deferred policies"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
