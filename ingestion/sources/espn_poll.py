from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

ESPN_POLL_URL = "https://www.espn.com/college-sports/softball/rankings"


def _load_fixture(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def fetch_top25(run_date: str, season: int, fixture_path: Path | None = None) -> list[dict[str, Any]]:
    """Fetch Top 25 rankings from ESPN poll page.

    Falls back to fixture data if live fetch fails.
    """
    if fixture_path and fixture_path.exists():
        return _load_fixture(fixture_path)

    try:
        from bs4 import BeautifulSoup

        response = requests.get(ESPN_POLL_URL, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        table_rows = soup.select("table tbody tr")
        rankings: list[dict[str, Any]] = []
        for row in table_rows:
            cells = row.select("td")
            if len(cells) < 2:
                continue
            rank_text = cells[0].get_text(strip=True)
            team_name = cells[1].get_text(strip=True)
            if not rank_text.isdigit() or not team_name:
                continue
            rankings.append(
                {
                    "season": season,
                    "run_date": run_date,
                    "poll_source": "ESPN/USA Softball",
                    "rank": int(rank_text),
                    "team_id": _canonical_team_id(team_name),
                    "team_name": team_name,
                }
            )
        if rankings:
            return rankings[:25]
    except Exception:
        pass

    default_fixture = Path("fixtures/top25_espn.json")
    return _load_fixture(default_fixture)


def _canonical_team_id(team_name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in team_name).strip("-")
