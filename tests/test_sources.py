from pathlib import Path

from ingestion.sources.espn_poll import fetch_top25
from ingestion.sources.fallbacks import fetch_fallback_stats


def test_fetch_top25_fixture():
    rows = fetch_top25("2026-02-17", 2026, fixture_path=Path("fixtures/top25_espn.json"))
    assert len(rows) == 5
    assert rows[0]["team_id"] == "tennessee"


def test_fallback_stats_fixture_shape():
    teams, players, provenance = fetch_fallback_stats("2026-02-17", 2026, fixture_dir=Path("fixtures"))
    assert teams
    assert players
    assert provenance[0]["source"] == "fallback"
