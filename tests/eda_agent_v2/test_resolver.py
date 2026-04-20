from __future__ import annotations

import json
from pathlib import Path

from eda_agent.config import EDARunConfig
from eda_agent.resolvers import DatasetResolver


def _write_dataset(folder: Path, team_header: str = "team_id", player_header: str = "player_id") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "teams.csv").write_text(f"{team_header}\nalpha\n")
    (folder / "players.csv").write_text(f"{player_header}\np1\n")


def test_latest_processed_resolution(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    _write_dataset(tmp_path / "data" / "processed" / "2026-03-01")
    _write_dataset(tmp_path / "data" / "processed" / "2026-04-10")

    bundle = DatasetResolver.resolve_bundle(EDARunConfig())
    assert bundle.resolution_mode == "latest_processed"
    assert bundle.teams_path.as_posix().endswith("data/processed/2026-04-10/teams.csv")
    assert bundle.profile_name in {"softball", "generic"}


def test_explicit_paths_resolution(tmp_path: Path):
    data_root = tmp_path / "repo"
    _write_dataset(data_root / "data" / "processed" / "2026-04-10")

    teams = data_root / "data" / "processed" / "2026-04-10" / "teams.csv"
    players = data_root / "data" / "processed" / "2026-04-10" / "players.csv"
    bundle = DatasetResolver.resolve_bundle(EDARunConfig(teams_path=teams, players_path=players, repo_root=data_root))
    assert bundle.resolution_mode == "explicit"
    assert bundle.teams_path == teams
    assert bundle.players_path == players
    assert bundle.source_root == data_root


def test_manifest_resolution(tmp_path: Path):
    repo_root = tmp_path / "basketball-repo"
    _write_dataset(repo_root / "data" / "processed" / "2026-04-10", team_header="team_name", player_header="player_name")
    manifest = tmp_path / "eda_agent.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source_root": str(repo_root),
                "dataset_label": "basketball-repo",
                "dataset_version": "2026-04-10",
                "profile_name": "basketball",
                "teams_path": "data/processed/2026-04-10/teams.csv",
                "players_path": "data/processed/2026-04-10/players.csv",
            }
        )
    )

    bundle = DatasetResolver.resolve_bundle(EDARunConfig(manifest_path=manifest))
    assert bundle.resolution_mode == "manifest"
    assert bundle.profile_name == "basketball"
    assert bundle.dataset_label == "basketball-repo"


def test_manifest_auto_detection_from_repo_root(tmp_path: Path):
    repo_root = tmp_path / "repo"
    _write_dataset(repo_root / "data" / "processed" / "2026-04-10")
    (repo_root / "eda_agent.manifest.json").write_text(
        json.dumps(
            {
                "source_root": str(repo_root),
                "dataset_label": "repo",
                "dataset_version": "2026-04-10",
                "profile_name": "softball",
                "teams_path": "data/processed/2026-04-10/teams.csv",
                "players_path": "data/processed/2026-04-10/players.csv",
            }
        )
    )

    bundle = DatasetResolver.resolve_bundle(EDARunConfig(repo_root=repo_root))
    assert bundle.resolution_mode == "manifest"
    assert bundle.profile_name == "softball"
    assert bundle.dataset_label == "repo"
