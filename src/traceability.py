from __future__ import annotations

import csv
from pathlib import Path

from .models import FunctionalRequirement, RequirementSet


def build_traceability_rows(requirements: RequirementSet) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for requirement in requirements.iter_all_requirement_items():
        sources = getattr(requirement, "source", []) or ["source:unknown"]
        acceptance_ids = "|".join(getattr(requirement, "acceptance_ids", []))
        prototype_ref = _extract_prototype_ref(sources)

        for source in sources:
            source_type, source_ref = _split_source(source)
            rows.append(
                {
                    "requirement_id": requirement.id,
                    "requirement_title": getattr(requirement, "title", ""),
                    "source_type": source_type,
                    "source_ref": source_ref,
                    "prototype_ref": prototype_ref,
                    "acceptance_ids": acceptance_ids,
                }
            )

    return rows


def write_traceability_csv(requirements: RequirementSet, output_path: str | Path) -> None:
    rows = build_traceability_rows(requirements)
    fieldnames = [
        "requirement_id",
        "requirement_title",
        "source_type",
        "source_ref",
        "prototype_ref",
        "acceptance_ids",
    ]

    with Path(output_path).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _split_source(source: str) -> tuple[str, str]:
    if ":" not in source:
        return "unknown", source
    source_type, source_ref = source.split(":", 1)
    return source_type, source_ref


def _extract_prototype_ref(sources: list[str]) -> str:
    for source in sources:
        if source.startswith("prototype:"):
            return source.split(":", 1)[1]
    return ""
