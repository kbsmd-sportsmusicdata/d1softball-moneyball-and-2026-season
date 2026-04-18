from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from transform.metrics import add_player_derived_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a manually curated D1Softball workbook into CSVs.")
    parser.add_argument(
        "--workbook-path",
        type=Path,
        default=ROOT / "data" / "raw" / "2026-02-17" / "D1Softball_Manual_April2026.xlsx",
    )
    parser.add_argument("--run-date", type=str, default="2026-04-16")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data" / "processed")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.workbook_path.exists():
        raise FileNotFoundError(args.workbook_path)

    team_batting = pd.read_excel(args.workbook_path, sheet_name="team_batting").drop(columns=["Unnamed: 0"])
    team_pitching = pd.read_excel(args.workbook_path, sheet_name="team_pitching").drop(columns=["Unnamed: 0"])
    player_batting = pd.read_excel(args.workbook_path, sheet_name="player_batting")
    player_pitching = pd.read_excel(args.workbook_path, sheet_name="player_pitching")
    rpi = pd.read_excel(args.workbook_path, sheet_name="rpi_041526")

    teams = build_team_table(team_batting, team_pitching, rpi, run_date=args.run_date, season=args.season)
    players = build_player_table(player_batting, player_pitching, run_date=args.run_date, season=args.season)

    output_dir = args.output_root / args.run_date
    output_dir.mkdir(parents=True, exist_ok=True)
    teams_path = output_dir / "teams.csv"
    players_path = output_dir / "players.csv"
    teams.to_csv(teams_path, index=False)
    players.to_csv(players_path, index=False)

    profile = {
        "schema_version": "manual_workbook_v1",
        "workbook_path": str(args.workbook_path),
        "run_date": args.run_date,
        "season": args.season,
        "sheets": {
            "team_batting": int(len(team_batting)),
            "team_pitching": int(len(team_pitching)),
            "player_batting": int(len(player_batting)),
            "player_pitching": int(len(player_pitching)),
            "rpi_041526": int(len(rpi)),
        },
        "outputs": {
            "teams_rows": int(len(teams)),
            "players_rows": int(len(players)),
            "teams_path": str(teams_path),
            "players_path": str(players_path),
        },
    }
    (output_dir / "manual_workbook_profile.json").write_text(json.dumps(profile, indent=2))
    print(json.dumps(profile, indent=2))


