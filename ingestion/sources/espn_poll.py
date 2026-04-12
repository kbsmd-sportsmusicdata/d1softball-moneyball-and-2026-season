from __future__ import annotations

import json
import re
from xml.etree import ElementTree as ET
from pathlib import Path
from typing import Any

import requests

ESPN_POLL_URL = "https://www.espn.com/college-sports/softball/rankings"
ESPN_SOFTBALL_RSS_URL = "https://www.espn.com/espn/rss/college-softball/news"


def _load_fixture(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def fetch_top25(run_date: str, season: int, fixture_path: Path | None = None) -> list[dict[str, Any]]:
    """Fetch Top 25 rankings from ESPN poll page.

    Strategy:
    1) fixture override (for deterministic local/test runs)
    2) live ESPN parse from embedded JSON script blocks
    3) live ESPN parse from table fallback
    4) local default fixture fallback
    """
    if fixture_path and fixture_path.exists():
        return _load_fixture(fixture_path)

    try:
        response = requests.get(
            ESPN_POLL_URL,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SoftballStatsBot/1.0)"},
        )
        response.raise_for_status()
        rankings = parse_espn_rankings_html(response.text, run_date=run_date, season=season)
        if len(rankings) >= 25:
            return rankings[:25]
    except Exception:
        pass

    story_url = discover_latest_rankings_story_url()
    if story_url:
        try:
            response = requests.get(
                story_url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SoftballStatsBot/1.0)"},
            )
            response.raise_for_status()
            rankings = parse_espn_rankings_story_html(response.text, run_date=run_date, season=season)
            if len(rankings) >= 25:
                return rankings[:25]
        except Exception:
            pass

    default_fixture = Path("fixtures/top25_espn.json")
    return _load_fixture(default_fixture)


def parse_espn_rankings_html(html: str, run_date: str, season: int) -> list[dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")

    # Preferred: parse embedded JSON structures with rank/team objects.
    from_json = _parse_rankings_from_embedded_json(soup, run_date, season)
    if from_json:
        return from_json

    # Fallback: parse visible table rows.
    rankings: list[dict[str, Any]] = []
    for row in soup.select("table tbody tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue

        rank_text = cells[0].get_text(strip=True)
        team_name = cells[1].get_text(" ", strip=True)
        if not rank_text.isdigit() or not team_name:
            continue

        rankings.append(
            {
                "season": season,
                "run_date": run_date,
                "poll_source": "ESPN/USA Softball",
                "rank": int(rank_text),
                "team_id": canonical_team_id(team_name),
                "team_name": normalize_team_name(team_name),
            }
        )

    rankings.sort(key=lambda x: x["rank"])
    return rankings


def parse_espn_rankings_story_html(html: str, run_date: str, season: int) -> list[dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    headings = [h.get_text(" ", strip=True) for h in soup.select("h2")]
    rankings: list[dict[str, Any]] = []
    for heading in headings:
        match = re.match(r"^\s*(\d{1,2})\.\s+(.+?)\s*$", heading)
        if not match:
            continue
        rank = int(match.group(1))
        if not (1 <= rank <= 25):
            continue
        team_name = normalize_team_name(match.group(2))
        rankings.append(
            {
                "season": season,
                "run_date": run_date,
                "poll_source": "ESPN/USA Softball",
                "rank": rank,
                "team_id": canonical_team_id(team_name),
                "team_name": team_name,
            }
        )

    deduped = {row["rank"]: row for row in rankings}
    return [deduped[key] for key in sorted(deduped.keys())]


def discover_latest_rankings_story_url() -> str | None:
    try:
        response = requests.get(
            ESPN_SOFTBALL_RSS_URL,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SoftballStatsBot/1.0)"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except Exception:
        return None

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").lower()
        link = (item.findtext("link") or "").strip()
        if not link:
            continue
        if "top 25" in title or "top-25" in title or "rankings" in title:
            return link

    return None


def _parse_rankings_from_embedded_json(soup: Any, run_date: str, season: int) -> list[dict[str, Any]]:
    rankings: list[dict[str, Any]] = []
    for script in soup.find_all("script"):
        payload = script.string or script.get_text("", strip=True)
        if not payload or "rank" not in payload.lower():
            continue

        if "window['__espnfitt__']" in payload or "__espnfitt__" in payload:
            for rank, team_name in re.findall(
                r'"rank"\s*:\s*(\d+).*?"displayName"\s*:\s*"([^\"]+)"',
                payload,
                flags=re.DOTALL,
            ):
                rank_num = int(rank)
                if 1 <= rank_num <= 25:
                    rankings.append(
                        {
                            "season": season,
                            "run_date": run_date,
                            "poll_source": "ESPN/USA Softball",
                            "rank": rank_num,
                            "team_id": canonical_team_id(team_name),
                            "team_name": normalize_team_name(team_name),
                        }
                    )

    if rankings:
        deduped = {row["rank"]: row for row in rankings}
        return [deduped[key] for key in sorted(deduped.keys())]
    return []


def normalize_team_name(team_name: str) -> str:
    cleaned = re.sub(r"\s+", " ", team_name).strip()
    cleaned = cleaned.replace("St.", "State")
    return cleaned


def canonical_team_id(team_name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in normalize_team_name(team_name)).strip("-")
