import json
from pathlib import Path

import nbformat
import pandas as pd

from scripts.eda_analyst_agent import (
    EDARunConfig,
    DatasetResolver,
    REQUIRED_FINDING_CATEGORIES,
    _build_findings,
    _build_storyboard,
    _polish_with_llm,
    run_agent,
)


def _sample_teams() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "team_id": "alpha",
                "team_name": "Alpha",
                "composite_score": 2.4,
                "composite_rank": 1,
                "offense_z": 1.3,
                "pitching_z": 1.2,
                "discipline_z": 0.6,
                "defense_z": 0.7,
                "runs_per_game": 8.1,
                "whip": 1.0,
                "era": 1.9,
                "bb_k_ratio": 0.55,
                "fielding_pct": 0.981,
            },
            {
                "team_id": "beta",
                "team_name": "Beta",
                "composite_score": 1.9,
                "composite_rank": 2,
                "offense_z": 1.2,
                "pitching_z": 1.1,
                "discipline_z": 0.5,
                "defense_z": 0.4,
                "runs_per_game": 7.7,
                "whip": 1.1,
                "era": 2.1,
                "bb_k_ratio": 0.44,
                "fielding_pct": 0.972,
            },
        ]
    )


def _sample_players() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": "p1",
                "player_name": "Slugger One",
                "team_id": "alpha",
                "team_name": "Alpha",
                "ab": 100,
                "ops": 1.220,
                "iso": 0.420,
                "hr": 15,
                "k": 18,
                "ip": 0,
                "so": 18,
            },
            {
                "player_id": "p2",
                "player_name": "Ace Arm",
                "team_id": "alpha",
                "team_name": "Alpha",
                "ab": 10,
                "ops": 0.500,
                "iso": 0.050,
                "hr": 0,
                "k": 120,
                "ip": 98.0,
                "so": 0,
            },
            {
                "player_id": "p3",
                "player_name": "Power Volatility",
                "team_id": "beta",
                "team_name": "Beta",
                "ab": 120,
                "ops": 1.010,
                "iso": 0.390,
                "hr": 14,
                "k": 40,
                "ip": 0,
                "so": 52,
            },
        ]
    )


def test_resolver_selects_latest_processed_folder(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    processed = tmp_path / "data" / "processed"
    (processed / "2026-03-01").mkdir(parents=True)
    (processed / "2026-04-10").mkdir(parents=True)
    (processed / "2026-03-01" / "teams.csv").write_text("team_id\nalpha\n")
    (processed / "2026-03-01" / "players.csv").write_text("player_id\np1\n")
    (processed / "2026-04-10" / "teams.csv").write_text("team_id\nbeta\n")
    (processed / "2026-04-10" / "players.csv").write_text("player_id\np2\n")

    teams_path, players_path, mode = DatasetResolver.resolve(None, None)
    assert teams_path.as_posix().endswith("data/processed/2026-04-10/teams.csv")
    assert players_path.as_posix().endswith("data/processed/2026-04-10/players.csv")
    assert mode == "latest_processed"


def test_findings_contract_category_and_visual_coverage():
    findings = _build_findings(
        teams=_sample_teams(),
        players=_sample_players(),
        min_player_ab=30,
        min_player_ip=20.0,
        max_findings=8,
    )
    assert 5 <= len(findings) <= 10

    categories = {f.category for f in findings}
    assert set(REQUIRED_FINDING_CATEGORIES).issubset(categories)

    for finding in findings:
        assert 1 <= len(finding.visual_suggestions) <= 2


def test_storyboard_links_findings_with_valid_step_count():
    findings = _build_findings(
        teams=_sample_teams(),
        players=_sample_players(),
        min_player_ab=30,
        min_player_ip=20.0,
        max_findings=8,
    )
    storyboard = _build_storyboard(findings)
    assert 4 <= len(storyboard["steps"]) <= 8
    valid_ids = {f.id for f in findings}
    assert all(step["finding_id"] in valid_ids for step in storyboard["steps"])
    assert all(step["transition"] for step in storyboard["steps"])


def test_llm_polish_falls_back_when_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    findings = _build_findings(
        teams=_sample_teams(),
        players=_sample_players(),
        min_player_ab=30,
        min_player_ip=20.0,
        max_findings=8,
    )
    polished, err = _polish_with_llm(findings, model="gpt-4o-mini")
    assert polished
    assert err == "OPENAI_API_KEY not set"


def test_run_agent_emits_full_artifact_set(tmp_path: Path):
    output_root = tmp_path / "eda_runs"
    config = EDARunConfig(
        teams_path=Path("data/processed/2026-04-10/teams.csv"),
        players_path=Path("data/processed/2026-04-10/players.csv"),
        run_label="test-run",
        output_root=output_root,
        min_player_ab=30,
        min_player_ip=20.0,
        max_findings=8,
        llm_enabled=False,
        llm_model="gpt-4o-mini",
    )

    result = run_agent(config)
    run_dir = Path(result["run_path"])

    required_files = [
        "run_metadata.json",
        "dataset_profile.json",
        "findings.json",
        "storyboard.json",
        "deeper_analysis.json",
        "summary.md",
        "run_log.ipynb",
    ]
    for filename in required_files:
        assert (run_dir / filename).exists()

    metadata = json.loads((run_dir / "run_metadata.json").read_text())
    assert metadata["schema_version"] == "eda_agent_v1"
    assert metadata["outputs"]["findings_count"] >= 5
    assert 4 <= metadata["outputs"]["storyboard_steps"] <= 8
    assert any("AB=0" in warning for warning in metadata["warnings"])

    profile = json.loads((run_dir / "dataset_profile.json").read_text())
    assert profile["players"]["nonzero_counts"]["ab"] == 0
    assert profile["players"]["nonzero_counts"]["ip"] >= 0

    findings = json.loads((run_dir / "findings.json").read_text())
    assert 5 <= len(findings) <= 10
    assert set(REQUIRED_FINDING_CATEGORIES).issubset({f["category"] for f in findings})

    notebook = nbformat.read(run_dir / "run_log.ipynb", as_version=4)
    assert len(notebook.cells) >= 8

    latest = json.loads((output_root / "latest.json").read_text())
    assert latest["run_id"] == result["run_id"]
    assert latest["run_path"] == result["run_path"]
