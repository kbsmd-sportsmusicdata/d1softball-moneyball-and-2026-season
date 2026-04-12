from pathlib import Path

from ingestion.sources.espn_poll import parse_espn_rankings_html
from ingestion.sources import ncaa
from ingestion.sources.ncaa import _extract_org_id_from_html, parse_player_stat_rows, parse_team_stat_row


def test_espn_embedded_json_parser_contract():
    html = Path("fixtures/contract/espn_rankings_sample.html").read_text()
    rows = parse_espn_rankings_html(html, run_date="2026-02-17", season=2026)

    assert len(rows) == 3
    assert rows[0]["rank"] == 1
    assert rows[0]["team_id"] == "tennessee"


def test_ncaa_org_id_extraction_contract():
    html = Path("fixtures/contract/ncaa_search_sample.html").read_text()
    org_id = _extract_org_id_from_html(html, team_name="Tennessee")
    assert org_id == 522


def test_ncaa_team_and_player_parser_contract():
    html = Path("fixtures/contract/ncaa_team_stats_sample.html").read_text()
    team = parse_team_stat_row(html, team_name="Tennessee", team_id="tennessee")
    players = parse_player_stat_rows(html, team_name="Tennessee", team_id="tennessee")

    assert team is not None
    assert team["conference"] == "SEC"
    assert team["ab"] == 320
    assert team["h"] == 110
    assert team["hr"] == 18

    assert len(players) == 2
    assert players[0]["player_name"] == "Jane Doe"
    assert players[1]["position"] == "P"


def test_ncaa_live_mode_falls_back_per_team(monkeypatch):
    top25 = [{"team_name": "Tennessee", "team_id": "tennessee"}]

    monkeypatch.setattr(ncaa, "resolve_org_id", lambda session, team_name, retries=3: None)

    teams, players, provenance = ncaa.fetch_team_player_stats(
        top25=top25,
        run_date="2026-02-17",
        season=2026,
        fixture_dir=None,
    )

    assert len(teams) == 1
    assert len(players) >= 1
    assert provenance[0]["status"] == "fixture_fallback"
