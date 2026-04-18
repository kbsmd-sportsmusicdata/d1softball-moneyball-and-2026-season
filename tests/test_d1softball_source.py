from pathlib import Path

from ingestion.sources.d1softball import parse_d1softball_stats_html, parse_team_player_rows


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


def test_parse_team_player_rows_merges_batting_and_pitching():
    html = """
    <html>
      <body>
        <table id="batting-stats">
          <thead>
            <tr>
              <th>Player</th><th>Class</th><th>POS</th><th>GP</th><th>AB</th><th>R</th><th>H</th><th>2B</th><th>3B</th><th>HR</th><th>BB</th><th>K</th><th>SB</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><a href="/player/jane-doe/">Jane Doe</a></td><td>Sr</td><td>OF</td><td>10</td><td>20</td><td>6</td><td>8</td><td>2</td><td>1</td><td>3</td><td>4</td><td>5</td><td>1</td>
            </tr>
          </tbody>
        </table>
        <table id="pitching-stats">
          <thead>
            <tr>
              <th>Player</th><th>Class</th><th>POS</th><th>APP</th><th>IP</th><th>H</th><th>ER</th><th>BB</th><th>K</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><a href="/player/jane-doe/">Jane Doe</a></td><td>Sr</td><td>P</td><td>5</td><td>14.2</td><td>10</td><td>3</td><td>2</td><td>18</td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """

    rows = parse_team_player_rows(html, team_name="Duke", team_id="duke")
    assert len(rows) == 1
    row = rows[0]
    assert row["player_name"] == "Jane Doe"
    assert row["team_id"] == "duke"
    assert row["ab"] == 20
    assert row["h"] == 8
    assert row["hr"] == 3
    assert row["ip"] == 14.2
    assert row["er"] == 3
    assert row["k"] == 18
