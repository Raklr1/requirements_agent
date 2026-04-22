from __future__ import annotations

import re
from typing import Any

from .models import (
    AcceptanceCriterion,
    BusinessRule,
    ClarificationQuestion,
    EdgeCase,
    FunctionalRequirement,
    NonFunctionalRequirement,
    RequirementDraft,
    RequirementSet,
)


PLACEHOLDER_TEXT = "TBD"
VALID_PRIORITIES = {"high", "medium", "low"}


def normalize_requirements(
    draft: RequirementDraft,
    previous: RequirementSet | None = None,
    *,
    project_name: str = "",
    version: str = "",
) -> RequirementSet:
    previous_maps = _build_previous_maps(previous)

    functional_requirements = _normalize_functional_requirements(
        draft.functional_requirements,
        previous_maps.get("FR", {}),
    )
    non_functional_requirements = _normalize_non_functional_requirements(
        draft.non_functional_requirements,
        previous_maps.get("NFR", {}),
    )
    business_rules = _normalize_business_rules(
        draft.business_rules,
        previous_maps.get("BR", {}),
    )
    edge_cases = _normalize_edge_cases(
        draft.edge_cases,
        previous_maps.get("EC", {}),
    )

    title_to_requirement_id = {
        _canonical_text(requirement.title): requirement.id for requirement in functional_requirements
    }
    acceptance_criteria = _normalize_acceptance_criteria(
        draft.acceptance_criteria,
        previous_maps.get("AC", {}),
        title_to_requirement_id,
    )
    _attach_acceptance_ids(functional_requirements, acceptance_criteria)

    return RequirementSet(
        project_name=project_name,
        version=version,
        functional_requirements=functional_requirements,
        non_functional_requirements=non_functional_requirements,
        business_rules=business_rules,
        edge_cases=edge_cases,
        acceptance_criteria=acceptance_criteria,
        open_questions=_normalize_questions(draft.open_questions),
        assumptions=list(dict.fromkeys(draft.assumptions)),
    )


def _normalize_functional_requirements(
    requirements: list[FunctionalRequirement],
    previous_map: dict[str, str],
) -> list[FunctionalRequirement]:
    normalized: list[FunctionalRequirement] = []
    next_number = _next_sequence(previous_map.values())
    seen_fingerprints: set[str] = set()

    for requirement in requirements:
        requirement.title = requirement.title.strip() or PLACEHOLDER_TEXT
        requirement.description = requirement.description.strip() or f"系统应支持{requirement.title}。"
        requirement.actors = _normalize_list(requirement.actors, placeholder="用户")
        requirement.preconditions = _normalize_list(requirement.preconditions, placeholder=PLACEHOLDER_TEXT)
        requirement.main_flow = _normalize_list(requirement.main_flow, placeholder=PLACEHOLDER_TEXT)
        requirement.alternate_flow = _normalize_list(requirement.alternate_flow, placeholder=PLACEHOLDER_TEXT)
        requirement.postconditions = _normalize_list(requirement.postconditions, placeholder=PLACEHOLDER_TEXT)
        requirement.priority = _normalize_priority(requirement.priority)
        requirement.source = _normalize_list(requirement.source, placeholder="source:unknown")
        requirement.status = requirement.status or "proposed"

        fingerprint = _requirement_fingerprint("FR", requirement.title, requirement.description)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        requirement.id = previous_map.get(fingerprint, _format_id("FR", next_number))
        if fingerprint not in previous_map:
            next_number += 1
        requirement.acceptance_ids = []
        normalized.append(requirement)

    return normalized


def _normalize_non_functional_requirements(
    requirements: list[NonFunctionalRequirement],
    previous_map: dict[str, str],
) -> list[NonFunctionalRequirement]:
    normalized: list[NonFunctionalRequirement] = []
    next_number = _next_sequence(previous_map.values())
    seen_fingerprints: set[str] = set()

    for requirement in requirements:
        requirement.category = requirement.category.strip().lower() or "general"
        requirement.title = requirement.title.strip() or PLACEHOLDER_TEXT
        requirement.description = requirement.description.strip() or f"系统应满足{requirement.title}。"
        requirement.metric = requirement.metric.strip() or "metric_to_be_confirmed"
        requirement.scope = _normalize_list(requirement.scope, placeholder="全系统")
        requirement.priority = _normalize_priority(requirement.priority)
        requirement.source = _normalize_list(requirement.source, placeholder="source:unknown")

        fingerprint = _requirement_fingerprint("NFR", requirement.category, requirement.title, requirement.description)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        requirement.id = previous_map.get(fingerprint, _format_id("NFR", next_number))
        if fingerprint not in previous_map:
            next_number += 1
        normalized.append(requirement)

    return normalized


def _normalize_business_rules(
    rules: list[BusinessRule],
    previous_map: dict[str, str],
) -> list[BusinessRule]:
    normalized: list[BusinessRule] = []
    next_number = _next_sequence(previous_map.values())
    seen_fingerprints: set[str] = set()

    for rule in rules:
        rule.title = rule.title.strip() or PLACEHOLDER_TEXT
        rule.description = rule.description.strip() or rule.title
        rule.priority = _normalize_priority(rule.priority)
        rule.source = _normalize_list(rule.source, placeholder="source:unknown")
        rule.status = rule.status or "proposed"

        fingerprint = _requirement_fingerprint("BR", rule.title, rule.description)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        rule.id = previous_map.get(fingerprint, _format_id("BR", next_number))
        if fingerprint not in previous_map:
            next_number += 1
        normalized.append(rule)

    return normalized


