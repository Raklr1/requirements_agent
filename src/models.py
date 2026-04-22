from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any


def to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        result: dict[str, Any] = {}
        for item in fields(value):
            if item.metadata.get("serialize", True) is False:
                continue
            result[item.name] = to_serializable(getattr(value, item.name))
        return result

    if isinstance(value, dict):
        return {key: to_serializable(item) for key, item in value.items()}

    if isinstance(value, list):
        return [to_serializable(item) for item in value]

    return value


@dataclass(slots=True)
class SourceDocument:
    name: str
    path: str
    content: str
    sections: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class ProjectContext:
    project_name: str = ""
    project_goal: str = ""
    target_users: list[str] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    prototype_notes: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    feedback_notes: list[str] = field(default_factory=list)
    source_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    documents: dict[str, SourceDocument] = field(default_factory=dict)
    missing_inputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class ClarificationQuestion:
    question_id: str = ""
    question: str = ""
    reason: str = ""
    default_option: str = ""
    blocking: bool = False

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class FunctionalRequirement:
    id: str = ""
    title: str = ""
    description: str = ""
    actors: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    main_flow: list[str] = field(default_factory=list)
    alternate_flow: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    priority: str = "medium"
    source: list[str] = field(default_factory=list)
    acceptance_ids: list[str] = field(default_factory=list)
    status: str = "proposed"

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class NonFunctionalRequirement:
    id: str = ""
    category: str = ""
    title: str = ""
    description: str = ""
    metric: str = ""
    scope: list[str] = field(default_factory=list)
    priority: str = "medium"
    source: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class BusinessRule:
    id: str = ""
    title: str = ""
    description: str = ""
    priority: str = "medium"
    source: list[str] = field(default_factory=list)
    status: str = "proposed"

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class EdgeCase:
    id: str = ""
    title: str = ""
    description: str = ""
    related_requirement_ids: list[str] = field(default_factory=list)
    source: list[str] = field(default_factory=list)
    status: str = "proposed"

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class AcceptanceCriterion:
    id: str = ""
    requirement_id: str = ""
    scenario: str = ""
    given: str = ""
    when: str = ""
    then: str = ""
    source: list[str] = field(default_factory=list)
    linked_requirement_title: str = field(default="", metadata={"serialize": False})

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class RequirementDraft:
    functional_requirements: list[FunctionalRequirement] = field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = field(default_factory=list)
    business_rules: list[BusinessRule] = field(default_factory=list)
    edge_cases: list[EdgeCase] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    open_questions: list[ClarificationQuestion] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class RequirementSet:
    project_name: str = ""
    version: str = ""
    status: str = "proposed"
    functional_requirements: list[FunctionalRequirement] = field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = field(default_factory=list)
    business_rules: list[BusinessRule] = field(default_factory=list)
    edge_cases: list[EdgeCase] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    open_questions: list[ClarificationQuestion] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def iter_all_requirement_items(self) -> list[FunctionalRequirement | NonFunctionalRequirement | BusinessRule | EdgeCase]:
        return [
            *self.functional_requirements,
            *self.non_functional_requirements,
            *self.business_rules,
            *self.edge_cases,
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": {
                "name": self.project_name,
                "version": self.version,
                "status": self.status,
            },
            "functional_requirements": [item.to_dict() for item in self.functional_requirements],
            "non_functional_requirements": [item.to_dict() for item in self.non_functional_requirements],
            "business_rules": [item.to_dict() for item in self.business_rules],
            "edge_cases": [item.to_dict() for item in self.edge_cases],
            "acceptance_criteria": [item.to_dict() for item in self.acceptance_criteria],
            "open_questions": [item.to_dict() for item in self.open_questions],
            "assumptions": list(self.assumptions),
        }


@dataclass(slots=True)
class ValidationIssue:
    issue_id: str = ""
    severity: str = "medium"
    category: str = ""
    requirement_id: str | None = None
    summary: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class ValidationResult:
    passed: bool = False
    status: str = "BLOCKED"
    issues: list[ValidationIssue] = field(default_factory=list)
    open_questions: list[ClarificationQuestion] = field(default_factory=list)
    risk_summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class DecisionRecord:
    time: str
    type: str
    content: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class BaselineRecord:
    version: str
    requirements_file: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class AgentMemory:
    project_name: str = ""
    current_version: str = ""
    last_status: str = ""
    decisions: list[DecisionRecord] = field(default_factory=list)
    history_questions: list[ClarificationQuestion] = field(default_factory=list)
    baselines: list[BaselineRecord] = field(default_factory=list)
    last_baseline: RequirementSet | None = field(default=None, metadata={"serialize": False})

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "current_version": self.current_version,
            "last_status": self.last_status,
            "decisions": [item.to_dict() for item in self.decisions],
            "history_questions": [item.to_dict() for item in self.history_questions],
            "baselines": [item.to_dict() for item in self.baselines],
        }


@dataclass(slots=True)
class ChangeSummary:
    added_ids: list[str] = field(default_factory=list)
    modified_ids: list[str] = field(default_factory=list)
    removed_ids: list[str] = field(default_factory=list)
    reason: str = ""
    downstream_impact: str = ""

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(self)


@dataclass(slots=True)
class RequirementRunResult:
    context: ProjectContext
    requirements: RequirementSet
    validation: ValidationResult
    change_summary: ChangeSummary
    generated_at: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "context": self.context.to_dict(),
            "requirements": self.requirements.to_dict(),
            "validation": self.validation.to_dict(),
            "change_summary": self.change_summary.to_dict(),
            "generated_at": self.generated_at,
            "status": self.status,
        }
