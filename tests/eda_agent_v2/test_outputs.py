from __future__ import annotations

import json
from pathlib import Path

import nbformat

from eda_agent.config import EDARunConfig
from eda_agent.runners import run_agent


def _write_softball_dataset(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "teams.csv").write_text(
        "team_id,team_name,composite_score,composite_rank,offense_z,pitching_z,discipline_z,defense_z,whip,era\n"
        "alpha,Alpha,2.4,1,1.3,1.2,0.6,0.7,1.0,1.9\n"
        "beta,Beta,1.9,2,1.2,1.1,0.5,0.4,1.1,2.1\n"
    )
    (folder / "players.csv").write_text(
        "player_id,player_name,team_id,team_name,ab,ops,iso,hr,k,ip,so\n"
        "p1,Slugger One,alpha,Alpha,100,1.220,0.420,15,18,0,18\n"
        "p2,Ace Arm,alpha,Alpha,10,0.500,0.050,0,120,98.0,0\n"
    )


def test_full_output_contract(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_softball_dataset(tmp_path / "data" / "processed" / "2026-04-10")

    result = run_agent(
        EDARunConfig(
            repo_root=tmp_path,
            run_label="artifact-test",
            output_root=tmp_path / "eda_runs",
            llm_enabled=False,
        )
    )

    run_dir = Path(result["run_path"])
    assert run_dir.exists()
    assert (run_dir / "run_metadata.json").exists()
    assert (run_dir / "dataset_profile.json").exists()
    assert (run_dir / "findings.json").exists()
    assert (run_dir / "storyboard.json").exists()
    assert (run_dir / "deeper_analysis.json").exists()
    assert (run_dir / "summary.md").exists()
    assert (run_dir / "run_log.ipynb").exists()

    metadata = json.loads((run_dir / "run_metadata.json").read_text())
    assert metadata["schema_version"] == "eda_agent_v2"
    assert metadata["config"]["profile_name"] == "softball"
    assert isinstance(metadata["config"]["qualification_rules"], list)

    latest = json.loads((tmp_path / "eda_runs" / "latest.json").read_text())
    assert latest["run_id"] == result["run_id"]
    notebook = nbformat.read(run_dir / "run_log.ipynb", as_version=4)
    assert len(notebook.cells) >= 8
