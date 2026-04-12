from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.sources.espn_poll import fetch_top25
from ingestion.sources.espn_stats import fetch_team_player_stats_from_espn
from ingestion.sources.fallbacks import fetch_fallback_stats
from ingestion.sources.ncaa import SourceFetchError, fetch_team_player_stats
from transform.cleaning import clean_player_rows, clean_team_rows
from transform.composite import apply_composite_score
from transform.metrics import add_player_derived_metrics, add_team_derived_metrics
from transform.validation import raise_if_errors, validate_players, validate_teams


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--run-date", type=str, default=datetime.now().date().isoformat())
    parser.add_argument("--fixtures", action="store_true")
    args = parser.parse_args()

    season = args.season
    run_date = args.run_date

    fixture_path = Path("fixtures/top25_espn.json") if args.fixtures else None
    top25 = fetch_top25(run_date=run_date, season=season, fixture_path=fixture_path)
    if len(top25) < 25 and not args.fixtures:
        raise RuntimeError(
            f"Top 25 poll fetch returned only {len(top25)} teams in live mode; aborting for data completeness."
        )

    teams_raw: list[dict]
    players_raw: list[dict]
    provenance: list[dict]

    if args.fixtures:
        try:
            teams_raw, players_raw, provenance = fetch_team_player_stats(
                top25=top25,
                run_date=run_date,
                season=season,
                fixture_dir=Path("fixtures"),
            )
        except SourceFetchError:
            teams_raw, players_raw, provenance = fetch_fallback_stats(
                run_date=run_date,
                season=season,
                fixture_dir=Path("fixtures"),
            )
    else:
        # Live mode priority:
        # 1) ESPN team/player ingestion (team totals + full rosters)
        # 2) NCAA ingestion
        # 3) fixture fallback
        teams_raw, players_raw, provenance = fetch_team_player_stats_from_espn(
            top25=top25,
            run_date=run_date,
            season=season,
        )
        live_espn_teams = [p for p in provenance if p.get("source") == "espn" and p.get("status") == "live"]
        if len(live_espn_teams) < len(top25):
            try:
                teams_raw, players_raw, provenance = fetch_team_player_stats(
                    top25=top25,
                    run_date=run_date,
                    season=season,
                    fixture_dir=None,
                )
            except SourceFetchError:
                teams_raw, players_raw, provenance = fetch_fallback_stats(
                    run_date=run_date,
                    season=season,
                    fixture_dir=Path("fixtures"),
                )

    teams = clean_team_rows(teams_raw, run_date=run_date, season=season)
    players = clean_player_rows(players_raw, run_date=run_date, season=season)

    teams = add_team_derived_metrics(teams)
    teams = apply_composite_score(teams)
    players = add_player_derived_metrics(players)

    errors = validate_teams(teams)
    errors.extend(validate_players(players, teams))
    raise_if_errors(errors)

    emit_outputs(top25, teams_raw, players_raw, teams, players, provenance, run_date)


def emit_outputs(
    top25: list[dict],
    teams_raw: list[dict],
    players_raw: list[dict],
    teams: list[dict],
    players: list[dict],
    provenance: list[dict],
    run_date: str,
) -> None:
    raw_dir = Path("data/raw") / run_date
    processed_dir = Path("data/processed") / run_date
    latest_dir = Path("data/public/latest")
    history_dir = Path("data/public/history")

    for directory in [raw_dir, processed_dir, latest_dir, history_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    (raw_dir / "poll.json").write_text(json.dumps(top25, indent=2))
    (raw_dir / "teams_raw.json").write_text(json.dumps(teams_raw, indent=2))
    (raw_dir / "players_raw.json").write_text(json.dumps(players_raw, indent=2))

    _write_csv(processed_dir / "teams.csv", teams)
    _write_csv(processed_dir / "players.csv", players)

    (latest_dir / "teams.json").write_text(json.dumps(teams, indent=2))
    (latest_dir / "players.json").write_text(json.dumps(players, indent=2))
    (latest_dir / "leaderboards.json").write_text(json.dumps(build_leaderboards(teams, players), indent=2))

    trends = append_trend_snapshot(history_dir / "team_trends.json", teams, run_date)
    (history_dir / "team_trends.json").write_text(json.dumps(trends, indent=2))

    metadata = {
        "schema_version": "1.0.0",
        "run_date": run_date,
        "sources": provenance,
        "warnings": [],
    }
    (latest_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))


def build_leaderboards(teams: list[dict], players: list[dict]) -> dict:
    top_composite = sorted(teams, key=lambda x: x["composite_score"], reverse=True)[:5]
    top_offense = sorted(teams, key=lambda x: x["ops"], reverse=True)[:5]
    top_pitching = sorted(teams, key=lambda x: x["whip"])[:5]
    top_players_ops = sorted(players, key=lambda x: x["ops"], reverse=True)[:10]

    return {
        "teams_composite": top_composite,
        "teams_offense": top_offense,
        "teams_pitching": top_pitching,
        "players_ops": top_players_ops,
    }


def append_trend_snapshot(path: Path, teams: list[dict], run_date: str) -> dict:
    if path.exists():
        existing = json.loads(path.read_text())
    else:
        existing = {"snapshots": []}

    snapshot = {
        "run_date": run_date,
        "teams": [
            {
                "team_id": team["team_id"],
                "team_name": team["team_name"],
                "composite_score": team["composite_score"],
                "composite_rank": team["composite_rank"],
            }
            for team in teams
        ],
    }

    existing["snapshots"] = [row for row in existing["snapshots"] if row.get("run_date") != run_date]
    existing["snapshots"].append(snapshot)

    existing["snapshots"] = existing["snapshots"][-30:]
    return existing


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
