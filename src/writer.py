from __future__ import annotations

import json
from pathlib import Path

from .config import dump_yaml_file
from .models import RequirementRunResult
from .traceability import write_traceability_csv


def write_outputs(result: RequirementRunResult, output_dir: str) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    (output_path / "SRS.md").write_text(_render_srs(result), encoding="utf-8")
    (output_path / "requirements.json").write_text(
        json.dumps(result.requirements.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    dump_yaml_file(
        output_path / "acceptance_criteria.yaml",
        [criterion.to_dict() for criterion in result.requirements.acceptance_criteria],
    )
    (output_path / "open_questions.md").write_text(_render_open_questions(result), encoding="utf-8")
    (output_path / "review_report.md").write_text(_render_review_report(result), encoding="utf-8")
    (output_path / "change_log.md").write_text(_render_change_log(result), encoding="utf-8")
    write_traceability_csv(result.requirements, output_path / "traceability.csv")


def _render_srs(result: RequirementRunResult) -> str:
    context = result.context
    requirements = result.requirements

    lines = [
        f"# {context.project_name or '未命名项目'} 软件需求规格说明书",
        "",
        "## 1. 项目背景",
        _paragraph_or_placeholder(_extract_brief_excerpt(context)),
        "",
        "## 2. 产品目标",
        _paragraph_or_placeholder(context.project_goal),
        "",
        "## 3. 用户与场景",
        "### 3.1 目标用户",
    ]
    lines.extend(_render_bullets(context.target_users))
    lines.extend(
        [
            "",
            "### 3.2 核心场景",
        ]
    )
    lines.extend(_render_bullets(context.scenarios))
    lines.extend(
        [
            "",
            "## 4. 功能需求",
        ]
    )
    for requirement in requirements.functional_requirements:
        lines.extend(
            [
                f"### {requirement.id} {requirement.title}",
                f"- 描述：{requirement.description}",
                f"- 角色：{', '.join(requirement.actors)}",
                f"- 前置条件：{'；'.join(requirement.preconditions)}",
                f"- 主流程：{'；'.join(requirement.main_flow)}",
                f"- 备选流程：{'；'.join(requirement.alternate_flow)}",
                f"- 后置条件：{'；'.join(requirement.postconditions)}",
                f"- 优先级：{requirement.priority}",
                f"- 来源：{', '.join(requirement.source)}",
                f"- 验收标准：{', '.join(requirement.acceptance_ids) if requirement.acceptance_ids else 'None'}",
                "",
            ]
        )

    lines.extend(["## 5. 非功能需求"])
    for requirement in requirements.non_functional_requirements:
        lines.extend(
            [
                f"- {requirement.id} {requirement.title}：{requirement.description} "
                f"(category={requirement.category}, metric={requirement.metric}, scope={', '.join(requirement.scope)})"
            ]
        )
    if not requirements.non_functional_requirements:
        lines.append("- None")

    lines.extend(["", "## 6. 业务规则"])
    lines.extend(
        [f"- {rule.id} {rule.description}" for rule in requirements.business_rules]
        or ["- None"]
    )

    lines.extend(["", "## 7. 异常与边界情况"])
    lines.extend(
        [f"- {edge_case.id} {edge_case.description}" for edge_case in requirements.edge_cases]
        or ["- None"]
    )

    lines.extend(["", "## 8. 验收标准摘要"])
    if requirements.acceptance_criteria:
        for criterion in requirements.acceptance_criteria:
            lines.append(
                f"- {criterion.id} ({criterion.requirement_id or 'UNLINKED'}) "
                f"Given {criterion.given} / When {criterion.when} / Then {criterion.then}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## 9. 待确认问题"])
    if result.validation.open_questions:
        for question in result.validation.open_questions:
            blocking = "是" if question.blocking else "否"
            lines.extend(
                [
                    f"### {question.question_id}",
                    f"- 问题：{question.question}",
                    f"- 原因：{question.reason}",
                    f"- 默认方案：{question.default_option or 'None'}",
                    f"- 是否阻塞：{blocking}",
                    "",
                ]
            )
    else:
        lines.append("None")

    lines.extend(
        [
            "## 10. 版本信息",
            f"- 版本：{requirements.version}",
            f"- 生成时间：{result.generated_at}",
            f"- 状态：{result.status}",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def _render_open_questions(result: RequirementRunResult) -> str:
    questions = result.validation.open_questions
    if not questions:
        return "None\n"

    lines = ["# Open Questions", ""]
    for question in questions:
        lines.extend(
            [
                f"## {question.question_id}",
                f"- Question: {question.question}",
                f"- Reason: {question.reason}",
                f"- Default Option: {question.default_option or 'None'}",
                f"- Blocking: {'true' if question.blocking else 'false'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_review_report(result: RequirementRunResult) -> str:
    validation = result.validation
    context = result.context
    allow_downstream = "Yes" if validation.status == "BASELINE_READY" else "No"

    lines = [
        "# Review Report",
        "",
        "## 1. 本次检查时间",
        result.generated_at,
        "",
        "## 2. 输入材料摘要",
        f"- project_brief.md: {'present' if 'product_brief.md' in context.documents else 'missing'}",
        f"- prototype.md: {'present' if 'prototype.md' in context.documents else 'missing'}",
        f"- constraints.yaml: {'present' if context.constraints else 'missing_or_empty'}",
        f"- feedback.md: {'present' if context.feedback_notes else 'missing_or_empty'}",
        "",
        "## 3. 总体结论",
        f"- Status: {validation.status}",
        f"- Passed: {'true' if validation.passed else 'false'}",
        "",
        "## 4. 问题列表",
    ]

    if validation.issues:
        for issue in validation.issues:
            lines.append(
                f"- {issue.issue_id} [{issue.severity}] ({issue.category}) "
                f"{issue.requirement_id or 'GLOBAL'}: {issue.summary} | 建议：{issue.suggestion}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## 5. 风险等级统计"])
    if validation.risk_summary:
        for severity, count in validation.risk_summary.items():
            lines.append(f"- {severity}: {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## 6. 是否允许下发", f"- {allow_downstream}"])
    return "\n".join(lines).rstrip() + "\n"


def _render_change_log(result: RequirementRunResult) -> str:
    change_summary = result.change_summary
    lines = [
        "# Change Log",
        "",
        f"## {result.generated_at}",
        f"- Version: {result.requirements.version}",
        f"- Status: {result.status}",
        f"- Reason: {change_summary.reason or 'none'}",
        f"- Downstream Impact: {change_summary.downstream_impact or 'none'}",
        f"- Added: {', '.join(change_summary.added_ids) if change_summary.added_ids else 'None'}",
        f"- Modified: {', '.join(change_summary.modified_ids) if change_summary.modified_ids else 'None'}",
        f"- Removed: {', '.join(change_summary.removed_ids) if change_summary.removed_ids else 'None'}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _render_bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _extract_brief_excerpt(result_context) -> str:
    brief = result_context.documents.get("product_brief.md")
    if not brief:
        return ""

    for section_text in brief.sections.values():
        paragraph = _first_nonempty_line(section_text)
        if paragraph:
            return paragraph
    return ""


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _paragraph_or_placeholder(value: str) -> str:
    return value.strip() if value.strip() else "None"
