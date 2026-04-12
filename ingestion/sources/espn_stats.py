from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import requests

from ingestion.sources.d1softball import (
    fetch_player_stats_index_from_d1softball,
    normalize_player_key,
    normalize_team_key,
)
from ingestion.sources.espn_poll import canonical_team_id, normalize_team_name

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/baseball/college-softball"
USER_AGENT = "Mozilla/5.0 (compatible; SoftballStatsBot/1.0)"
TEAM_NAME_OVERRIDES = {
    "oklahoma": "Oklahoma Sooners",
    "alabama": "Alabama Crimson Tide",
    "texas": "Texas Longhorns",
    "texas a m": "Texas A&M Aggies",
    "washington": "Washington Huskies",
}


@dataclass
class EspnTeam:
    espn_team_id: str
    team_name: str
    abbreviation: str


def fetch_team_player_stats_from_espn(
    top25: list[dict[str, Any]],
    run_date: str,
    season: int,
    retries: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    espn_teams = _fetch_espn_teams(session=session, retries=retries)
    d1_player_index = fetch_player_stats_index_from_d1softball(season=season)
    d1_team_player_index = _build_d1_team_player_index(d1_player_index)
    teams_out: list[dict[str, Any]] = []
    players_out: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    used_espn_ids: set[str] = set()

    for poll_team in top25:
        team_name = normalize_team_name(str(poll_team["team_name"]))
        team_id = canonical_team_id(team_name)

        match = _match_team(team_name, espn_teams, used_espn_ids)
        if match is None:
            provenance.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "source": "espn",
                    "status": "failed",
                    "reason": "Unable to map ESPN team ID",
                }
            )
            continue

        try:
            roster = _fetch_team_roster(session, match.espn_team_id, retries=retries)
            team_totals, player_aggregates = _aggregate_team_totals_from_schedule(
                session=session,
                espn_team_id=match.espn_team_id,
                team_name=team_name,
                retries=retries,
            )
            teams_out.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "conference": "Unknown",
                    **team_totals,
                }
            )

            players_out.extend(
                _build_player_rows_from_roster(
                    roster=roster,
                    team_id=team_id,
                    team_name=team_name,
                    player_aggregates=player_aggregates,
                    d1_player_index=d1_player_index,
                    d1_team_player_index=d1_team_player_index,
                )
            )
            used_espn_ids.add(match.espn_team_id)

            provenance.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "source": "espn",
                    "status": "live",
                    "espn_team_id": match.espn_team_id,
                    "player_rows": len(roster),
                }
            )
        except Exception as exc:
            provenance.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "source": "espn",
                    "status": "failed",
                    "espn_team_id": match.espn_team_id,
                    "reason": str(exc),
                }
            )

    return teams_out, players_out, provenance


def _fetch_espn_teams(session: requests.Session, retries: int) -> list[EspnTeam]:
    payload = _get_json_with_retry(session, f"{ESPN_SITE_BASE}/teams?limit=600", retries)
    teams = payload.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])

    out: list[EspnTeam] = []
    for wrapper in teams:
        team = wrapper.get("team", {})
        espn_team_id = str(team.get("id", "")).strip()
        name = team.get("displayName") or team.get("shortDisplayName") or ""
        if not espn_team_id or not name:
            continue
        out.append(
            EspnTeam(
                espn_team_id=espn_team_id,
                team_name=normalize_team_name(name),
                abbreviation=str(team.get("abbreviation", "")).strip(),
            )
        )
    return out


def _fetch_team_roster(session: requests.Session, espn_team_id: str, retries: int) -> list[dict[str, Any]]:
    payload = _get_json_with_retry(session, f"{ESPN_SITE_BASE}/teams/{espn_team_id}/roster", retries)
    return payload.get("athletes", []) or []


