from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests

from ingestion.sources.espn_poll import canonical_team_id, normalize_team_name

NCAA_BASE_URL = "https://stats.ncaa.org"
USER_AGENT = "Mozilla/5.0 (compatible; SoftballStatsBot/1.0)"
ORG_ID_OVERRIDES_PATH = Path("fixtures/team_org_id_overrides.json")


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

    Live flow:
    - Resolve NCAA org_id for each Top 25 team
    - Pull team stats page for each org_id
    - Parse one team aggregate row + player rows
    - Per-team fallback to fixture rows if live fails
    """
    fallback_dir = fixture_dir or Path("fixtures")
    fallback_teams = _safe_load_json(fallback_dir / "fallback_team_stats.json")
    fallback_players = _safe_load_json(fallback_dir / "fallback_player_stats.json")

    # Explicit fixture mode only (used by local tests and deterministic CI checks).
    if fixture_dir and (fixture_dir / "ncaa_team_stats.json").exists() and (fixture_dir / "ncaa_player_stats.json").exists():
        teams = _safe_load_json(fixture_dir / "ncaa_team_stats.json")
        players = _safe_load_json(fixture_dir / "ncaa_player_stats.json")
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

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    team_rows: list[dict[str, Any]] = []
    player_rows: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []

    for team in top25:
        team_name = normalize_team_name(str(team["team_name"]))
        team_id = canonical_team_id(team_name)
        resolved_org_id: int | None = None

        try:
            resolved_org_id = resolve_org_id(session=session, team_name=team_name, retries=retries)
            if resolved_org_id is None:
                raise SourceFetchError(f"Unable to resolve org_id for {team_name}")

            html = fetch_team_stats_html(
                session=session,
                org_id=resolved_org_id,
                season=season,
                retries=retries,
            )
            team_stat = parse_team_stat_row(html, team_name=team_name, team_id=team_id)
            players = parse_player_stat_rows(html, team_name=team_name, team_id=team_id)

            if not team_stat:
                raise SourceFetchError(f"No team stat row parsed for {team_name}")
            if not players:
                raise SourceFetchError(f"No player rows parsed for {team_name}")

            team_rows.append(team_stat)
            player_rows.extend(players)
            provenance.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "org_id": resolved_org_id,
                    "source": "ncaa",
                    "status": "live",
                    "confidence": "medium",
                }
            )
        except Exception as exc:
            fallback_team_row = _find_team_row(fallback_teams, team_id=team_id, team_name=team_name)
            fallback_player_rows = _find_player_rows(fallback_players, team_id=team_id, team_name=team_name)
            if fallback_team_row and fallback_player_rows:
                team_rows.append(fallback_team_row)
                player_rows.extend(fallback_player_rows)
                provenance.append(
                    {
                        "team_id": team_id,
                        "team_name": team_name,
                        "source": "fallback",
                        "status": "fixture_fallback",
                        "confidence": "low",
                        "org_id": resolved_org_id,
                        "reason": str(exc),
                    }
                )
            else:
                raise SourceFetchError(f"Failed live fetch and no fallback data for {team_name}")

    return team_rows, player_rows, provenance


def resolve_org_id(session: requests.Session, team_name: str, retries: int = 3) -> int | None:
    override = _lookup_org_id_override(team_name)
    if override is not None:
        return override

    candidates = [
        f"{NCAA_BASE_URL}/search?query={quote_plus(team_name)}",
        f"{NCAA_BASE_URL}/teams/search?query={quote_plus(team_name)}",
        f"{NCAA_BASE_URL}/rankings/ranking_summary",
    ]

    for url in candidates:
        html = _get_text_with_retry(session=session, url=url, retries=retries)
        org_id = _extract_org_id_from_html(html, team_name=team_name)
        if org_id is not None:
            return org_id

    return None


def _lookup_org_id_override(team_name: str) -> int | None:
    if not ORG_ID_OVERRIDES_PATH.exists():
        return None

    try:
        overrides = json.loads(ORG_ID_OVERRIDES_PATH.read_text())
    except Exception:
        return None

    normalized_target = normalize_team_name(team_name).lower()
    for key, value in overrides.items():
        if normalize_team_name(str(key)).lower() == normalized_target:
            try:
                return int(value)
            except Exception:
                return None
    return None


def fetch_team_stats_html(session: requests.Session, org_id: int, season: int, retries: int = 3) -> str:
    # Start from the canonical team stats page. NCAA often redirects this to a season-specific URL
    # carrying game_sport_year_ctl_id and id query params.
    url = f"{NCAA_BASE_URL}/team/{org_id}/stats"
    html = _get_text_with_retry(session=session, url=url, retries=retries)

    season_url = _select_season_url_from_html(html, season=season)
    if season_url:
        if season_url.startswith("/"):
            season_url = f"{NCAA_BASE_URL}{season_url}"
        html = _get_text_with_retry(session=session, url=season_url, retries=retries)

    return html


def parse_team_stat_row(html: str, team_name: str, team_id: str) -> dict[str, Any] | None:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return None

    soup = BeautifulSoup(html, "html.parser")
    table = _best_stats_table(soup)
    if table is None:
        return None

    headers = _table_headers(table)
    rows = _table_rows(table)
    if not rows:
        return None

    total_row = rows[-1]

    return {
        "team_id": team_id,
        "team_name": team_name,
        "conference": _extract_conference(soup),
        "g": _num(total_row, headers, ["GP", "G"]),
        "ab": _num(total_row, headers, ["AB"]),
        "r": _num(total_row, headers, ["R"]),
        "h": _num(total_row, headers, ["H"]),
        "2b": _num(total_row, headers, ["2B"]),
        "3b": _num(total_row, headers, ["3B"]),
        "hr": _num(total_row, headers, ["HR"]),
        "bb": _num(total_row, headers, ["BB"]),
        "so": _num(total_row, headers, ["SO", "K"]),
        "sb": _num(total_row, headers, ["SB"]),
        "ip": _num(total_row, headers, ["IP"]),
        "ha": _num(total_row, headers, ["HA", "H"]),
        "wh": _num(total_row, headers, ["WH", "BB+H", "BB + H"]),
        "er": _num(total_row, headers, ["ER"]),
        "k": _num(total_row, headers, ["SO", "K"]),
        "opp_ba": _num(total_row, headers, ["OPP BA", "BAA", "BA"]),
        "fe": _num(total_row, headers, ["E", "Errors"]),
    }


def parse_player_stat_rows(html: str, team_name: str, team_id: str) -> list[dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    table = _best_stats_table(soup)
    if table is None:
        return []

    headers = _table_headers(table)
    rows = _table_rows(table)
    if not rows:
        return []

    player_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        player_name = _text(row, headers, ["Player", "Name"])
        if not player_name or player_name.lower() in {"totals", "team", "total"}:
            continue

        player_rows.append(
            {
                "player_id": f"{team_id}-{index+1}",
                "player_name": player_name,
                "team_id": team_id,
                "team_name": team_name,
                "class_year": _text(row, headers, ["Yr", "Class"], default="UNK"),
                "position": _text(row, headers, ["Pos", "Position"], default="UTIL"),
                "g": _num(row, headers, ["GP", "G"]),
                "ab": _num(row, headers, ["AB"]),
                "r": _num(row, headers, ["R"]),
                "h": _num(row, headers, ["H"]),
                "2b": _num(row, headers, ["2B"]),
                "3b": _num(row, headers, ["3B"]),
                "hr": _num(row, headers, ["HR"]),
                "bb": _num(row, headers, ["BB"]),
                "so": _num(row, headers, ["SO", "K"]),
                "sb": _num(row, headers, ["SB"]),
                # Keep pitching columns present for downstream schema consistency.
                "ip": _num(row, headers, ["IP"]),
                "er": _num(row, headers, ["ER"]),
                "k": _num(row, headers, ["SO", "K"]),
                "ha": _num(row, headers, ["HA", "H"]),
            }
        )

    return player_rows


def _extract_org_id_from_html(html: str, team_name: str) -> int | None:
    normalized = normalize_team_name(team_name).lower()

    # Prefer nearby links that include the team name in context.
    for pattern in [r"/team/(\d+)/stats", r"/teams/(\d+)"]:
        for match in re.finditer(pattern, html):
            start = max(0, match.start() - 180)
            end = min(len(html), match.end() + 180)
            context = html[start:end].lower()
            if normalized.split()[0] in context:
                return int(match.group(1))

    # Fallback: first team-like link.
    generic = re.search(r"/team/(\d+)/stats", html)
    if generic:
        return int(generic.group(1))
    generic = re.search(r"/teams/(\d+)", html)
    if generic:
        return int(generic.group(1))

    return None


def _extract_conference(soup: Any) -> str:
    text = soup.get_text(" ", strip=True)
    conf_match = re.search(r"Conference\s*:\s*([A-Za-z0-9\-\s&\.]+)", text)
    if conf_match:
        return conf_match.group(1).strip()
    return "Unknown"


def _best_stats_table(soup: Any) -> Any | None:
    tables = soup.select("table")
    if not tables:
        return None

    scored: list[tuple[int, Any]] = []
    for table in tables:
        header_text = " ".join(th.get_text(" ", strip=True).upper() for th in table.select("th"))
        score = 0
        for token in ["PLAYER", "AB", "H", "HR", "BB", "SO"]:
            if token in header_text:
                score += 1
        scored.append((score, table))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else tables[0]


def _table_headers(table: Any) -> list[str]:
    headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
    if headers:
        return headers

    first_row = table.select_one("tr")
    if first_row is None:
        return []
    return [cell.get_text(" ", strip=True) for cell in first_row.select("th, td")]


def _table_rows(table: Any) -> list[list[str]]:
    rows: list[list[str]] = []
    body_rows = table.select("tbody tr") or table.select("tr")
    for tr in body_rows:
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        if cells:
            rows.append(cells)
    return rows


def _find_col_idx(headers: list[str], aliases: list[str]) -> int | None:
    normalized_headers = [re.sub(r"\s+", "", h).upper() for h in headers]
    normalized_aliases = [re.sub(r"\s+", "", a).upper() for a in aliases]
    for alias in normalized_aliases:
        if alias in normalized_headers:
            return normalized_headers.index(alias)
    return None


def _text(row: list[str], headers: list[str], aliases: list[str], default: str = "") -> str:
    idx = _find_col_idx(headers, aliases)
    if idx is None or idx >= len(row):
        return default
    return row[idx].strip()


def _num(row: list[str], headers: list[str], aliases: list[str]) -> float:
    raw = _text(row, headers, aliases)
    if raw in {"", "-", "--"}:
        return 0.0
    raw = raw.replace(",", "")
    if "/" in raw:
        raw = raw.split("/")[0]
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _select_season_url_from_html(html: str, season: int) -> str | None:
    # Capture option values and links carrying game_sport_year_ctl_id/id.
    direct = re.search(
        rf'href="([^"]*game_sport_year_ctl_id=\d+&id=\d+[^"]*{season}[^"]*)"',
        html,
        flags=re.IGNORECASE,
    )
    if direct:
        return direct.group(1)

    generic = re.search(r'href="([^"]*game_sport_year_ctl_id=\d+&id=\d+[^"]*)"', html, flags=re.IGNORECASE)
    if generic:
        return generic.group(1)

    option_value = re.search(rf'<option[^>]*value="([^"]+)"[^>]*>{season}</option>', html, flags=re.IGNORECASE)
    if option_value:
        return option_value.group(1)

    return None


def _safe_load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _find_team_row(rows: list[dict[str, Any]], team_id: str, team_name: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("team_id") == team_id:
            return row
    for row in rows:
        if normalize_team_name(str(row.get("team_name", ""))).lower() == team_name.lower():
            return row
    return None


def _find_player_rows(rows: list[dict[str, Any]], team_id: str, team_name: str) -> list[dict[str, Any]]:
    by_id = [row for row in rows if row.get("team_id") == team_id]
    if by_id:
        return by_id
    return [
        row
        for row in rows
        if normalize_team_name(str(row.get("team_name", ""))).lower() == team_name.lower()
    ]


def _get_text_with_retry(session: requests.Session, url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)

    raise RuntimeError("Unreachable")
