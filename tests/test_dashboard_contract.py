import json
from pathlib import Path


REQUIRED_TEAM_KEYS = {
    "team_id",
    "team_name",
    "composite_score",
    "composite_rank",
    "offense_z",
    "pitching_z",
    "defense_z",
    "discipline_z",
}


def test_dashboard_contract_files_exist():
    base = Path("data/public/latest")
    assert (base / "teams.json").exists()
    assert (base / "players.json").exists()
    assert (base / "leaderboards.json").exists()
    assert (base / "metadata.json").exists()


def test_dashboard_team_schema_contract():
    teams = json.loads(Path("data/public/latest/teams.json").read_text())
    assert teams
    assert REQUIRED_TEAM_KEYS.issubset(set(teams[0].keys()))
