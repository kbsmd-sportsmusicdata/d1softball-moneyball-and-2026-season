from __future__ import annotations

import re
import time
from typing import Any

import requests

D1SOFTBALL_STATS_URL = "https://d1softball.com/statistics/"
D1SOFTBALL_TEAM_STATS_URL = "https://d1softball.com/team/{slug}/{season}/stats/"
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


def _get_text_with_retry(session: requests.Session, url: str, retries: int = 3) -> str:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_exc = exc
            if attempt == retries - 1:
                break
            time.sleep(2**attempt)

    raise RuntimeError(f"D1Softball request failed for {url}: {last_exc}")


def fetch_team_player_stats_from_d1softball(
    top25: list[dict[str, Any]],
    run_date: str,
    season: int,
    retries: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch full team pages from D1Softball and parse player totals.

    The public statistics page exposes team pages with full batting and pitching tables.
    This adapter is intentionally used as a fallback when ESPN roster/player extraction
    returns zeroed player rows.
    """

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    stats_page = _get_text_with_retry(session, D1SOFTBALL_STATS_URL, retries=retries)
    slug_map = _discover_team_slug_map(stats_page)

    team_rows: list[dict[str, Any]] = []
    player_rows: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []

    for team in top25:
        team_name = normalize_team_name(str(team["team_name"]))
        team_id = str(team["team_id"]).strip() or normalize_team_key(team_name)

        slug = _resolve_team_slug(team_name=team_name, slug_map=slug_map)
        html: str | None = None
        used_slug: str | None = None

        for candidate in _slug_candidates(team_name, slug):
            # Try the season-scoped URL first; if it fails (404 or other),
            # try the non-season variant once before giving up on this candidate.
            candidate_html = None
            try:
                candidate_html = _get_text_with_retry(
                    session,
                    D1SOFTBALL_TEAM_STATS_URL.format(slug=candidate, season=season),
                    retries=retries,
                )
            except Exception:
                try:
                    alt_url = f"https://d1softball.com/team/{candidate}/stats/"
                    candidate_html = _get_text_with_retry(session, alt_url, retries=1)
                except Exception:
                    continue
            parsed_players = parse_team_player_rows(candidate_html, team_name=team_name, team_id=team_id)
            if parsed_players:
                html = candidate_html
                used_slug = candidate
                player_rows.extend(parsed_players)
                team_rows.append(_aggregate_team_row_from_players(parsed_players, team_name=team_name, team_id=team_id))
                provenance.append(
                    {
                        "team_id": team_id,
                        "team_name": team_name,
                        "source": "d1softball",
                        "status": "live",
                        "confidence": "medium",
                        "team_slug": candidate,
                        "player_rows": len(parsed_players),
                    }
                )
                break

        if html is None or used_slug is None:
            provenance.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "source": "d1softball",
                    "status": "failed",
                    "confidence": "low",
                    "team_slug": slug,
                    "reason": "Unable to fetch or parse team stats page",
                }
            )

    return team_rows, player_rows, provenance


def parse_team_player_rows(html: str, team_name: str, team_id: str) -> list[dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    # Prefer explicit ID'd tables but fall back to detecting any table
    # with expected headers (PLAYER + AB for batting, IP/HA/ER for pitching).
    batting_table = soup.select_one("#batting-stats")
    pitching_table = soup.select_one("#pitching-stats")

    tables_to_parse: list[tuple[str, Any]] = []
    if batting_table is not None:
        tables_to_parse.append(("batting", batting_table))
    if pitching_table is not None:
        tables_to_parse.append(("pitching", pitching_table))

    # If no explicit ID'd tables, inspect all <table> elements and pick those
    # whose headers indicate they contain batting or pitching stats.
    if not tables_to_parse:
        for table in soup.select("table"):
            headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
            if not headers:
                first_row = table.select_one("tr")
                if first_row is not None:
                    headers = [c.get_text(" ", strip=True) for c in first_row.select("th,td")]
            if not headers:
                continue
            up = [h.upper() for h in headers]
            # heuristics: batting tables contain PLAYER and AB; pitching tables contain IP/HA/ER
            if any("PLAYER" in h for h in up) and any(h == "AB" or "AB" in h for h in up):
                tables_to_parse.append(("batting", table))
            elif any(h in ("IP", "IP/INN") for h in up) and any(h in ("HA", "H", "ER") for h in up):
                tables_to_parse.append(("pitching", table))

    if not tables_to_parse:
        return []

    players: dict[str, dict[str, Any]] = {}
    for kind, table in tables_to_parse:
        _merge_table_rows(
            table=table,
            players=players,
            team_name=team_name,
            team_id=team_id,
            table_kind=kind,
        )

    return list(players.values())


def _merge_table_rows(
    table: Any,
    players: dict[str, dict[str, Any]],
    team_name: str,
    team_id: str,
    table_kind: str,
) -> None:
    headers = [th.get_text(" ", strip=True) for th in table.select("thead th")]
    if not headers:
        first_row = table.select_one("tr")
        if first_row is not None:
            headers = [cell.get_text(" ", strip=True) for cell in first_row.select("th, td")]

    for tr in table.select("tbody tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
        if not cells:
            continue

        player_name = _text(cells, headers, ["Player", "Name"])
        if not player_name or player_name.lower() in {"totals", "team", "total"}:
            continue

        player_link = tr.select_one("a[href*='/player/']")
        player_key = _player_key_from_href(player_link.get("href") if player_link else None, player_name)
        if not player_key:
            continue

        row = players.setdefault(
            player_key,
            {
                "player_id": player_key,
                "player_name": player_name,
                "team_id": team_id,
                "team_name": team_name,
                "class_year": _text(cells, headers, ["Class", "Yr"], default="UNK"),
                "position": _text(cells, headers, ["POS", "Position"], default="UTIL"),
                "g": 0.0,
                "ab": 0.0,
                "r": 0.0,
                "h": 0.0,
                "2b": 0.0,
                "3b": 0.0,
                "hr": 0.0,
                "bb": 0.0,
                "so": 0.0,
                "sb": 0.0,
                "ip": 0.0,
                "er": 0.0,
                "k": 0.0,
                "ha": 0.0,
            },
        )

        row["class_year"] = row["class_year"] or _text(cells, headers, ["Class", "Yr"], default="UNK")
        row["position"] = row["position"] or _text(cells, headers, ["POS", "Position"], default="UTIL")

        if table_kind == "batting":
            row["g"] = max(row.get("g", 0.0), _num(cells, headers, ["GP", "G"]))
            row["ab"] = _num(cells, headers, ["AB"])
            row["r"] = _num(cells, headers, ["R"])
            row["h"] = _num(cells, headers, ["H"])
            row["2b"] = _num(cells, headers, ["2B"])
            row["3b"] = _num(cells, headers, ["3B"])
            row["hr"] = _num(cells, headers, ["HR"])
            row["bb"] = _num(cells, headers, ["BB"])
            row["so"] = _num(cells, headers, ["K"])
            row["sb"] = _num(cells, headers, ["SB"])
        elif table_kind == "pitching":
            row["g"] = max(row.get("g", 0.0), _num(cells, headers, ["APP", "GP", "G"]))
            row["ip"] = _num(cells, headers, ["IP"])
            row["ha"] = _num(cells, headers, ["H"])
            row["er"] = _num(cells, headers, ["ER"])
            if row.get("bb", 0.0) == 0.0:
                row["bb"] = _num(cells, headers, ["BB"])
            row["k"] = _num(cells, headers, ["K"])
            if row.get("position") in {"UTIL", ""}:
                row["position"] = "P"


def _aggregate_team_row_from_players(players: list[dict[str, Any]], team_name: str, team_id: str) -> dict[str, Any]:
    batting_players = [p for p in players if float(p.get("ab", 0.0) or 0.0) > 0.0]
    pitching_players = [p for p in players if float(p.get("ip", 0.0) or 0.0) > 0.0]

    def _sum(field: str, source: list[dict[str, Any]]) -> float:
        return sum(_to_float(p.get(field, 0.0)) for p in source)

    batting_games = max((_to_float(p.get("g", 0.0)) for p in batting_players), default=0.0)
    pitching_games = max((_to_float(p.get("g", 0.0)) for p in pitching_players), default=0.0)
    games = max(batting_games, pitching_games, 0.0)

    ab = _sum("ab", batting_players)
    h = _sum("h", batting_players)
    doubles = _sum("2b", batting_players)
    triples = _sum("3b", batting_players)
    hr = _sum("hr", batting_players)
    bb = _sum("bb", batting_players)
    pitch_bb = _sum("bb", pitching_players)
    so = _sum("so", batting_players)
    sb = _sum("sb", batting_players)
    ip = _sum("ip", pitching_players)
    ha = _sum("ha", pitching_players)
    er = _sum("er", pitching_players)
    k = _sum("k", pitching_players)
    wh = ha + pitch_bb
    opp_ba = ha / ab if ab > 0 else 0.0

    return {
        "team_id": team_id,
        "team_name": team_name,
        "conference": "Unknown",
        "g": games,
        "ab": ab,
        "r": _sum("r", batting_players),
        "h": h,
        "2b": doubles,
        "3b": triples,
        "hr": hr,
        "bb": bb,
        "so": so,
        "sb": sb,
        "ip": ip,
        "ha": ha,
        "wh": wh,
        "er": er,
        "k": k,
        "opp_ba": opp_ba,
        "fe": 0.0,
    }


def _discover_team_slug_map(html: str) -> dict[str, str]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    slug_map: dict[str, str] = {}
    for anchor in soup.select("a[href*='/team/']"):
        href = anchor.get("href") or ""
        match = re.search(r"/team/([^/]+)/", href)
        if not match:
            continue
        slug = match.group(1).strip().strip("/")
        if not slug:
            continue
        label = anchor.get_text(" ", strip=True)
        if not label:
            continue
        slug_map[normalize_team_key(label)] = slug
    return slug_map


def _resolve_team_slug(team_name: str, slug_map: dict[str, str]) -> str | None:
    team_key = normalize_team_key(team_name)
    if team_key in slug_map:
        return slug_map[team_key]

    compact = team_key.replace(" ", "")
    if compact in slug_map:
        return slug_map[compact]

    for key, slug in slug_map.items():
        if key in team_key or team_key in key:
            return slug
    return None


def _slug_candidates(team_name: str, resolved_slug: str | None) -> list[str]:
    candidates: list[str] = []
    if resolved_slug:
        candidates.append(resolved_slug)

    team_key = normalize_team_key(team_name)
    candidate_forms = [
        team_key,
        team_key.replace(" ", "-"),
        team_key.replace(" ", ""),
        re.sub(r"[^a-z0-9]+", "-", team_key).strip("-"),
    ]
    for candidate in candidate_forms:
        candidate = candidate.strip().strip("-")
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _player_key_from_href(href: str | None, player_name: str) -> str:
    if href:
        match = re.search(r"/player/([^/?#]+)/?", href)
        if match:
            return match.group(1).strip().strip("/")
        cleaned = href.rstrip("/").split("/")[-1].strip()
        if cleaned:
            return cleaned
    return normalize_player_key(player_name)


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


def _find_col_idx(headers: list[str], aliases: list[str]) -> int | None:
    normalized_headers = [re.sub(r"\s+", "", h).upper() for h in headers]
    normalized_aliases = [re.sub(r"\s+", "", a).upper() for a in aliases]
    for alias in normalized_aliases:
        if alias in normalized_headers:
            return normalized_headers.index(alias)
    return None


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


def normalize_team_name(team_name: str) -> str:
    cleaned = re.sub(r"\s+", " ", team_name).strip()
    cleaned = cleaned.replace("St.", "State")
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
