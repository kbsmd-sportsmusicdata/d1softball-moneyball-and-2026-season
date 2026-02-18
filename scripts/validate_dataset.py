from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from transform.validation import raise_if_errors, validate_players, validate_teams


def main() -> None:
    teams = json.loads(Path("data/public/latest/teams.json").read_text())
    players = json.loads(Path("data/public/latest/players.json").read_text())

    errors = validate_teams(teams)
    errors.extend(validate_players(players, teams))

    report = {
        "errors": errors,
        "team_count": len(teams),
        "player_count": len(players),
    }
    Path("validation_report.json").write_text(json.dumps(report, indent=2))

    raise_if_errors(errors)


if __name__ == "__main__":
    main()
