from __future__ import annotations

from .models import ChangeSummary, RequirementSet


def diff_requirement_sets(previous: RequirementSet | None, current: RequirementSet) -> ChangeSummary:
    if not previous:
        return ChangeSummary(
            added_ids=_collect_all_ids(current),
            modified_ids=[],
            removed_ids=[],
            reason="initial_baseline",
            downstream_impact="建议下游设计、开发、测试模块以当前基线为准。",
        )

    previous_items = _serialize_items(previous)
    current_items = _serialize_items(current)

    previous_ids = set(previous_items)
    current_ids = set(current_items)

    added_ids = sorted(current_ids - previous_ids)
    removed_ids = sorted(previous_ids - current_ids)
    modified_ids = sorted(
        requirement_id
        for requirement_id in previous_ids & current_ids
        if previous_items[requirement_id] != current_items[requirement_id]
    )

    if added_ids or removed_ids or modified_ids:
        reason = "requirements_updated"
        downstream_impact = _infer_downstream_impact(added_ids, modified_ids, removed_ids)
    else:
        reason = "no_material_change"
        downstream_impact = "当前需求基线与上一版本一致，下游无需重新同步。"

    return ChangeSummary(
        added_ids=added_ids,
        modified_ids=modified_ids,
        removed_ids=removed_ids,
        reason=reason,
        downstream_impact=downstream_impact,
    )


def resolve_next_version(
    previous_version: str,
    change_summary: ChangeSummary,
    status: str,
    draft_version: str,
) -> str:
    if status != "BASELINE_READY":
        return previous_version or draft_version

    if not previous_version:
        return "v1.0"

    if not any([change_summary.added_ids, change_summary.modified_ids, change_summary.removed_ids]):
        return previous_version

    major, minor = _parse_version(previous_version)
    if _has_core_requirement_changes(change_summary):
        return f"v{major + 1}.0"
    return f"v{major}.{minor + 1}"


def _serialize_items(requirements: RequirementSet) -> dict[str, tuple]:
    serialized: dict[str, tuple] = {}

    for item in requirements.functional_requirements:
        serialized[item.id] = (
            item.title,
            item.description,
            tuple(item.actors),
            tuple(item.preconditions),
            tuple(item.main_flow),
            tuple(item.alternate_flow),
            tuple(item.postconditions),
            item.priority,
            tuple(item.source),
        )

    for item in requirements.non_functional_requirements:
        serialized[item.id] = (
            item.category,
            item.title,
            item.description,
            item.metric,
            tuple(item.scope),
            item.priority,
            tuple(item.source),
        )

    for item in requirements.business_rules:
        serialized[item.id] = (
            item.title,
            item.description,
            item.priority,
            tuple(item.source),
        )

    for item in requirements.edge_cases:
        serialized[item.id] = (
            item.title,
            item.description,
            tuple(item.related_requirement_ids),
            tuple(item.source),
        )

    for item in requirements.acceptance_criteria:
        serialized[item.id] = (
            item.requirement_id,
            item.scenario,
            item.given,
            item.when,
            item.then,
            tuple(item.source),
        )

    return serialized


def _collect_all_ids(requirements: RequirementSet) -> list[str]:
    return sorted(_serialize_items(requirements))


def _infer_downstream_impact(added_ids: list[str], modified_ids: list[str], removed_ids: list[str]) -> str:
    impacted_ids = added_ids + modified_ids + removed_ids
    if any(identifier.startswith(("FR-", "NFR-", "BR-", "EC-")) for identifier in impacted_ids):
        return "建议设计、开发、测试模块重新同步需求基线。"
    if any(identifier.startswith("AC-") for identifier in impacted_ids):
        return "建议测试模块同步最新验收标准。"
    return "建议下游模块检查是否需要同步更新。"


def _parse_version(value: str) -> tuple[int, int]:
    if not value.startswith("v") or "." not in value:
        return 0, 0
    major_text, minor_text = value[1:].split(".", 1)
    try:
        return int(major_text), int(minor_text)
    except ValueError:
        return 0, 0


def _has_core_requirement_changes(change_summary: ChangeSummary) -> bool:
    impacted_ids = change_summary.added_ids + change_summary.modified_ids + change_summary.removed_ids
    return any(identifier.startswith(("FR-", "NFR-", "BR-", "EC-")) for identifier in impacted_ids)
