from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.hs_table1_softball import (
    _build_game_team_logs,
    _build_coverage_summary,
    _compute_team_season_inputs,
    _prepare_hitting_logs,
    _prepare_scoreboard,
    _run_regressions,
    run_pipeline,
)


def _sample_hitting() -> pd.DataFrame:
    # Two games, three teams, with one duplicate row to test aggregation.
    return pd.DataFrame(
        [
            {"season": 2025, "game_id": "g1", "game_date": "2025-03-01", "team": "A", "opponent": "B", "ab": 30, "h": 10, "x2b": 2, "x3b": 1, "hr": 1, "bb": 4, "hbp": 1, "sf": 1},
            {"season": 2025, "game_id": "g1", "game_date": "2025-03-01", "team": "A", "opponent": "B", "ab": 0, "h": 0, "x2b": 0, "x3b": 0, "hr": 0, "bb": 0, "hbp": 0, "sf": 0},
            {"season": 2025, "game_id": "g1", "game_date": "2025-03-01", "team": "B", "opponent": "A", "ab": 28, "h": 8, "x2b": 1, "x3b": 0, "hr": 1, "bb": 2, "hbp": 0, "sf": 1},
            {"season": 2025, "game_id": "g2", "game_date": "2025-03-02", "team": "A", "opponent": "C", "ab": 29, "h": 9, "x2b": 1, "x3b": 0, "hr": 2, "bb": 3, "hbp": 0, "sf": 0},
            {"season": 2025, "game_id": "g2", "game_date": "2025-03-02", "team": "C", "opponent": "A", "ab": 27, "h": 7, "x2b": 0, "x3b": 0, "hr": 1, "bb": 2, "hbp": 1, "sf": 1},
        ]
    )


def _sample_scoreboard() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"game_id": "g1", "game_date": "2025-03-01", "home_team": "A", "away_team": "B", "home_team_runs": 5, "away_team_runs": 3, "status": "Final"},
            {"game_id": "g2", "game_date": "2025-03-02", "home_team": "C", "away_team": "A", "home_team_runs": 2, "away_team_runs": 6, "status": "Final"},
        ]
    )


def _sample_team_inputs_for_regression() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"year": 2021, "Team": "A", "wins": 35, "games": 50, "wpc": 0.70, "obpfor": 0.410, "obpagn": 0.300, "slgfor": 0.560, "slgagn": 0.370},
            {"year": 2021, "Team": "B", "wins": 30, "games": 50, "wpc": 0.60, "obpfor": 0.390, "obpagn": 0.320, "slgfor": 0.520, "slgagn": 0.410},
            {"year": 2021, "Team": "C", "wins": 25, "games": 50, "wpc": 0.50, "obpfor": 0.360, "obpagn": 0.340, "slgfor": 0.480, "slgagn": 0.450},
            {"year": 2022, "Team": "D", "wins": 20, "games": 50, "wpc": 0.40, "obpfor": 0.340, "obpagn": 0.360, "slgfor": 0.450, "slgagn": 0.490},
            {"year": 2022, "Team": "E", "wins": 15, "games": 50, "wpc": 0.30, "obpfor": 0.320, "obpagn": 0.380, "slgfor": 0.420, "slgagn": 0.530},
            {"year": 2022, "Team": "F", "wins": 10, "games": 50, "wpc": 0.20, "obpfor": 0.300, "obpagn": 0.400, "slgfor": 0.390, "slgagn": 0.570},
        ]
    )


def test_formula_calculation_from_game_logs():
    hitting = _prepare_hitting_logs(_sample_hitting(), season=2025)
    scoreboard = _prepare_scoreboard(_sample_scoreboard(), season=2025)
    logs, _ = _build_game_team_logs(hitting=hitting, scoreboard=scoreboard)
    inputs = _compute_team_season_inputs(logs)

    a = inputs.loc[inputs["Team"] == "A"].iloc[0]

    # Manual A totals (for):
    # AB=59 H=19 2B=3 3B=1 HR=3 BB=7 HBP=1 SF=1
    obpfor = (19 + 7 + 1) / (59 + 7 + 1 + 1)
    slgfor = ((19 - 3 - 1 - 3) + 2 * 3 + 3 * 1 + 4 * 3) / 59

    assert a["obpfor"] == pytest.approx(obpfor, rel=1e-6)
    assert a["slgfor"] == pytest.approx(slgfor, rel=1e-6)


def test_split_integrity_one_home_one_away_per_game():
    hitting = _prepare_hitting_logs(_sample_hitting(), season=2025)
    scoreboard = _prepare_scoreboard(_sample_scoreboard(), season=2025)
    logs, _ = _build_game_team_logs(hitting=hitting, scoreboard=scoreboard)

    per_game_home = logs.groupby("game_id")["is_home"].sum()
    per_game_away = logs.groupby("game_id")["is_away"].sum()

    assert (per_game_home == 1).all()
    assert (per_game_away == 1).all()


def test_aggregation_consistency_and_no_duplicates():
    hitting = _prepare_hitting_logs(_sample_hitting(), season=2025)
    scoreboard = _prepare_scoreboard(_sample_scoreboard(), season=2025)
    logs, _ = _build_game_team_logs(hitting=hitting, scoreboard=scoreboard)
    inputs = _compute_team_season_inputs(logs)

    assert not inputs.duplicated(subset=["year", "Team"]).any()
    assert (inputs["wins"] <= inputs["games"]).all()


def test_regression_reproducibility_all_four_models():
    inputs = _sample_team_inputs_for_regression()
    results = _run_regressions(inputs)

    assert set(results["model"].unique()) == {"1", "2", "3", "4"}
    assert results["coef"].notna().all()
    assert results["p_value"].notna().all()


def test_coverage_gate_fails_under_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Construct a case where scoreboard has 2 games but hitting only matches 1 game.
    hit = pd.DataFrame(
        [
            {"season": 2025, "game_id": "g1", "game_date": "2025-03-01", "team": "A", "opponent": "B", "ab": 30, "h": 10, "x2b": 2, "x3b": 1, "hr": 1, "bb": 4, "hbp": 1, "sf": 1},
            {"season": 2025, "game_id": "g1", "game_date": "2025-03-01", "team": "B", "opponent": "A", "ab": 28, "h": 8, "x2b": 1, "x3b": 0, "hr": 1, "bb": 2, "hbp": 0, "sf": 1},
        ]
    )
    sb = _sample_scoreboard()

    monkeypatch.setattr("scripts.hs_table1_softball._load_or_download_hitting", lambda season, cache_dir, timeout: hit)
    monkeypatch.setattr("scripts.hs_table1_softball._load_or_download_scoreboard", lambda season, cache_dir, timeout: sb)
    monkeypatch.setattr("scripts.hs_table1_softball._scrape_ncaa_hitting_totals", lambda game_id, season, timeout=45: pd.DataFrame())

    with pytest.raises(RuntimeError, match="Coverage gate failed"):
        run_pipeline(
            start_season=2025,
            end_season=2025,
            output_dir=tmp_path / "out",
            cache_dir=tmp_path / "cache",
            coverage_threshold=0.95,
            timeout=5,
        )


def test_coverage_summary_math():
    scoreboard = _prepare_scoreboard(_sample_scoreboard(), season=2025)
    hitting = _prepare_hitting_logs(_sample_hitting(), season=2025)
    logs, _ = _build_game_team_logs(hitting, scoreboard)
    summary = _build_coverage_summary(scoreboard, logs)

    assert summary.expected_games == 2
    assert summary.parsed_games == 2
    assert summary.dropped_games == 0
    assert summary.coverage_pct == pytest.approx(1.0)
