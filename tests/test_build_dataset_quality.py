from scripts.build_dataset import _failing_player_coverage, _player_quality_by_team


def test_player_quality_by_team_counts_hitters_with_ab_gt_0():
    rows = [
        {"team_id": "alpha", "ab": 10},
        {"team_id": "alpha", "ab": 0},
        {"team_id": "beta", "ab": 1},
        {"team_id": "beta", "ab": 2},
    ]

    quality = _player_quality_by_team(rows)
    assert quality["alpha"] == 1
    assert quality["beta"] == 2


def test_failing_player_coverage_flags_teams_below_threshold():
    top25 = [
        {"team_id": "alpha", "team_name": "Alpha"},
        {"team_id": "beta", "team_name": "Beta"},
    ]
    quality = {"alpha": 10, "beta": 9}

    failures = _failing_player_coverage(top25, quality, min_hitters=10)
    assert len(failures) == 1
    assert failures[0]["team_id"] == "beta"
    assert failures[0]["ab_gt_0"] == 9
