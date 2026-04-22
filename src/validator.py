from __future__ import annotations

from collections import Counter

from .config import RuleSettings
from .models import (
    ClarificationQuestion,
    ProjectContext,
    RequirementSet,
    ValidationIssue,
    ValidationResult,
)


CORE_ACTION_KEYWORDS = ("登录", "注册", "搜索", "提交", "报名", "取消报名", "审核", "发布", "查看详情")
CONFLICT_PAIRS = (
    ("必须登录", "无需登录"),
    ("允许重复报名", "不能重复报名"),
    ("游客可以报名", "游客不能报名"),
)


def validate_requirements(
    requirements: RequirementSet,
    context: ProjectContext,
    rules: RuleSettings | None = None,
) -> ValidationResult:
    rule_settings = rules or RuleSettings()
    issues: list[ValidationIssue] = []

    issues.extend(_check_completeness(requirements, context))
    issues.extend(_check_consistency(requirements))
    issues.extend(_check_ambiguity(requirements, rule_settings))
    issues.extend(_check_testability(requirements))
    issues.extend(_check_reference_integrity(requirements))

    questions = list(requirements.open_questions)
    questions.extend(_questions_from_ambiguity(issues))
    questions = _deduplicate_questions(questions)

    if context.missing_inputs:
        status = "BLOCKED"
    elif any(question.blocking for question in questions):
        status = "DRAFT_READY"
    elif any(issue.severity in {"critical", "high"} for issue in issues):
        status = "REVISION_REQUIRED"
    else:
        status = "BASELINE_READY"

    issues = _assign_issue_ids(issues)
    risk_summary = dict(Counter(issue.severity for issue in issues))
    return ValidationResult(
        passed=status == "BASELINE_READY",
        status=status,
        issues=issues,
        open_questions=questions,
        risk_summary=risk_summary,
    )


def _check_completeness(requirements: RequirementSet, context: ProjectContext) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if context.target_users and not context.scenarios:
        issues.append(
            ValidationIssue(
                severity="high",
                category="completeness",
                requirement_id=None,
                summary="已识别目标用户，但未提取到对应核心场景。",
                suggestion="补充或确认关键用户场景，并将其映射到功能需求。",
            )
        )

    if not requirements.functional_requirements:
        issues.append(
            ValidationIssue(
                severity="critical",
                category="completeness",
                requirement_id=None,
                summary="未生成任何功能需求。",
                suggestion="检查输入解析与需求抽取逻辑，确保核心功能范围被正确提取。",
            )
        )

    for requirement in requirements.functional_requirements:
        if requirement.priority == "high" and not requirement.acceptance_ids:
            issues.append(
                ValidationIssue(
                    severity="high",
                    category="completeness",
                    requirement_id=requirement.id,
                    summary="高优先级功能缺少验收标准关联。",
                    suggestion="为该功能补充至少一条 Given-When-Then 验收标准。",
                )
            )

    input_text = "\n".join(document.content for document in context.documents.values())
    extracted_text = "\n".join(
        f"{item.title} {item.description}" for item in requirements.functional_requirements
    )
    for keyword in CORE_ACTION_KEYWORDS:
        if keyword in input_text and not _action_covered(keyword, extracted_text):
            issues.append(
                ValidationIssue(
                    severity="medium",
                    category="completeness",
                    requirement_id=None,
                    summary=f"输入材料中出现“{keyword}”，但需求项未明显覆盖该核心动作。",
                    suggestion=f"检查是否需要为“{keyword}”补充独立功能需求或补充到现有需求描述中。",
                )
            )

    return issues


def _check_consistency(requirements: RequirementSet) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    combined_text = "\n".join(
        [
            *(f"{item.title} {item.description}" for item in requirements.functional_requirements),
            *(f"{item.title} {item.description}" for item in requirements.business_rules),
        ]
    )

    for positive_text, negative_text in CONFLICT_PAIRS:
        if positive_text in combined_text and negative_text in combined_text:
            issues.append(
                ValidationIssue(
                    severity="high",
                    category="consistency",
                    requirement_id=None,
                    summary=f"检测到潜在冲突描述：同时出现“{positive_text}”和“{negative_text}”。",
                    suggestion="确认角色权限或流程条件，统一需求描述口径。",
                )
            )

    return issues


