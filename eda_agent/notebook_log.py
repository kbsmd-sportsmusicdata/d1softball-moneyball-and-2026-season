from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import nbformat
import pandas as pd

from .contracts import EDARunConfig, Finding, StoryboardStep, DeeperAnalysisItem


def findings_markdown(findings: list[Finding]) -> str:
    lines = ["## Key Findings", ""]
    for index, finding in enumerate(findings, start=1):
        lines.append(f"### {index}. {finding.title}")
        lines.append(f"- Category: `{finding.category}`")
        lines.append(f"- Insight: {finding.insight}")
        lines.append(f"- Confidence: {finding.confidence:.2f}")
        lines.append("- Visual Suggestions:")
        for visual in finding.visual_suggestions:
            lines.append(f"  - {visual.chart_type}: `{visual.x}` vs `{visual.y}` ({visual.segment}) - {visual.why}")
        lines.append("")
    return "\n".join(lines)


def build_notebook(
    run_config: EDARunConfig,
    run_metadata: dict[str, Any],
    dataset_profile: dict[str, Any],
    findings: list[Finding],
    storyboard: dict[str, Any],
    deeper_analysis: list[DeeperAnalysisItem],
    teams: pd.DataFrame,
    players: pd.DataFrame,
) -> nbformat.NotebookNode:
    notebook = nbformat.v4.new_notebook()
    team_preview = teams.head(10).to_string(index=False)
    player_preview = players.head(10).to_string(index=False)

    notebook.cells = [
        nbformat.v4.new_markdown_cell(
            f"# EDA Analyst Run Log\n\n- Run ID: `{run_metadata['run_id']}`\n- Label: `{run_config.run_label}`\n- Schema: `{run_metadata['schema_version']}`"
        ),
        nbformat.v4.new_markdown_cell(
            "## Setup / Config\n\n```json\n" + json.dumps(asdict(run_config), indent=2, default=str) + "\n```"
        ),
        nbformat.v4.new_markdown_cell(
            "## Dataset Profile + Quality Checks\n\n```json\n" + json.dumps(dataset_profile, indent=2) + "\n```"
        ),
        nbformat.v4.new_markdown_cell(
            "## Metric Engineering\n\n"
            "Generated comparative metrics for team balance, elite player impact, run prevention, and fan-facing volatility signals."
            "\n\n### Team Preview\n\n```\n"
            + team_preview
            + "\n```\n\n### Player Preview\n\n```\n"
            + player_preview
            + "\n```"
        ),
        nbformat.v4.new_markdown_cell(
            "## Hypothesis Checks\n\n"
            "- Stronger team-level signal should cluster near the top of the ranked board.\n"
            "- Qualified player performance should separate otherwise similar teams.\n"
            "- Coaching signals should emerge from discipline plus defensive consistency."
        ),
        nbformat.v4.new_markdown_cell(findings_markdown(findings)),
        nbformat.v4.new_markdown_cell(
            "## Storyboard Synthesis\n\n```json\n" + json.dumps(storyboard, indent=2) + "\n```"
        ),
        nbformat.v4.new_markdown_cell(
            "## Deeper Analysis Suggestions\n\n```json\n"
            + json.dumps([asdict(item) for item in deeper_analysis], indent=2)
            + "\n```"
        ),
    ]
    return notebook
