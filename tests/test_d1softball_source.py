from pathlib import Path

from ingestion.sources.d1softball import parse_d1softball_stats_html


def test_parse_d1softball_stats_contract():
    html = Path("fixtures/contract/d1softball_stats_sample.html").read_text()
    index = parse_d1softball_stats_html(html)

    key = ("duke", "jada baker")
    assert key in index
    assert index[key]["ab"] == 51
    assert index[key]["h"] == 12
    assert index[key]["hr"] == 2
    assert index[key]["bb"] == 2
    assert index[key]["so"] == 5
