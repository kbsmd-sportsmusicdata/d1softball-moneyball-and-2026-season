from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.sources.espn_poll import parse_espn_rankings_html
from ingestion.sources.ncaa import _extract_org_id_from_html, parse_player_stat_rows, parse_team_stat_row


def main() -> None:
    espn_html = Path("fixtures/contract/espn_rankings_sample.html").read_text()
    ncaa_search_html = Path("fixtures/contract/ncaa_search_sample.html").read_text()
    ncaa_stats_html = Path("fixtures/contract/ncaa_team_stats_sample.html").read_text()

    ranks = parse_espn_rankings_html(espn_html, run_date="2026-02-17", season=2026)
    assert len(ranks) == 3

    org_id = _extract_org_id_from_html(ncaa_search_html, team_name="Tennessee")
    assert org_id == 522

    team = parse_team_stat_row(ncaa_stats_html, team_name="Tennessee", team_id="tennessee")
    players = parse_player_stat_rows(ncaa_stats_html, team_name="Tennessee", team_id="tennessee")
    assert team is not None
    assert team["ab"] == 320
    assert len(players) == 2

    print("parser smoke checks passed")


if __name__ == "__main__":
    main()
