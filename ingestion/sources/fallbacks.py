from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def fetch_fallback_stats(run_date: str, season: int, fixture_dir: Path | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Fallback provider adapter.

    v1: serves fixture-based data with provenance marks.
    """
    if fixture_dir is None:
        fixture_dir = Path("fixtures")

    teams = json.loads((fixture_dir / "fallback_team_stats.json").read_text())
    players = json.loads((fixture_dir / "fallback_player_stats.json").read_text())
    provenance = [
        {
            "source": "fallback",
            "status": "fixture",
            "confidence": "low",
            "run_date": run_date,
            "season": season,
        }
    ]
    return teams, players, provenance