def _check_ambiguity(
    requirements: RequirementSet,
    rules: RuleSettings,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    ambiguity_terms = rules.ambiguity_terms or []

    for term in ambiguity_terms:
        for requirement in requirements.iter_all_requirement_items():
            text = " ".join(
                filter(
                    None,
                    [
                        getattr(requirement, "title", ""),
                        getattr(requirement, "description", ""),
                    ],
                )
            )
            if term in text:
                issues.append(
                    ValidationIssue(
                        severity="medium",
                        category="ambiguity",
                        requirement_id=requirement.id,
                        summary=f"需求描述包含歧义词“{term}”。",
                        suggestion="将该描述量化，或转为待确认问题并给出保守默认方案。",
                    )
                )

    return issues


def _check_testability(requirements: RequirementSet) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for requirement in requirements.functional_requirements:
        if not requirement.main_flow or requirement.main_flow == ["TBD"]:
            issues.append(
                ValidationIssue(
                    severity="high",
                    category="testability",
                    requirement_id=requirement.id,
                    summary="功能需求缺少明确主流程。",
                    suggestion="补充清晰的操作步骤，使其可映射为测试用例。",
                )
            )
        if not requirement.postconditions or requirement.postconditions == ["TBD"]:
            issues.append(
                ValidationIssue(
                    severity="high",
                    category="testability",
                    requirement_id=requirement.id,
                    summary="功能需求缺少可观察结果。",
                    suggestion="补充成功后的系统状态变化或用户可见结果。",
                )
            )

    for requirement in requirements.non_functional_requirements:
        if not requirement.metric or requirement.metric == "metric_to_be_confirmed":
            issues.append(
                ValidationIssue(
                    severity="medium",
                    category="testability",
                    requirement_id=requirement.id,
                    summary="非功能需求缺少明确指标。",
                    suggestion="补充可量化的指标或验收口径。",
                )
            )

    for criterion in requirements.acceptance_criteria:
        if not all([criterion.requirement_id, criterion.given, criterion.when, criterion.then]):
            issues.append(
                ValidationIssue(
                    severity="high",
                    category="testability",
                    requirement_id=criterion.requirement_id or None,
                    summary="验收标准未形成完整的 Given-When-Then 结构。",
                    suggestion="补充 requirement_id 以及 Given/When/Then 字段，确保验收可执行。",
                )
            )

    return issues


def _check_reference_integrity(requirements: RequirementSet) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for requirement in requirements.iter_all_requirement_items():
        sources = getattr(requirement, "source", [])
        if not sources:
            issues.append(
                ValidationIssue(
                    severity="high",
                    category="reference_integrity",
                    requirement_id=requirement.id,
                    summary="需求项缺少来源引用。",
                    suggestion="补充输入文档与章节来源，保证需求可追踪。",
                )
            )
            continue
        if any(source == "source:unknown" for source in sources):
            issues.append(
                ValidationIssue(
                    severity="medium",
                    category="reference_integrity",
                    requirement_id=requirement.id,
                    summary="需求项来源引用不明确。",
                    suggestion="将占位来源替换为具体文档和章节标识。",
                )
            )

    return issues


def _questions_from_ambiguity(issues: list[ValidationIssue]) -> list[ClarificationQuestion]:
    questions: list[ClarificationQuestion] = []
    counter = 1
    for issue in issues:
        if issue.category != "ambiguity":
            continue
        questions.append(
            ClarificationQuestion(
                question_id=f"Q-AMB-{counter:03d}",
                question=f"请确认需求 {issue.requirement_id or '未编号项'} 中的歧义描述应如何量化。",
                reason=issue.summary,
                default_option="若暂时无法量化，则保守保留为待确认问题，不纳入正式基线。",
                blocking=False,
            )
        )
        counter += 1
    return questions


def _deduplicate_questions(questions: list[ClarificationQuestion]) -> list[ClarificationQuestion]:
    seen_signatures: set[tuple[str, str]] = set()
    result: list[ClarificationQuestion] = []
    for question in questions:
        signature = (question.question_id, question.question)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        result.append(question)
    return result


def _assign_issue_ids(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    for index, issue in enumerate(issues, start=1):
        issue.issue_id = f"ISSUE-{index:03d}"
    return issues


def _action_covered(keyword: str, extracted_text: str) -> bool:
    if keyword in extracted_text:
        return True
    if keyword == "查看详情":
        return "查看" in extracted_text and "详情" in extracted_text
    return False
