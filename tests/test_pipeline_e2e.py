import json
import shutil
import subprocess
from pathlib import Path


def test_pipeline_fixture_e2e(tmp_path: Path):
    root = Path.cwd()

    for folder in ["data/raw/2026-02-17", "data/processed/2026-02-17"]:
        target = root / folder
        if target.exists():
            shutil.rmtree(target)

    cmd = [
        "python3",
        "scripts/build_dataset.py",
        "--fixtures",
        "--season",
        "2026",
        "--run-date",
        "2026-02-17",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    teams_path = root / "data/public/latest/teams.json"
    players_path = root / "data/public/latest/players.json"
    metadata_path = root / "data/public/latest/metadata.json"

    assert teams_path.exists()
    assert players_path.exists()
    assert metadata_path.exists()

    teams = json.loads(teams_path.read_text())
    assert len(teams) >= 5
    assert "composite_score" in teams[0]