def _normalize_edge_cases(
    edge_cases: list[EdgeCase],
    previous_map: dict[str, str],
) -> list[EdgeCase]:
    normalized: list[EdgeCase] = []
    next_number = _next_sequence(previous_map.values())
    seen_fingerprints: set[str] = set()

    for edge_case in edge_cases:
        edge_case.title = edge_case.title.strip() or PLACEHOLDER_TEXT
        edge_case.description = edge_case.description.strip() or edge_case.title
        edge_case.related_requirement_ids = _normalize_list(edge_case.related_requirement_ids)
        edge_case.source = _normalize_list(edge_case.source, placeholder="source:unknown")
        edge_case.status = edge_case.status or "proposed"

        fingerprint = _requirement_fingerprint("EC", edge_case.title, edge_case.description)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        edge_case.id = previous_map.get(fingerprint, _format_id("EC", next_number))
        if fingerprint not in previous_map:
            next_number += 1
        normalized.append(edge_case)

    return normalized


def _normalize_acceptance_criteria(
    acceptance_criteria: list[AcceptanceCriterion],
    previous_map: dict[str, str],
    title_to_requirement_id: dict[str, str],
) -> list[AcceptanceCriterion]:
    normalized: list[AcceptanceCriterion] = []
    next_number = _next_sequence(previous_map.values())
    seen_fingerprints: set[str] = set()

    for criterion in acceptance_criteria:
        requirement_id = criterion.requirement_id.strip()
        if not requirement_id and criterion.linked_requirement_title:
            requirement_id = title_to_requirement_id.get(_canonical_text(criterion.linked_requirement_title), "")
        criterion.requirement_id = requirement_id
        criterion.scenario = criterion.scenario.strip() or PLACEHOLDER_TEXT
        criterion.given = criterion.given.strip() or PLACEHOLDER_TEXT
        criterion.when = criterion.when.strip() or PLACEHOLDER_TEXT
        criterion.then = criterion.then.strip() or PLACEHOLDER_TEXT
        criterion.source = _normalize_list(criterion.source, placeholder="source:unknown")

        fingerprint = _requirement_fingerprint(
            "AC",
            criterion.requirement_id,
            criterion.scenario,
            criterion.given,
            criterion.when,
            criterion.then,
        )
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        criterion.id = previous_map.get(fingerprint, _format_id("AC", next_number))
        if fingerprint not in previous_map:
            next_number += 1
        normalized.append(criterion)

    return normalized


def _normalize_questions(questions: list[ClarificationQuestion]) -> list[ClarificationQuestion]:
    normalized: list[ClarificationQuestion] = []
    seen_ids: set[str] = set()
    next_number = 1

    for question in questions:
        question.question = question.question.strip()
        if not question.question:
            continue
        question.reason = question.reason.strip() or PLACEHOLDER_TEXT
        question.default_option = question.default_option.strip()
        if not question.question_id:
            question.question_id = _format_id("Q", next_number)
        next_number += 1
        if question.question_id in seen_ids:
            continue
        seen_ids.add(question.question_id)
        normalized.append(question)

    return normalized


def _attach_acceptance_ids(
    requirements: list[FunctionalRequirement],
    acceptance_criteria: list[AcceptanceCriterion],
) -> None:
    requirement_map = {requirement.id: requirement for requirement in requirements}
    for criterion in acceptance_criteria:
        if not criterion.requirement_id:
            continue
        requirement = requirement_map.get(criterion.requirement_id)
        if not requirement:
            continue
        requirement.acceptance_ids.append(criterion.id)

    for requirement in requirements:
        requirement.acceptance_ids = list(dict.fromkeys(requirement.acceptance_ids))


def _build_previous_maps(previous: RequirementSet | None) -> dict[str, dict[str, str]]:
    if not previous:
        return {"FR": {}, "NFR": {}, "BR": {}, "EC": {}, "AC": {}}

    return {
        "FR": {
            _requirement_fingerprint("FR", item.title, item.description): item.id
            for item in previous.functional_requirements
        },
        "NFR": {
            _requirement_fingerprint("NFR", item.category, item.title, item.description): item.id
            for item in previous.non_functional_requirements
        },
        "BR": {
            _requirement_fingerprint("BR", item.title, item.description): item.id
            for item in previous.business_rules
        },
        "EC": {
            _requirement_fingerprint("EC", item.title, item.description): item.id
            for item in previous.edge_cases
        },
        "AC": {
            _requirement_fingerprint("AC", item.requirement_id, item.scenario, item.given, item.when, item.then): item.id
            for item in previous.acceptance_criteria
        },
    }


def _normalize_list(values: list[str], *, placeholder: str = "") -> list[str]:
    normalized: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    if normalized:
        return normalized
    return [placeholder] if placeholder else []


def _normalize_priority(value: str) -> str:
    priority = value.strip().lower()
    return priority if priority in VALID_PRIORITIES else "medium"


def _requirement_fingerprint(*values: Any) -> str:
    return "|".join(_canonical_text(str(value)) for value in values if str(value).strip())


def _canonical_text(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[^\w\u4e00-\u9fff ]+", "", lowered, flags=re.UNICODE)
    return lowered.strip()


def _next_sequence(existing_ids) -> int:
    max_value = 0
    for item in existing_ids:
        match = re.search(r"(\d+)$", item)
        if not match:
            continue
        max_value = max(max_value, int(match.group(1)))
    return max_value + 1


def _format_id(prefix: str, value: int) -> str:
    return f"{prefix}-{value:03d}"
