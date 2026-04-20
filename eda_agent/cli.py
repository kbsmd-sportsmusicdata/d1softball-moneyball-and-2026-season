from __future__ import annotations

import argparse
import os
from pathlib import Path

from .config import EDARunConfig
from .runners import run_agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the EDA analyst agent on a repo dataset bundle.")
    parser.add_argument("--repo-root", type=Path, help="Root of the repo or project containing data/processed.")
    parser.add_argument("--teams-path", type=Path, help="Explicit teams CSV path.")
    parser.add_argument("--players-path", type=Path, help="Explicit players CSV path.")
    parser.add_argument("--manifest", type=Path, dest="manifest_path", help="JSON manifest describing dataset paths.")
    parser.add_argument("--profile", type=str, default="auto", help="Profile name or path to a profile JSON file.")
    parser.add_argument("--run-label", type=str, default="default", help="Human-readable label for the run.")
    parser.add_argument("--output-root", type=Path, default=Path("eda_runs"), help="Folder where run artifacts are written.")
    parser.add_argument("--max-findings", type=int, default=8, help="Maximum number of findings to retain.")
    parser.add_argument("--llm-model", type=str, default="gpt-4o-mini", help="Model used for optional narrative polishing.")
    parser.add_argument(
        "--llm-enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable optional LLM polishing explicitly.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    llm_enabled = args.llm_enabled
    if llm_enabled is None:
        llm_enabled = bool(os.getenv("OPENAI_API_KEY", "").strip())

    config = EDARunConfig(
        repo_root=args.repo_root,
        teams_path=args.teams_path,
        players_path=args.players_path,
        manifest_path=args.manifest_path,
        profile_name=args.profile,
        output_root=args.output_root,
        run_label=args.run_label,
        max_findings=args.max_findings,
        llm_enabled=llm_enabled,
        llm_model=args.llm_model,
    )
    result = run_agent(config)
    from .outputs import json_ready
    import json

    print(json.dumps(json_ready(result), indent=2))


if __name__ == "__main__":
    main()
