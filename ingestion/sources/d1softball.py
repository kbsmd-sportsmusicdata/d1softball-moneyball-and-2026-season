from __future__ import annotations

import re
from typing import Any

import requests

D1SOFTBALL_STATS_URL = "https://d1softball.com/statistics/"
USER_AGENT = "Mozilla/5.0 (compatible; SoftballStatsBot/1.0)"


def fetch_player_stats_index_from_d1softball(season: int) -> dict[tuple[str, str], dict[str, float]]:
    # The current page is season-scoped by site configuration and often reflects current season.
    # Keep season arg in signature for future endpoint upgrades.
    _ = season

    try:
        response = requests.get(
            D1SOFTBALL_STATS_URL,
            timeout=30,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        return parse_d1softball_stats_html(response.text)
    except Exception:
        return {}


def parse_d1softball_stats_html(html: str) -> dict[tuple[str, str], dict[str, float]]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table")
    if not tables:
        return {}

    index: dict[tuple[str, str], dict[str, float]] = {}

    for table in tables:
        headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
        if not headers:
            first_row = table.select_one("tr")
            if first_row:
                headers = [c.get_text(" ", strip=True) for c in first_row.select("th,td")]

        if not headers:
            continue

        normalized_headers = [h.upper() for h in headers]
        required = {"PLAYER", "TEAM", "AB", "H", "HR", "BB", "K"}
        if not required.issubset(set(normalized_headers)):
            continue

        rows = table.select("tbody tr") or table.select("tr")
        for tr in rows:
            cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
            if len(cells) < len(headers):
                continue

            row = {headers[i].upper(): cells[i] for i in range(len(headers))}
            player_name = row.get("PLAYER", "").strip()
            team_name = row.get("TEAM", "").strip()
            if not player_name or not team_name:
                continue

            stats = {
                "g": _to_float(row.get("GP", row.get("G", "0"))),
                "ab": _to_float(row.get("AB", "0")),
                "r": _to_float(row.get("R", "0")),
                "h": _to_float(row.get("H", "0")),
                "2b": _to_float(row.get("2B", "0")),
                "3b": _to_float(row.get("3B", "0")),
                "hr": _to_float(row.get("HR", "0")),
                "bb": _to_float(row.get("BB", "0")),
                "so": _to_float(row.get("K", "0")),
                "sb": _to_float(row.get("SB", "0")),
                "ip": 0.0,
                "er": 0.0,
                "k": 0.0,
                "ha": 0.0,
            }

            key = (normalize_team_key(team_name), normalize_player_key(player_name))
            index[key] = stats

    return index


def normalize_team_key(team_name: str) -> str:
    cleaned = team_name.lower().strip()
    cleaned = cleaned.replace("st.", "state")
    cleaned = cleaned.replace("st ", "state ")
    cleaned = cleaned.replace("&", " ")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_player_key(player_name: str) -> str:
    cleaned = player_name.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _to_float(value: str | int | float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "--"}:
        return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0
