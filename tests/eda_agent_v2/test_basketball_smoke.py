from __future__ import annotations

import json
from pathlib import Path

from eda_agent.config import EDARunConfig
from eda_agent.runners import run_agent


def _write_basketball_dataset(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "teams.csv").write_text(
        "team_id,team_name,net_rating,off_rating,def_rating,assist_rate,turnover_rate,opp_fg_pct\n"
        "alpha,Alpha,18.5,112.4,94.0,0.68,0.15,0.41\n"
        "beta,Beta,12.1,108.1,96.0,0.61,0.18,0.44\n"
    )
    (folder / "players.csv").write_text(
        "player_id,player_name,team_id,team_name,minutes,points,assists,rebounds,usage_rate,turnover_rate,three_pointers,steals\n"
        "p1,Lead Guard,alpha,Alpha,32.1,18.4,7.2,4.1,0.24,0.11,2.4,1.9\n"
        "p2,Primary Wing,alpha,Alpha,31.0,21.0,3.0,6.5,0.28,0.09,3.1,1.3\n"
        "p3,Stretch Four,beta,Beta,29.5,15.2,2.6,7.9,0.21,0.10,2.0,0.8\n"
    )


def test_basketball_profile_smoke(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_basketball_dataset(tmp_path / "basketball-repo" / "data" / "processed" / "2026-02-01")

    result = run_agent(
        EDARunConfig(
            repo_root=tmp_path / "basketball-repo",
            profile_name="basketball",
            run_label="basketball-smoke",
            output_root=tmp_path / "eda_runs",
            llm_enabled=False,
        )
    )

    run_dir = Path(result["run_path"])
    findings = json.loads((run_dir / "findings.json").read_text())
    assert 5 <= len(findings) <= 10
    categories = {item["category"] for item in findings}
    assert {"analytical", "elite_talent", "coaching", "fan_first"}.issubset(categories)
    assert any("Lead Guard" in json.dumps(finding) or "Primary Wing" in json.dumps(finding) for finding in findings)
