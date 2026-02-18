from __future__ import annotations

from collections import Counter


class ValidationError(RuntimeError):
    pass


def validate_teams(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    required = ["season", "run_date", "team_id", "team_name", "composite_score"]

    for idx, row in enumerate(rows):
        for field in required:
            if field not in row or row[field] in (None, ""):
                errors.append(f"teams[{idx}] missing required field: {field}")

        for pct_field in ["fielding_pct"]:
            val = row.get(pct_field, 0)
            if not (0 <= val <= 1.0):
                errors.append(f"teams[{idx}] invalid {pct_field}: {val}")

    keys = [(r.get("season"), r.get("run_date"), r.get("team_id")) for r in rows]
    dupes = [key for key, count in Counter(keys).items() if count > 1]
    for key in dupes:
        errors.append(f"duplicate team key found: {key}")

    return errors


def validate_players(rows: list[dict], team_rows: list[dict]) -> list[str]:
    errors: list[str] = []
    team_ids = {team["team_id"] for team in team_rows}
    required = ["season", "run_date", "player_id", "player_name", "team_id"]

    for idx, row in enumerate(rows):
        for field in required:
            if field not in row or row[field] in (None, ""):
                errors.append(f"players[{idx}] missing required field: {field}")
        if row.get("team_id") not in team_ids:
            errors.append(
                f"players[{idx}] references unknown team_id: {row.get('team_id')}"
            )

    return errors


def raise_if_errors(errors: list[str]) -> None:
    if errors:
        formatted = "\n".join(errors)
        raise ValidationError(f"Validation failed:\n{formatted}")