def build_team_table(
    team_batting: pd.DataFrame,
    team_pitching: pd.DataFrame,
    rpi: pd.DataFrame,
    run_date: str,
    season: int,
) -> pd.DataFrame:
    batting = team_batting.rename(
        columns={
            "BA": "bat_ba",
            "OBP": "obp",
            "SLG": "slg",
            "OPS": "ops",
            "GP": "games",
            "PA": "pa",
            "AB": "ab",
            "R": "runs",
            "H": "hits",
            "2B": "doubles",
            "3B": "triples",
            "HR": "hr",
            "RBI": "rbi",
            "HBP": "hbp_bat",
            "BB": "bb_bat",
            "K": "so_bat",
            "SB": "sb",
            "CS": "cs",
        }
    ).copy()

    pitching = team_pitching.rename(
        columns={
            "W": "wins",
            "L": "losses",
            "ERA": "era",
            "CG": "cg",
            "SHO": "sho",
            "SV": "sv",
            "IP": "ip",
            "H": "hits_allowed",
            "R": "runs_allowed",
            "ER": "er",
            "BB": "bb_pitch",
            "K": "k_pitch",
            "HBP": "hbp_pitch",
            "BA": "ba_against",
        }
    ).copy()

    teams = batting.merge(pitching, on="Team", how="outer")
    teams["team_id"] = teams["Team"].map(canonical_team_id)
    teams["team_name"] = teams["Team"].astype(str)
    teams["season"] = season
    teams["run_date"] = run_date
    teams["conference"] = "Manual D1Softball Workbook"
    teams["source"] = "manual_workbook"

    rpi = rpi.rename(
        columns={
            "RPI": "rpi_rank",
            "RPI.1": "rpi_points",
            "SOS": "sos",
            "Overall Record": "overall_record",
            "Home Record": "home_record",
            "Road Record": "road_record",
            "Neutral": "neutral_record",
        }
    )
    teams = teams.merge(
        rpi[
            [
                "Team",
                "rpi_rank",
                "rpi_points",
                "sos",
                "overall_record",
                "home_record",
                "road_record",
                "neutral_record",
            ]
        ],
        on="Team",
        how="left",
    )

    teams["g"] = teams["games"].fillna(teams["wins"].fillna(0) + teams["losses"].fillna(0))
    teams["r"] = teams["runs"].fillna(0)
    teams["h"] = teams["hits"].fillna(0)
    teams["2b"] = teams["doubles"].fillna(0)
    teams["3b"] = teams["triples"].fillna(0)
    teams["hr"] = teams["hr"].fillna(0)
    teams["bb"] = teams["bb_bat"].fillna(0)
    teams["so"] = teams["so_bat"].fillna(0)
    teams["ip"] = teams["ip"].fillna(0)
    teams["ha"] = teams["hits_allowed"].fillna(0)
    teams["er"] = teams["er"].fillna(0)
    teams["k"] = teams["k_pitch"].fillna(0)
    teams["wh"] = teams["ha"] + teams["bb_pitch"].fillna(0)
    teams["opp_ba"] = teams["ba_against"].fillna(0)
    teams["fe"] = 0.0

    teams["g"] = pd.to_numeric(teams["g"], errors="coerce").fillna(0)
    teams["ab"] = pd.to_numeric(teams["ab"], errors="coerce").fillna(0)
    teams["r"] = pd.to_numeric(teams["r"], errors="coerce").fillna(0)
    teams["h"] = pd.to_numeric(teams["h"], errors="coerce").fillna(0)
    teams["2b"] = pd.to_numeric(teams["2b"], errors="coerce").fillna(0)
    teams["3b"] = pd.to_numeric(teams["3b"], errors="coerce").fillna(0)
    teams["hr"] = pd.to_numeric(teams["hr"], errors="coerce").fillna(0)
    teams["bb"] = pd.to_numeric(teams["bb"], errors="coerce").fillna(0)
    teams["so"] = pd.to_numeric(teams["so"], errors="coerce").fillna(0)
    teams["ip"] = pd.to_numeric(teams["ip"], errors="coerce").fillna(0)
    teams["ha"] = pd.to_numeric(teams["ha"], errors="coerce").fillna(0)
    teams["er"] = pd.to_numeric(teams["er"], errors="coerce").fillna(0)
    teams["k"] = pd.to_numeric(teams["k"], errors="coerce").fillna(0)
    teams["bb_pitch"] = pd.to_numeric(teams["bb_pitch"], errors="coerce").fillna(0)

    singles = (teams["h"] - teams["2b"] - teams["3b"] - teams["hr"]).clip(lower=0)
    teams["avg"] = _safe_divide(teams["h"], teams["ab"]).round(4)
    teams["obp"] = _safe_divide(teams["h"] + teams["bb"], teams["ab"] + teams["bb"]).round(4)
    teams["slg"] = _safe_divide(singles + 2 * teams["2b"] + 3 * teams["3b"] + 4 * teams["hr"], teams["ab"]).round(4)
    teams["ops"] = (teams["obp"] + teams["slg"]).round(4)
    teams["iso"] = (teams["slg"] - teams["avg"]).round(4)
    teams["runs_per_game"] = _safe_divide(teams["r"], teams["g"]).round(4)
    teams["bb_k_ratio"] = _safe_divide(teams["bb"], teams["so"]).round(4)
    teams["wh"] = (teams["ha"] + teams["bb_pitch"]).round(4)
    teams["whip"] = _safe_divide(teams["wh"], teams["ip"]).round(4)
    teams["k_bb_ratio"] = _safe_divide(teams["k"], teams["bb_pitch"]).round(4)
    teams["opponent_ba"] = teams["opp_ba"].fillna(0).round(4)
    teams["errors_per_game"] = 0.0
    teams["fielding_pct"] = 1.0
    teams["era"] = teams["era"].fillna(_safe_divide(9.0 * teams["er"], teams["ip"])).round(4)

    teams["offense_z"] = _zscore(teams, ["ops", "runs_per_game", "iso"])
    teams["pitching_z"] = _zscore(teams, ["k_bb_ratio", "whip", "era"], invert=["whip", "era"])
    teams["discipline_z"] = _zscore(teams, ["bb_k_ratio"])
    teams["defense_z"] = _zscore(teams, ["fielding_pct", "errors_per_game"])
    teams["composite_score"] = (
        0.35 * teams["offense_z"]
        + 0.40 * teams["pitching_z"]
        + 0.15 * teams["discipline_z"]
        + 0.10 * teams["defense_z"]
    ).round(4)
    teams = teams.sort_values("composite_score", ascending=False).reset_index(drop=True)
    teams["composite_rank"] = range(1, len(teams) + 1)

    return teams[
        [
            "season",
            "run_date",
            "team_id",
            "team_name",
            "conference",
            "source",
            "rpi_rank",
            "rpi_points",
            "sos",
            "overall_record",
            "home_record",
            "road_record",
            "neutral_record",
            "g",
            "wins",
            "losses",
            "bat_ba",
            "obp",
            "slg",
            "ops",
            "pa",
            "ab",
            "r",
            "h",
            "2b",
            "3b",
            "hr",
            "rbi",
            "hbp_bat",
            "bb",
            "so",
            "sb",
            "cs",
            "era",
            "cg",
            "sho",
            "sv",
            "ip",
            "ha",
            "er",
            "bb_pitch",
            "k_pitch",
            "hbp_pitch",
            "ba_against",
            "wh",
            "opp_ba",
            "fe",
            "runs_per_game",
            "bb_k_ratio",
            "whip",
            "k_bb_ratio",
            "opponent_ba",
            "errors_per_game",
            "fielding_pct",
            "offense_z",
            "pitching_z",
            "discipline_z",
            "defense_z",
            "composite_score",
            "composite_rank",
        ]
    ]


