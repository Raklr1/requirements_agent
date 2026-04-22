from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import load_yaml_file
from .models import ProjectContext, SourceDocument


REQUIRED_INPUTS = ("product_brief.md", "prototype.md")


@dataclass(slots=True)
class MarkdownSection:
    ref: str
    title: str
    level: int
    path: str
    content: str


def load_project_context(input_dir: str) -> ProjectContext:
    input_path = Path(input_dir)
    documents: dict[str, SourceDocument] = {}
    source_map: dict[str, dict[str, str]] = {}
    missing_inputs: list[str] = []

    for file_name in REQUIRED_INPUTS:
        file_path = input_path / file_name
        if not file_path.exists():
            missing_inputs.append(file_name)
            continue
        document, doc_source_map = _load_markdown_document(file_path, _alias_for(file_name))
        documents[file_name] = document
        source_map.update(doc_source_map)

    feedback_notes: list[str] = []
    feedback_path = input_path / "feedback.md"
    if feedback_path.exists():
        feedback_document, feedback_source_map = _load_markdown_document(feedback_path, "feedback")
        documents["feedback.md"] = feedback_document
        source_map.update(feedback_source_map)
        feedback_notes = _extract_bullets(feedback_document.content)

    constraints_path = input_path / "constraints.yaml"
    constraints = load_yaml_file(constraints_path) if constraints_path.exists() else {}

    brief_content = documents.get("product_brief.md", SourceDocument("", "", "")).content
    prototype_content = documents.get("prototype.md", SourceDocument("", "", "")).content

    project_name = (
        _extract_label_value(brief_content, "产品名称")
        or _extract_first_heading(brief_content)
        or _extract_first_heading(prototype_content)
    )

    return ProjectContext(
        project_name=project_name,
        project_goal=_extract_project_goal(documents.get("product_brief.md")),
        target_users=_extract_target_users(documents.get("product_brief.md")),
        scenarios=_extract_scenarios(documents),
        prototype_notes=_extract_prototype_notes(documents.get("prototype.md")),
        constraints=constraints,
        feedback_notes=feedback_notes,
        source_map=source_map,
        documents=documents,
        missing_inputs=missing_inputs,
    )


def _load_markdown_document(path: Path, alias: str) -> tuple[SourceDocument, dict[str, dict[str, str]]]:
    content = path.read_text(encoding="utf-8")
    sections = _parse_markdown_sections(content, alias)
    source_map: dict[str, dict[str, str]] = {}
    serialized_sections: dict[str, str] = {}

    for section in sections:
        serialized_sections[section.ref] = section.content
        source_map[section.ref] = {
            "document": path.name,
            "title": section.title,
            "title_path": section.path,
            "path": str(path.resolve()),
            "excerpt": section.content[:240].strip(),
        }

    return SourceDocument(
        name=path.name,
        path=str(path.resolve()),
        content=content,
        sections=serialized_sections,
    ), source_map


def _parse_markdown_sections(content: str, alias: str) -> list[MarkdownSection]:
    sections: list[MarkdownSection] = []
    lines = content.splitlines()
    heading_stack: list[tuple[int, str]] = []
    current_title = "document"
    current_level = 0
    current_buffer: list[str] = []
    section_index = 0

    for raw_line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", raw_line)
        if match:
            _append_section(
                sections,
                alias,
                section_index,
                current_title,
                current_level,
                heading_stack,
                current_buffer,
            )
            if current_title != "document":
                section_index += 1

            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack = [item for item in heading_stack if item[0] < level]
            heading_stack.append((level, title))
            current_title = title
            current_level = level
            current_buffer = []
            continue

        current_buffer.append(raw_line)

    _append_section(
        sections,
        alias,
        section_index,
        current_title,
        current_level,
        heading_stack,
        current_buffer,
    )
    return [section for section in sections if section.content.strip()]


