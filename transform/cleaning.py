from __future__ import annotations

from typing import Any


TEAM_NUMERIC_FIELDS = [
    "g",
    "ab",
    "r",
    "h",
    "2b",
    "3b",
    "hr",
    "bb",
    "so",
    "sb",
    "era",
    "ip",
    "ha",
    "wh",
    "er",
    "k",
    "opp_ba",
    "fe",
]

PLAYER_NUMERIC_FIELDS = [
    "g",
    "ab",
    "r",
    "h",
    "2b",
    "3b",
    "hr",
    "bb",
    "so",
    "sb",
    "ip",
    "er",
    "k",
    "ha",
]


def clean_team_rows(rows: list[dict[str, Any]], run_date: str, season: int) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["run_date"] = row.get("run_date", run_date)
        item["season"] = int(row.get("season", season))
        item["team_id"] = str(row["team_id"]).strip()
        item["team_name"] = str(row["team_name"]).strip()
        item["conference"] = str(row.get("conference", "Unknown")).strip()

        for field in TEAM_NUMERIC_FIELDS:
            item[field] = _to_float(row.get(field, 0))

        cleaned.append(item)
    return cleaned


def clean_player_rows(rows: list[dict[str, Any]], run_date: str, season: int) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["run_date"] = row.get("run_date", run_date)
        item["season"] = int(row.get("season", season))
        item["player_id"] = str(row["player_id"]).strip()
        item["player_name"] = str(row["player_name"]).strip()
        item["team_id"] = str(row["team_id"]).strip()
        item["class_year"] = str(row.get("class_year", "UNK")).strip()
        item["position"] = str(row.get("position", "UTIL")).strip()

        for field in PLAYER_NUMERIC_FIELDS:
            item[field] = _to_float(row.get(field, 0))

        cleaned.append(item)
    return cleaned


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", ""))