def build_player_table(
    player_batting: pd.DataFrame,
    player_pitching: pd.DataFrame,
    run_date: str,
    season: int,
) -> pd.DataFrame:
    batting = player_batting.copy()
    batting["team_id"] = batting["Team"].map(canonical_team_id)
    batting["player_id"] = batting.apply(lambda row: f"{row['team_id']}-{slugify(row['Player'])}", axis=1)
    batting = batting.rename(
        columns={
            "Player": "player_name",
            "Class": "class_year",
            "POS": "position",
            "BA": "bat_ba",
            "OBP": "obp",
            "SLG": "slg",
            "OPS": "ops",
            "GP": "g",
            "PA": "pa",
            "AB": "ab",
            "R": "r",
            "H": "h",
            "2B": "2b",
            "3B": "3b",
            "HR": "hr",
            "RBI": "rbi",
            "HBP": "hbp",
            "BB": "bb",
            "K": "so",
            "SB": "sb",
            "CS": "cs",
        }
    )

    pitching = player_pitching.copy()
    pitching["team_id"] = pitching["Team"].map(canonical_team_id)
    pitching["player_id"] = pitching.apply(lambda row: f"{row['team_id']}-{slugify(row['Player'])}", axis=1)
    pitching = pitching.rename(
        columns={
            "Player": "player_name",
            "Class": "class_year",
            "W": "pit_w",
            "L": "pit_l",
            "ERA": "pit_era",
            "APP": "pit_app",
            "GS": "pit_gs",
            "CG": "pit_cg",
            "SHO": "pit_sho",
            "SV": "pit_sv",
            "IP": "ip",
            "H": "ha",
            "R": "pit_r",
            "ER": "er",
            "BB": "pit_bb",
            "K": "k",
            "HBP": "pit_hbp",
            "BA": "pit_ba",
        }
    )

    players = batting.merge(
        pitching[
            [
                "player_name",
                "Team",
                "class_year",
                "pit_w",
                "pit_l",
                "pit_era",
                "pit_app",
                "pit_gs",
                "pit_cg",
                "pit_sho",
                "pit_sv",
                "ip",
                "ha",
                "pit_r",
                "er",
                "pit_bb",
                "k",
                "pit_hbp",
                "pit_ba",
                "team_id",
                "player_id",
            ]
        ],
        on=["player_name", "Team", "class_year", "team_id", "player_id"],
        how="outer",
        suffixes=("", "_pit"),
    )

    players["season"] = season
    players["run_date"] = run_date
    players["team_name"] = players["Team"].astype(str)
    players["position"] = players["position"].fillna("UTIL")
    players["class_year"] = players["class_year"].fillna("UNK")
    for col in ["g", "ab", "r", "h", "2b", "3b", "hr", "rbi", "hbp", "bb", "so", "sb", "cs", "ip", "ha", "er", "k"]:
        players[col] = players[col].fillna(0)
    players = pd.DataFrame(add_player_derived_metrics(players.to_dict(orient="records")))

    return players[
        [
            "season",
            "run_date",
            "player_id",
            "player_name",
            "team_id",
            "team_name",
            "class_year",
            "position",
            "g",
            "ab",
            "r",
            "h",
            "2b",
            "3b",
            "hr",
            "rbi",
            "hbp",
            "bb",
            "so",
            "sb",
            "cs",
            "ip",
            "ha",
            "er",
            "k",
            "pit_w",
            "pit_l",
            "pit_era",
            "pit_app",
            "pit_gs",
            "pit_cg",
            "pit_sho",
            "pit_sv",
            "pit_bb",
            "pit_hbp",
            "pit_ba",
            "avg",
            "ops",
            "iso",
        ]
    ]


def canonical_team_id(team_name: str) -> str:
    text = str(team_name).strip().lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def slugify(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _safe_divide(numerator: pd.Series | pd.Index | Any, denominator: pd.Series | pd.Index | Any) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce").replace(0, pd.NA)
    return (numerator / denominator).fillna(0)


def _zscore(frame: pd.DataFrame, columns: list[str], invert: list[str] | None = None) -> pd.Series:
    invert = set(invert or [])
    values: list[pd.Series] = []
    for col in columns:
        series = pd.to_numeric(frame[col], errors="coerce").fillna(0).astype(float)
        mean = series.mean()
        stdev = series.std(ddof=0)
        if stdev == 0 or pd.isna(stdev):
            z = pd.Series([0.0] * len(series), index=series.index)
        else:
            z = (series - mean) / stdev
        if col in invert:
            z = -z
        values.append(z)
    if not values:
        return pd.Series([0.0] * len(frame), index=frame.index)
    return pd.concat(values, axis=1).mean(axis=1).round(4)


if __name__ == "__main__":
    main()
