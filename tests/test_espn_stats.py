import json
from pathlib import Path

from ingestion.sources.espn_stats import EspnTeam, _match_team, _parse_pitching_totals, _parse_stat_totals


def test_match_team_handles_aliases():
    teams = [
        EspnTeam(espn_team_id="537", team_name="Tennessee Lady Volunteers", abbreviation="TENN"),
        EspnTeam(espn_team_id="201", team_name="Oklahoma Sooners", abbreviation="OU"),
    ]

    match = _match_team("Tennessee", teams, set())
    assert match is not None
    assert match.espn_team_id == "537"


def test_match_team_overrides_ambiguous_school_names():
    teams = [
        EspnTeam(espn_team_id="1237", team_name="East Texas A&M Lions", abbreviation="ETAMU"),
        EspnTeam(espn_team_id="538", team_name="Texas Longhorns", abbreviation="TEX"),
        EspnTeam(espn_team_id="535", team_name="Texas A&M Aggies", abbreviation="TAMU"),
    ]

    texas = _match_team("Texas", teams, set())
    tamu = _match_team("Texas A&M", teams, {"538"})

    assert texas is not None and texas.espn_team_id == "538"
    assert tamu is not None and tamu.espn_team_id == "535"


def test_parse_batting_totals_group_contract():
    group = json.loads(Path("fixtures/contract/espn_summary_side_sample.json").read_text())
    parsed = _parse_stat_totals(group)

    assert parsed["h"] == 9
    assert parsed["ab"] == 28
    assert parsed["r"] == 6
    assert parsed["hr"] == 2


def test_parse_pitching_totals_group_contract():
    group = {
        "type": "pitching",
        "labels": ["IP", "H", "ER", "BB", "K", "WHIP"],
        "totals": ["7.0", "6", "2", "3", "8", "1.29"],
    }
    parsed = _parse_pitching_totals(group)

    assert parsed["ip"] == 7.0
    assert parsed["ha"] == 6
    assert parsed["er"] == 2
    assert parsed["k"] == 8
