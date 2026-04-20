from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DatasetBundle:
    source_root: Path
    teams_path: Path
    players_path: Path
    dataset_label: str
    dataset_version: str | None = None
    profile_name: str = "auto"
    resolution_mode: str = "explicit"
    games_path: Path | None = None
    box_scores_path: Path | None = None
    extra_files: dict[str, Path] = field(default_factory=dict)


@dataclass
class DomainProfile:
    name: str
    sport: str
    entity_names: dict[str, str]
    required_files: list[str]
    thresholds: dict[str, Any]
    metric_map: dict[str, str]
    finding_categories: list[str]
    storyboard_template: dict[str, Any]
    alias_rules: dict[str, dict[str, list[str]]]
    finding_specs: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""


@dataclass
class EDARunConfig:
    repo_root: Path | None = None
    teams_path: Path | None = None
    players_path: Path | None = None
    manifest_path: Path | None = None
    profile_name: str = "auto"
    output_root: Path = Path("eda_runs")
    run_label: str = "default"
    max_findings: int = 8
    llm_enabled: bool | None = None
    llm_model: str = "gpt-4o-mini"
    # Backward-compatible aliases for the original softball-only v1 interface.
    min_player_ab: int | None = None
    min_player_ip: float | None = None
    min_qualified_rows: int | None = None


@dataclass
class VisualSuggestion:
    chart_type: str
    x: str
    y: str
    segment: str
    why: str


@dataclass
class Finding:
    id: str
    title: str
    category: str
    insight: str
    evidence: dict[str, Any]
    confidence: float
    audience_tags: list[str]
    visual_suggestions: list[VisualSuggestion]
    provenance: dict[str, Any]


@dataclass
class StoryboardStep:
    order: int
    finding_id: str
    step_type: str
    narrative: str
    transition: str


@dataclass
class DeeperAnalysisItem:
    question: str
    importance: str
    needed_data: list[str]
    method: str
    priority: str
