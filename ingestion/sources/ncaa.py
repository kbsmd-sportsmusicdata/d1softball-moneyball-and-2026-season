from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

NCAA_BASE_URL = "https://stats.ncaa.org"


class SourceFetchError(RuntimeError):
    pass


def fetch_team_player_stats(
    top25: list[dict[str, Any]],
    run_date: str,
    season: int,
    fixture_dir: Path | None = None,
    retries: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return team stats, player stats, and source provenance records.

    Uses fixtures by default for reproducible local runs.
    """
    if fixture_dir is None:
        fixture_dir = Path("fixtures")

    teams_file = fixture_dir / "ncaa_team_stats.json"
    players_file = fixture_dir / "ncaa_player_stats.json"
    if teams_file.exists() and players_file.exists():
        teams = json.loads(teams_file.read_text())
        players = json.loads(players_file.read_text())
        provenance = [
            {
                "source": "ncaa",
                "status": "fixture",
                "confidence": "high",
                "run_date": run_date,
                "season": season,
            }
        ]
        return teams, players, provenance

    team_stats: list[dict[str, Any]] = []
    player_stats: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []

    for team in top25:
        team_id = team["team_id"]
        # Placeholder endpoints for live parsing expansion.
        endpoints = {
            "team": f"{NCAA_BASE_URL}/teams/{team_id}/stats?season={season}",
            "players": f"{NCAA_BASE_URL}/teams/{team_id}/players?season={season}",
        }
        try:
            team_payload = _get_json_with_retry(endpoints["team"], retries)
            player_payload = _get_json_with_retry(endpoints["players"], retries)
            team_stats.extend(team_payload)
            player_stats.extend(player_payload)
            provenance.append(
                {
                    "team_id": team_id,
                    "source": "ncaa",
                    "status": "live",
                    "confidence": "medium",
                }
            )
        except Exception as exc:
            raise SourceFetchError(f"Failed to fetch NCAA stats for {team_id}: {exc}") from exc

    return team_stats, player_stats, provenance


def _get_json_with_retry(url: str, retries: int) -> Any:
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Unreachable")
