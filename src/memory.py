from __future__ import annotations

import json
from pathlib import Path

from .models import (
    AcceptanceCriterion,
    AgentMemory,
    BaselineRecord,
    BusinessRule,
    ClarificationQuestion,
    DecisionRecord,
    EdgeCase,
    FunctionalRequirement,
    NonFunctionalRequirement,
    RequirementRunResult,
    RequirementSet,
)


def load_memory(memory_dir: str | Path, *, package_root: str | Path | None = None) -> AgentMemory:
    memory_path = Path(memory_dir) / "project_memory.json"
    if not memory_path.exists():
        return AgentMemory()

    payload = json.loads(memory_path.read_text(encoding="utf-8"))
    memory = AgentMemory(
        project_name=str(payload.get("project_name", "")),
        current_version=str(payload.get("current_version", "")),
        last_status=str(payload.get("last_status", "")),
        decisions=[DecisionRecord(**item) for item in payload.get("decisions", [])],
        history_questions=[ClarificationQuestion(**item) for item in payload.get("history_questions", [])],
        baselines=[BaselineRecord(**item) for item in payload.get("baselines", [])],
    )

    if memory.baselines:
        latest_baseline = memory.baselines[-1]
        resolved_path = _resolve_baseline_path(latest_baseline.requirements_file, memory_dir, package_root)
        if resolved_path.exists():
            memory.last_baseline = _load_requirement_set_from_file(resolved_path)

    return memory


def save_memory(memory: AgentMemory, memory_dir: str | Path) -> None:
    path = Path(memory_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "project_memory.json").write_text(
        json.dumps(memory.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_memory(
    memory: AgentMemory,
    result: RequirementRunResult,
    *,
    requirements_file: str,
) -> AgentMemory:
    updated = AgentMemory(
        project_name=result.context.project_name,
        current_version=result.requirements.version,
        last_status=result.status,
        decisions=list(memory.decisions),
        history_questions=_merge_questions(memory.history_questions, result.validation.open_questions),
        baselines=list(memory.baselines),
        last_baseline=result.requirements if result.status == "BASELINE_READY" else memory.last_baseline,
    )

    for question in result.validation.open_questions:
        if question.blocking or not question.default_option:
            continue
        updated.decisions.append(
            DecisionRecord(
                time=result.generated_at,
                type="assumption",
                content=question.default_option,
                source=question.question_id,
            )
        )

    if result.status == "BASELINE_READY":
        has_material_change = any(
            [
                result.change_summary.added_ids,
                result.change_summary.modified_ids,
                result.change_summary.removed_ids,
            ]
        )
        if has_material_change or not updated.baselines:
            updated.baselines.append(
                BaselineRecord(
                    version=result.requirements.version,
                    requirements_file=requirements_file,
                    created_at=result.generated_at,
                )
            )

    updated.decisions = _deduplicate_decisions(updated.decisions)
    updated.baselines = _deduplicate_baselines(updated.baselines)
    return updated


def _merge_questions(
    previous: list[ClarificationQuestion],
    current: list[ClarificationQuestion],
) -> list[ClarificationQuestion]:
    seen: set[tuple[str, str]] = set()
    merged: list[ClarificationQuestion] = []
    for question in [*previous, *current]:
        signature = (question.question_id, question.question)
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(question)
    return merged


def _deduplicate_decisions(decisions: list[DecisionRecord]) -> list[DecisionRecord]:
    seen: set[tuple[str, str]] = set()
    result: list[DecisionRecord] = []
    for decision in decisions:
        signature = (decision.content, decision.source)
        if signature in seen:
            continue
        seen.add(signature)
        result.append(decision)
    return result


def _resolve_baseline_path(
    requirements_file: str,
    memory_dir: str | Path,
    package_root: str | Path | None,
) -> Path:
    path = Path(requirements_file)
    if path.is_absolute():
        return path

    if package_root:
        candidate = Path(package_root) / path
        if candidate.exists():
            return candidate

    return Path(memory_dir).parent / path


def _load_requirement_set_from_file(path: Path) -> RequirementSet:
    payload = json.loads(path.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    return RequirementSet(
        project_name=str(project.get("name", "")),
        version=str(project.get("version", "")),
        status=str(project.get("status", "")),
        functional_requirements=[FunctionalRequirement(**item) for item in payload.get("functional_requirements", [])],
        non_functional_requirements=[
            NonFunctionalRequirement(**item) for item in payload.get("non_functional_requirements", [])
        ],
        business_rules=[BusinessRule(**item) for item in payload.get("business_rules", [])],
        edge_cases=[EdgeCase(**item) for item in payload.get("edge_cases", [])],
        acceptance_criteria=[AcceptanceCriterion(**item) for item in payload.get("acceptance_criteria", [])],
        open_questions=[ClarificationQuestion(**item) for item in payload.get("open_questions", [])],
        assumptions=[str(item) for item in payload.get("assumptions", [])],
    )


def _deduplicate_baselines(baselines: list[BaselineRecord]) -> list[BaselineRecord]:
    seen: set[tuple[str, str]] = set()
    result: list[BaselineRecord] = []
    for baseline in baselines:
        signature = (baseline.version, baseline.requirements_file)
        if signature in seen:
            continue
        seen.add(signature)
        result.append(baseline)
    return result
