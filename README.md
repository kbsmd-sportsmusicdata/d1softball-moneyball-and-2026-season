# NCAA D1 Softball Stats Pipeline + Dashboard

This project scrapes, cleans, enriches, and publishes NCAA D1 softball stats (Top 25 focus) and renders a static Next.js dashboard.

## Quick start

### Pipeline

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/build_dataset.py --fixtures --season 2026 --run-date 2026-02-17
```

Live run (production scraping):

```bash
python3 scripts/build_dataset.py --season 2026 --run-date 2026-02-17
```

Notes:
- Live mode requires ESPN Top 25 to return all 25 teams; otherwise the run aborts for completeness.
- NCAA org-id hard overrides can be set in `fixtures/team_org_id_overrides.json`.
- Parser contract fixtures live in `fixtures/contract/`.

### Tests

```bash
pytest
```

Parser-only smoke check (works without full pytest run):

```bash
python3 scripts/smoke_parsers.py
```

### Dashboard

```bash
cd dashboard
npm install
npm run build
npm run dev
```

## Data outputs

- `data/public/latest/teams.json`
- `data/public/latest/players.json`
- `data/public/latest/leaderboards.json`
- `data/public/history/team_trends.json`
- `data/public/latest/metadata.json`

## H&S Table-1 Rebuild (D1 Softball 2021-2025)

Run the notebook-equivalent analysis (home/away game-log aggregation + OBP/SLG regressions):

```bash
python3 scripts/hs_table1_softball.py --start-season 2021 --end-season 2025
```

Outputs are written to `data/hs_table1/`:

- `game_team_logs_2021_2025.csv` (+ parquet best-effort)
- `team_season_hs_inputs.csv` (+ parquet best-effort)
- `chart_ready_team_season.csv`
- `table1_results.csv`
- `table1_results.md`
- `season_coverage_report.csv`
- `season_coverage_report.json`

Notes:
- Source: `sportsdataverse/softballR-data` D1 hitting + NCAA scoreboard files.
- Coverage gate defaults to 95% parsed games per season (`--coverage-threshold`).
- When coverage is below threshold, the script attempts NCAA contest-level fallback for missing game IDs before failing.

## Social-Ready Output Layer

Generate social assets from `data/hs_table1/`:

```bash
python3 scripts/build_social_outputs.py --input-dir data/hs_table1 --output-dir visuals/hs_table1 --top-n 5 --min-games 30
```

Assets written to `visuals/hs_table1/`:

- `visuals/hs_table1/table1_card.png`
- `visuals/hs_table1/season_trend_obp_diff_vs_wpc.png`
- `visuals/hs_table1/top_over_under_performers.png`
- `visuals/hs_table1/top_over_under_performers.csv`
- `visuals/hs_table1/top_over_under_performers.md`
- `visuals/hs_table1/social_summary.json`
- `visuals/hs_table1/release_notes.md`

## Storytelling Posts

Generate ready-to-post captions from the same dataset:

```bash
python3 scripts/storytelling_hs_posts.py --input-dir data/hs_table1 --social-dir visuals/hs_table1 --output visuals/hs_table1/storytelling_posts.md --min-games 30
```

Outputs:

- `visuals/hs_table1/storytelling_posts.md`
- `visuals/hs_table1/storytelling_posts.json`

## Project Structure

```text
data/
  raw/
  processed/
  public/
  hs_table1/
scripts/
visuals/
  hs_table1/
dashboard/
fixtures/
ingestion/
transform/
tests/
```
