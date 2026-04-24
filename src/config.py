from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Raised when configuration files are malformed or incomplete."""


@dataclass(slots=True)
class RuntimeSettings:
    input_dir: Path
    output_dir: Path
    memory_dir: Path
    prompt_dir: Path
    allow_rule_based_fallback: bool = True
    use_llm_for_srs: bool = False
    status_on_blocking_question: str = "DRAFT_READY"


@dataclass(slots=True)
class ModelSettings:
    provider_type: str
    model_name: str
    api_base_url: str
    api_key_env: str
    chat_completions_path: str = "/chat/completions"
    timeout_seconds: int = 60
    temperature: float = 0.2
    max_tokens: int = 4000
    top_p: float = 0.9

    def resolve_api_key(self) -> str | None:
        return os.getenv(self.api_key_env)


@dataclass(slots=True)
class RuleSettings:
    ambiguity_terms: list[str] = field(default_factory=list)
    blocking_issue_categories: list[str] = field(default_factory=list)
    warning_issue_categories: list[str] = field(default_factory=list)
    severity_order: list[str] = field(default_factory=lambda: ["critical", "high", "medium", "low"])


@dataclass(slots=True)
class ProjectSettings:
    default_author: str = "Requirements Agent"
    version_when_draft: str = "v0.1"


@dataclass(slots=True)
class AppConfig:
    package_root: Path
    runtime: RuntimeSettings
    model: ModelSettings
    rules: RuleSettings
    project: ProjectSettings
    raw: dict[str, Any] = field(default_factory=dict)

    def ensure_directories(self) -> None:
        for directory in (
            self.runtime.input_dir,
            self.runtime.output_dir,
            self.runtime.memory_dir,
            self.runtime.prompt_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def load_app_config(base_dir: str | Path | None = None) -> AppConfig:
    package_root = _resolve_package_root(base_dir)
    config_dir = package_root / "config"

    settings_data = load_yaml_file(config_dir / "settings.yaml")
    model_data = load_yaml_file(config_dir / "model_config.yaml")
    rule_data = load_yaml_file(config_dir / "rule_config.yaml")

    runtime_section = settings_data.get("runtime", {})
    project_section = settings_data.get("project", {})
    provider_section = model_data.get("provider", {})
    model_section = model_data.get("model", {})

    runtime = RuntimeSettings(
        input_dir=_resolve_subpath(package_root, runtime_section.get("input_dir", "inputs")),
        output_dir=_resolve_subpath(package_root, runtime_section.get("output_dir", "outputs")),
        memory_dir=_resolve_subpath(package_root, runtime_section.get("memory_dir", "memory")),
        prompt_dir=_resolve_subpath(package_root, runtime_section.get("prompt_dir", "prompts")),
        allow_rule_based_fallback=bool(runtime_section.get("allow_rule_based_fallback", True)),
        use_llm_for_srs=bool(runtime_section.get("use_llm_for_srs", False)),
        status_on_blocking_question=str(runtime_section.get("status_on_blocking_question", "DRAFT_READY")),
    )

    model = ModelSettings(
        provider_type=str(provider_section.get("type", "compatible")),
        chat_completions_path=str(provider_section.get("chat_completions_path", "/chat/completions")),
        model_name=str(model_section.get("name", "qwen3.6-plus-2026-04-02")),
        api_base_url=str(
            model_section.get("api_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        ),
        api_key_env=str(model_section.get("api_key_env", "DASHSCOPE_API_KEY")),
        timeout_seconds=int(model_section.get("timeout_seconds", 60)),
        temperature=float(model_section.get("temperature", 0.2)),
        max_tokens=int(model_section.get("max_tokens", 4000)),
        top_p=float(model_section.get("top_p", 0.9)),
    )

    rules = RuleSettings(
        ambiguity_terms=[str(item) for item in rule_data.get("ambiguity_terms", [])],
        blocking_issue_categories=[str(item) for item in rule_data.get("blocking_issue_categories", [])],
        warning_issue_categories=[str(item) for item in rule_data.get("warning_issue_categories", [])],
        severity_order=[str(item) for item in rule_data.get("severity_order", ["critical", "high", "medium", "low"])],
    )

    project = ProjectSettings(
        default_author=str(project_section.get("default_author", "Requirements Agent")),
        version_when_draft=str(project_section.get("version_when_draft", "v0.1")),
    )

    return AppConfig(
        package_root=package_root,
        runtime=runtime,
        model=model,
        rules=rules,
        project=project,
        raw={
            "settings": settings_data,
            "model": model_data,
            "rules": rule_data,
        },
    )


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}

    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        return {}

    parsed = parse_simple_yaml(text)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ConfigError(f"YAML root object must be a mapping: {file_path}")
    return parsed


def dump_yaml_file(path: str | Path, data: Any) -> None:
    Path(path).write_text(to_simple_yaml(data), encoding="utf-8")


def parse_simple_yaml(text: str) -> Any:
    cleaned_lines = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if "\t" in raw_line[:indent]:
            raise ConfigError("Tabs are not supported in YAML indentation.")
        cleaned_lines.append((indent, raw_line[indent:]))

    if not cleaned_lines:
        return {}

    value, next_index = _parse_yaml_block(cleaned_lines, 0, cleaned_lines[0][0])
    if next_index != len(cleaned_lines):
        raise ConfigError("Unable to parse the full YAML document.")
    return value


def to_simple_yaml(data: Any, indent: int = 0) -> str:
    lines = _serialize_yaml_lines(data, indent)
    return "\n".join(lines) + "\n"


def _serialize_yaml_lines(data: Any, indent: int) -> list[str]:
    space = " " * indent
    if isinstance(data, dict):
        lines: list[str] = []
        for key, value in data.items():
            if _is_scalar(value):
                lines.append(f"{space}{key}: {_format_yaml_scalar(value)}")
            else:
                lines.append(f"{space}{key}:")
                lines.extend(_serialize_yaml_lines(value, indent + 2))
        return lines

    if isinstance(data, list):
        lines = []
        for item in data:
            if _is_scalar(item):
                lines.append(f"{space}- {_format_yaml_scalar(item)}")
            else:
                lines.append(f"{space}-")
                lines.extend(_serialize_yaml_lines(item, indent + 2))
        return lines

    return [f"{space}{_format_yaml_scalar(data)}"]


def _parse_yaml_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if lines[index][1].startswith("- "):
        return _parse_yaml_list(lines, index, indent)
    return _parse_yaml_dict(lines, index, indent)


def _parse_yaml_dict(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}

    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ConfigError(f"Unexpected indentation near: {content}")
        if content.startswith("- "):
            break

        key, separator, remainder = content.partition(":")
        if not separator:
            raise ConfigError(f"Invalid mapping line: {content}")

        key = key.strip()
        remainder = remainder.strip()
        index += 1

        if remainder:
            result[key] = _parse_yaml_scalar(remainder)
            continue

        if index < len(lines) and lines[index][0] > indent:
            child, index = _parse_yaml_block(lines, index, lines[index][0])
            result[key] = child
        else:
            result[key] = {}

    return result, index


def _parse_yaml_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []

    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent != indent or not content.startswith("- "):
            break

        item = content[2:].strip()
        index += 1

        if not item:
            if index < len(lines) and lines[index][0] > indent:
                child, index = _parse_yaml_block(lines, index, lines[index][0])
                result.append(child)
            else:
                result.append(None)
            continue

        if ":" in item and not item.startswith(("{", "[", "\"", "'")):
            key, separator, remainder = item.partition(":")
            if separator:
                inline_dict: dict[str, Any] = {key.strip(): _parse_yaml_scalar(remainder.strip()) if remainder.strip() else {}}
                if index < len(lines) and lines[index][0] > indent:
                    child, index = _parse_yaml_block(lines, index, lines[index][0])
                    if remainder.strip():
                        inline_dict["_extra"] = child
                    elif isinstance(child, dict):
                        inline_dict[key.strip()] = child
                    else:
                        inline_dict["_value"] = child
                result.append(inline_dict)
                continue

        result.append(_parse_yaml_scalar(item))

    return result, index


def _parse_yaml_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None

    if value.startswith(("{", "[", "\"", "'")):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value

    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)

    try:
        return float(value)
    except ValueError:
        return value


def _format_yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)

    if not value:
        return '""'

    needs_quotes = any(
        (
            value.startswith((" ", "-", "{", "[", "!", "&", "*", "#", "?", ":", "@")),
            value.endswith(" "),
            ":" in value,
            "#" in value,
        )
    )
    return json.dumps(value, ensure_ascii=False) if needs_quotes else value


def _is_scalar(value: Any) -> bool:
    return not isinstance(value, (dict, list))


def _resolve_package_root(base_dir: str | Path | None) -> Path:
    if base_dir is None:
        return Path(__file__).resolve().parents[1]

    candidate = Path(base_dir).resolve()
    if (candidate / "config").exists():
        return candidate
    if (candidate / "requirements_agent" / "config").exists():
        return (candidate / "requirements_agent").resolve()
    return candidate


def _resolve_subpath(package_root: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path
    return (package_root / path).resolve()