def _aggregate_team_totals_from_schedule(
    session: requests.Session,
    espn_team_id: str,
    team_name: str,
    retries: int,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    schedule = _get_json_with_retry(session, f"{ESPN_SITE_BASE}/teams/{espn_team_id}/schedule", retries)
    events = schedule.get("events", [])

    totals = {
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
        "ha": 0.0,
        "wh": 0.0,
        "er": 0.0,
        "k": 0.0,
        "opp_ba": 0.0,
        "fe": 0.0,
    }

    games_with_totals = 0
    player_aggregates: dict[str, dict[str, float]] = {}
    for event in events:
        event_id = str(event.get("id", ""))
        if not event_id:
            continue

        summary = _get_json_with_retry(session, f"{ESPN_SITE_BASE}/summary?event={event_id}", retries)
        boxscore_players = summary.get("boxscore", {}).get("players", [])
        if not boxscore_players:
            continue

        side = _find_team_side(boxscore_players, team_name)
        if side is None:
            continue

        team_game_totals = _extract_team_totals_from_side(side)
        if team_game_totals is None:
            continue

        games_with_totals += 1
        for key in ["ab", "r", "h", "2b", "3b", "hr", "bb", "so", "sb", "ip", "ha", "wh", "er", "k", "fe"]:
            totals[key] += team_game_totals.get(key, 0.0)

        _accumulate_player_lines(side, player_aggregates)

    totals["g"] = float(games_with_totals)
    if totals["ab"] > 0:
        totals["opp_ba"] = round(totals["ha"] / totals["ab"], 4)

    return totals, player_aggregates


def _find_team_side(players_sections: list[dict[str, Any]], team_name: str) -> dict[str, Any] | None:
    target = normalize_team_name(team_name).lower()
    for side in players_sections:
        side_name = normalize_team_name(side.get("team", {}).get("displayName", "")).lower()
        if side_name == target:
            return side
    for side in players_sections:
        side_name = normalize_team_name(side.get("team", {}).get("displayName", "")).lower()
        if target.split()[0] and target.split()[0] in side_name:
            return side
    return None


def _extract_team_totals_from_side(side: dict[str, Any]) -> dict[str, float] | None:
    stats_groups = side.get("statistics", [])

    batting = next((g for g in stats_groups if str(g.get("type", "")).lower() == "batting"), None)
    pitching = next((g for g in stats_groups if str(g.get("type", "")).lower() == "pitching"), None)

    if not batting and not pitching:
        return None

    out = {"ab": 0.0, "r": 0.0, "h": 0.0, "2b": 0.0, "3b": 0.0, "hr": 0.0, "bb": 0.0, "so": 0.0, "sb": 0.0, "ip": 0.0, "ha": 0.0, "wh": 0.0, "er": 0.0, "k": 0.0, "fe": 0.0}

    if batting:
        out.update(_parse_stat_totals(batting))
    if pitching:
        out.update(_parse_pitching_totals(pitching))

    return out


def _parse_stat_totals(group: dict[str, Any]) -> dict[str, float]:
    labels = [str(x) for x in group.get("labels", [])]
    totals = [str(x) for x in group.get("totals", [])]
    mapping = {labels[i]: totals[i] for i in range(min(len(labels), len(totals)))}

    h_ab = mapping.get("H-AB", "0-0")
    h, ab = _split_pair(h_ab)

    return {
        "ab": ab,
        "h": h,
        "r": _to_float(mapping.get("R", "0")),
        "hr": _to_float(mapping.get("HR", "0")),
        "bb": _to_float(mapping.get("BB", "0")),
        "so": _to_float(mapping.get("K", "0")),
        "sb": _to_float(mapping.get("SB", "0")),
    }


def _parse_pitching_totals(group: dict[str, Any]) -> dict[str, float]:
    labels = [str(x) for x in group.get("labels", [])]
    totals = [str(x) for x in group.get("totals", [])]
    mapping = {labels[i]: totals[i] for i in range(min(len(labels), len(totals)))}

    return {
        "ip": _to_float(mapping.get("IP", "0")),
        "ha": _to_float(mapping.get("H", "0")),
        "er": _to_float(mapping.get("ER", "0")),
        "bb": _to_float(mapping.get("BB", "0")),
        "k": _to_float(mapping.get("K", "0")),
        "wh": _to_float(mapping.get("WHIP", "0")) * max(_to_float(mapping.get("IP", "0")), 0.0),
    }


def _build_player_rows_from_roster(
    roster: list[dict[str, Any]],
    team_id: str,
    team_name: str,
    player_aggregates: dict[str, dict[str, float]],
    d1_player_index: dict[tuple[str, str], dict[str, float]],
    d1_team_player_index: dict[str, list[tuple[str, dict[str, float]]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for athlete in roster:
        player_id = str(athlete.get("id", "")).strip()
        if not player_id:
            continue

        full_name = athlete.get("displayName") or athlete.get("fullName") or "Unknown"
        class_year = "UNK"
        position = athlete.get("position", {}).get("abbreviation") or "UTIL"

        aggregate = player_aggregates.get(player_id, {})
        if not _has_any_counting_stats(aggregate):
            d1_key = (normalize_team_key(team_name), normalize_player_key(str(full_name)))
            aggregate = d1_player_index.get(d1_key, aggregate)
        if not _has_any_counting_stats(aggregate):
            aggregate = _lookup_d1_player_stats_fuzzy(
                team_name=team_name,
                player_name=str(full_name),
                team_index=d1_team_player_index,
                default=aggregate,
            )

        rows.append(
            {
                "player_id": f"espn-{player_id}",
                "player_name": str(full_name),
                "team_id": team_id,
                "team_name": team_name,
                "class_year": class_year,
                "position": str(position),
                "g": aggregate.get("g", 0.0),
                "ab": aggregate.get("ab", 0.0),
                "r": aggregate.get("r", 0.0),
                "h": aggregate.get("h", 0.0),
                "2b": aggregate.get("2b", 0.0),
                "3b": aggregate.get("3b", 0.0),
                "hr": aggregate.get("hr", 0.0),
                "bb": aggregate.get("bb", 0.0),
                "so": aggregate.get("so", 0.0),
                "sb": aggregate.get("sb", 0.0),
                "ip": aggregate.get("ip", 0.0),
                "er": aggregate.get("er", 0.0),
                "k": aggregate.get("k", 0.0),
                "ha": aggregate.get("ha", 0.0),
            }
        )

    return rows


def _match_team(team_name: str, teams: list[EspnTeam], used_espn_ids: set[str]) -> EspnTeam | None:
    normalized_team = normalize_team_key(team_name)
    preferred_name = TEAM_NAME_OVERRIDES.get(normalized_team)
    if preferred_name:
        pref_norm = normalize_team_key(preferred_name)
        for t in teams:
            if t.espn_team_id in used_espn_ids:
                continue
            if normalize_team_key(t.team_name) == pref_norm:
                return t

    target_id = canonical_team_id(team_name)
    for t in teams:
        if t.espn_team_id in used_espn_ids:
            continue
        if canonical_team_id(t.team_name) == target_id:
            return t

    target_tokens = set(_tokenize(team_name))
    best: tuple[int, EspnTeam] | None = None
    for t in teams:
        if t.espn_team_id in used_espn_ids:
            continue
        tokens = set(_tokenize(t.team_name))
        score = len(target_tokens.intersection(tokens))
        if best is None or score > best[0]:
            best = (score, t)

    if best and best[0] >= max(1, len(target_tokens) - 1):
        return best[1]
    return None


def _accumulate_player_lines(side: dict[str, Any], accumulator: dict[str, dict[str, float]]) -> None:
    for group in side.get("statistics", []):
        group_type = str(group.get("type", "")).lower()
        labels = [str(x) for x in group.get("labels", [])]
        athletes = group.get("athletes", [])
        if not labels or not athletes:
            continue

        for row in athletes:
            athlete = row.get("athlete", {})
            athlete_id = str(athlete.get("id", "")).strip()
            if not athlete_id:
                continue
            stats = [str(x) for x in row.get("stats", [])]
            if athlete_id not in accumulator:
                accumulator[athlete_id] = {
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
                }
            entry = accumulator[athlete_id]
            entry["g"] += 1.0
            mapping = {labels[i]: stats[i] for i in range(min(len(labels), len(stats)))}

            if group_type == "batting":
                h, ab = _split_pair(mapping.get("H-AB", "0-0"))
                entry["ab"] += ab
                entry["h"] += h
                entry["r"] += _to_float(mapping.get("R", "0"))
                entry["hr"] += _to_float(mapping.get("HR", "0"))
                entry["bb"] += _to_float(mapping.get("BB", "0"))
                entry["so"] += _to_float(mapping.get("K", "0"))
                entry["sb"] += _to_float(mapping.get("SB", "0"))
            elif group_type == "pitching":
                entry["ip"] += _to_float(mapping.get("IP", "0"))
                entry["ha"] += _to_float(mapping.get("H", "0"))
                entry["er"] += _to_float(mapping.get("ER", "0"))
                entry["bb"] += _to_float(mapping.get("BB", "0"))
                entry["k"] += _to_float(mapping.get("K", "0"))


def _has_any_counting_stats(stats: dict[str, float]) -> bool:
    keys = ["ab", "h", "hr", "bb", "so", "sb", "ip", "er", "k", "ha", "r", "g"]
    return any(float(stats.get(k, 0.0)) > 0.0 for k in keys)


def _build_d1_team_player_index(
    d1_player_index: dict[tuple[str, str], dict[str, float]],
) -> dict[str, list[tuple[str, dict[str, float]]]]:
    out: dict[str, list[tuple[str, dict[str, float]]]] = {}
    for (team_key, player_key), stats in d1_player_index.items():
        out.setdefault(team_key, []).append((player_key, stats))
    return out


def _lookup_d1_player_stats_fuzzy(
    team_name: str,
    player_name: str,
    team_index: dict[str, list[tuple[str, dict[str, float]]]],
    default: dict[str, float],
) -> dict[str, float]:
    team_key = normalize_team_key(team_name)
    player_key = normalize_player_key(player_name)
    tokens = player_key.split()
    if not tokens:
        return default
    last = tokens[-1]
    first_initial = tokens[0][0] if tokens[0] else ""

    candidates = team_index.get(team_key, [])
    for cand_key, stats in candidates:
        cand_tokens = cand_key.split()
        if not cand_tokens:
            continue
        cand_last = cand_tokens[-1]
        cand_first_initial = cand_tokens[0][0] if cand_tokens[0] else ""
        if cand_last == last and cand_first_initial == first_initial:
            return stats
    return default


def _tokenize(name: str) -> list[str]:
    return [tok for tok in re.split(r"[^a-z0-9]+", normalize_team_name(name).lower()) if tok]


def _split_pair(value: str) -> tuple[float, float]:
    if "-" not in value:
        return 0.0, 0.0
    left, right = value.split("-", 1)
    return _to_float(left), _to_float(right)


def _to_float(value: str | int | float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _get_json_with_retry(session: requests.Session, url: str, retries: int) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {"data": payload}
        except Exception as exc:
            last_exc = exc
            if attempt == retries - 1:
                break
            time.sleep(2**attempt)

    raise RuntimeError(f"ESPN request failed for {url}: {last_exc}")
