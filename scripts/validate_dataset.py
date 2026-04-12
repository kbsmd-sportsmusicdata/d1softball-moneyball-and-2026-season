from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from transform.validation import raise_if_errors, validate_players, validate_teams


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--min-hitters-with-ab",
        type=int,
        default=10,
        help="Minimum hitters per team with AB > 0 for Top-25 quality gate.",
    )
    args = parser.parse_args()

    teams = json.loads(Path("data/public/latest/teams.json").read_text())
    players = json.loads(Path("data/public/latest/players.json").read_text())

    errors = validate_teams(teams)
    errors.extend(validate_players(players, teams))
    quality_gate = validate_min_hitter_coverage(
        teams=teams,
        players=players,
        min_hitters_with_ab=args.min_hitters_with_ab,
    )
    errors.extend(quality_gate["errors"])

    report = {
        "errors": errors,
        "team_count": len(teams),
        "player_count": len(players),
        "quality_gates": {
            "min_hitters_with_ab": args.min_hitters_with_ab,
            "team_hitter_counts": quality_gate["team_hitter_counts"],
        },
    }
    Path("validation_report.json").write_text(json.dumps(report, indent=2))

    raise_if_errors(errors)


def validate_min_hitter_coverage(
    teams: list[dict], players: list[dict], min_hitters_with_ab: int
) -> dict:
    # Gate is intended for live Top-25 runs.
    if len(teams) < 25:
        return {"errors": [], "team_hitter_counts": {}}

    hitter_counts: dict[str, int] = defaultdict(int)
    for player in players:
        team_id = str(player.get("team_id", ""))
        if not team_id:
            continue
        try:
            ab = float(player.get("ab", 0) or 0)
        except Exception:
            ab = 0.0
        if ab > 0:
            hitter_counts[team_id] += 1

    errors: list[str] = []
    team_hitter_counts: dict[str, int] = {}
    for team in teams:
        team_id = str(team.get("team_id", ""))
        team_name = str(team.get("team_name", team_id))
        count = int(hitter_counts.get(team_id, 0))
        team_hitter_counts[team_name] = count
        if count < min_hitters_with_ab:
            errors.append(
                f"quality_gate failed: team '{team_name}' has {count} hitters with AB > 0; required >= {min_hitters_with_ab}"
            )

    return {"errors": errors, "team_hitter_counts": team_hitter_counts}


if __name__ == "__main__":
    main()
