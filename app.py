from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from requirements_agent.src.config import load_app_config
from requirements_agent.src.orchestrator import run_requirements_agent


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Requirements Agent.")
    parser.add_argument("--base-dir", default=None, help="Workspace root or requirements_agent package root.")
    parser.add_argument("--input-dir", default=None, help="Override input directory.")
    parser.add_argument("--output-dir", default=None, help="Override output directory.")
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_app_config(args.base_dir)
    result = run_requirements_agent(
        base_dir=args.base_dir,
        input_dir=args.input_dir or config.runtime.input_dir,
        output_dir=args.output_dir or config.runtime.output_dir,
    )
    print(result.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
