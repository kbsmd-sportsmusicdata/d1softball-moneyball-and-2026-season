from transform.validation import validate_players, validate_teams


def test_validation_flags_unknown_team_on_player():
    teams = [
        {
            "season": 2026,
            "run_date": "2026-02-17",
            "team_id": "tennessee",
            "team_name": "Tennessee",
            "composite_score": 0.2,
            "fielding_pct": 0.9,
        }
    ]
    players = [
        {
            "season": 2026,
            "run_date": "2026-02-17",
            "player_id": "p1",
            "player_name": "Player",
            "team_id": "unknown",
        }
    ]

    assert validate_teams(teams) == []
    player_errors = validate_players(players, teams)
    assert len(player_errors) == 1
    assert "unknown team_id" in player_errors[0]