def _append_section(
    sections: list[MarkdownSection],
    alias: str,
    section_index: int,
    current_title: str,
    current_level: int,
    heading_stack: list[tuple[int, str]],
    current_buffer: list[str],
) -> None:
    text = "\n".join(current_buffer).strip()
    if current_title == "document" or not text:
        return

    path = " > ".join(title for _, title in heading_stack) or current_title
    ref = f"{alias}:{_slugify(path) or f'section-{section_index + 1:03d}'}"
    sections.append(
        MarkdownSection(
            ref=ref,
            title=current_title,
            level=current_level,
            path=path,
            content=text,
        )
    )


def _extract_label_value(content: str, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}\s*[：:]\s*(.+)")
    match = pattern.search(content)
    return match.group(1).strip() if match else ""


def _extract_first_heading(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            title = re.sub(r"\s+(Product Brief|Prototype Notes)$", "", title).strip()
            return title
    return ""


def _extract_project_goal(document: SourceDocument | None) -> str:
    if not document:
        return ""

    preferred_refs = ("总体目标", "产品目标", "业务目标", "系统目标")
    for ref, text in document.sections.items():
        if any(keyword in ref for keyword in preferred_refs):
            bullets = _extract_bullets(text)
            if bullets:
                return "；".join(bullets[:3])
            paragraph = _extract_first_paragraph(text)
            if paragraph:
                return paragraph

    return _extract_first_paragraph(document.content)


def _extract_target_users(document: SourceDocument | None) -> list[str]:
    if not document:
        return []

    roles: list[str] = []
    for ref in document.sections:
        normalized = _normalize_role_name(ref)
        if normalized:
            roles.append(normalized)

    content_roles = re.findall(r"^###\s+\d+\.\d+\s*(.+)$", document.content, flags=re.MULTILINE)
    roles.extend(_normalize_role_name(item) for item in content_roles)
    return _unique_preserve_order(item for item in roles if item)


def _extract_scenarios(documents: dict[str, SourceDocument]) -> list[str]:
    scenarios: list[str] = []
    for file_name, document in documents.items():
        if not file_name.endswith(".md"):
            continue
        for ref, text in document.sections.items():
            if any(keyword in ref for keyword in ("流程", "场景")):
                scenarios.extend(_extract_bullets(text))
    return _unique_preserve_order(item for item in scenarios if item)


def _extract_prototype_notes(document: SourceDocument | None) -> list[str]:
    if not document:
        return []

    notes: list[str] = []
    for ref, text in document.sections.items():
        if any(keyword in ref for keyword in ("页面", "工作台", "审核中心", "统计")):
            notes.extend(_extract_bullets(text))
    return _unique_preserve_order(note for note in notes if note)


def _extract_bullets(content: str) -> list[str]:
    bullets: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^[-*]\s+", stripped):
            bullets.append(re.sub(r"^[-*]\s+", "", stripped).strip())
            continue
        if re.match(r"^\d+\.\s+", stripped):
            bullets.append(re.sub(r"^\d+\.\s+", "", stripped).strip())
    return bullets


def _extract_first_paragraph(content: str) -> str:
    paragraph_lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            if paragraph_lines:
                break
            continue
        if stripped.startswith(("#", "-", "*")) or re.match(r"^\d+\.\s+", stripped):
            continue
        paragraph_lines.append(stripped)
    return " ".join(paragraph_lines).strip()


def _normalize_role_name(value: str) -> str:
    if "游客" in value:
        return "游客"
    if "学生" in value:
        return "学生用户"
    if "活动负责人" in value or "组织者" in value:
        return "活动负责人"
    if "管理员" in value or "老师" in value:
        return "管理员"
    return ""


def _unique_preserve_order(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _slugify(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^\w\u4e00-\u9fff]+", "-", lowered, flags=re.UNICODE)
    return lowered.strip("-")


def _alias_for(file_name: str) -> str:
    mapping = {
        "product_brief.md": "brief",
        "prototype.md": "prototype",
        "feedback.md": "feedback",
    }
    return mapping.get(file_name, Path(file_name).stem)
