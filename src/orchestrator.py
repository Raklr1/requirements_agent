from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_app_config
from .differ import diff_requirement_sets, resolve_next_version
from .extractor import extract_requirement_candidates
from .llm_client import LLMClient
from .memory import load_memory, save_memory, update_memory
from .models import ChangeSummary, RequirementRunResult, RequirementSet, ValidationIssue, ValidationResult
from .normalizer import normalize_requirements
from .parser import load_project_context
from .validator import validate_requirements
from .writer import write_outputs


def run_requirements_agent(
    *,
    base_dir: str | Path | None = None,
    input_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> RequirementRunResult:
    config = load_app_config(base_dir)
    config.ensure_directories()

    resolved_input_dir = Path(input_dir) if input_dir else config.runtime.input_dir
    resolved_output_dir = Path(output_dir) if output_dir else config.runtime.output_dir

    context = load_project_context(str(resolved_input_dir))
    generated_at = _now_timestamp()
    memory = load_memory(config.runtime.memory_dir, package_root=config.package_root)

    if context.missing_inputs:
        validation = ValidationResult(
            passed=False,
            status="BLOCKED",
            issues=[
                ValidationIssue(
                    issue_id="ISSUE-001",
                    severity="critical",
                    category="input",
                    requirement_id=None,
                    summary=f"缺少关键输入文件: {', '.join(context.missing_inputs)}",
                    suggestion="补齐 product_brief.md 和 prototype.md 后重新运行。",
                )
            ],
            open_questions=[],
            risk_summary={"critical": 1},
        )
        requirements = RequirementSet(
            project_name=context.project_name,
            version=config.project.version_when_draft,
            status=validation.status,
        )
        result = RequirementRunResult(
            context=context,
            requirements=requirements,
            validation=validation,
            change_summary=ChangeSummary(reason="blocked_due_to_missing_inputs"),
            generated_at=generated_at,
            status=validation.status,
        )
        write_outputs(result, str(resolved_output_dir))
        save_memory(
            update_memory(
                memory,
                result,
                requirements_file=_relative_requirements_path(config.package_root),
            ),
            config.runtime.memory_dir,
        )
        return result

    llm_client = LLMClient(config.model)
    draft = extract_requirement_candidates(
        context,
        llm_client=llm_client,
        prompt_dir=config.runtime.prompt_dir,
        allow_fallback=config.runtime.allow_rule_based_fallback,
    )
    requirements = normalize_requirements(
        draft,
        previous=memory.last_baseline,
        project_name=context.project_name,
    )
    validation = validate_requirements(requirements, context, config.rules)
    change_summary = diff_requirement_sets(memory.last_baseline, requirements)
    requirements.version = resolve_next_version(
        memory.current_version,
        change_summary,
        validation.status,
        config.project.version_when_draft,
    )
    requirements.status = validation.status

    result = RequirementRunResult(
        context=context,
        requirements=requirements,
        validation=validation,
        change_summary=change_summary,
        generated_at=generated_at,
        status=validation.status,
    )
    write_outputs(result, str(resolved_output_dir))
    save_memory(
        update_memory(
            memory,
            result,
            requirements_file=_relative_requirements_path(config.package_root),
        ),
        config.runtime.memory_dir,
    )
    return result


def _now_timestamp() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def _relative_requirements_path(package_root: Path) -> str:
    return str((Path("outputs") / "requirements.json").as_posix())
