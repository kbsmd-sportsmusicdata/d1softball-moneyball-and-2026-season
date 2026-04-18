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
- Live mode first tries the ESPN/USA Softball Top 25 poll, then falls back to the checked-in poll fixture if ESPN returns incomplete results.
- Live player extraction prefers ESPN, but if player rows are zeroed or the ESPN fetch fails, the build backfills player totals from D1Softball team pages.
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

### Manual Workbook Report

Regenerate the polished HTML-ready report artifacts for the April 2026 workbook import:

```bash
make report
```

Outputs:

- `reports/d1softball_manual_april2026/report.md`
- `reports/d1softball_manual_april2026/report_data.json`
- `reports/d1softball_manual_april2026/report_metadata.json`
- `reports/d1softball_manual_april2026/figures/*.svg`

Dashboard route:

- `dashboard/app/report/page.tsx` renders the report as a polished HTML page.

GitHub Actions:

- `build-report-bundle` runs the same workflow in GitHub with a `handoff_mode` input (`none`, `related`, or `full`).
- `deploy-dashboard` now refreshes Pages when the report bundle changes under `reports/d1softball_manual_april2026/`.

## EDA Analyst Agent v1

Run notebook-style EDA on the latest processed team/player datasets:

```bash
python3 scripts/eda_analyst_agent.py
```

Optional path overrides:

```bash
python3 scripts/eda_analyst_agent.py \
  --teams-path data/processed/2026-04-10/teams.csv \
  --players-path data/processed/2026-04-10/players.csv \
  --run-label first-pass
```

Outputs per run:

- `eda_runs/YYYY-MM-DDTHHMMSSZ/run_log.ipynb`
- `eda_runs/YYYY-MM-DDTHHMMSSZ/run_metadata.json`
- `eda_runs/YYYY-MM-DDTHHMMSSZ/dataset_profile.json`
- `eda_runs/YYYY-MM-DDTHHMMSSZ/findings.json`
- `eda_runs/YYYY-MM-DDTHHMMSSZ/storyboard.json`
- `eda_runs/YYYY-MM-DDTHHMMSSZ/deeper_analysis.json`
- `eda_runs/YYYY-MM-DDTHHMMSSZ/summary.md`
- `eda_runs/latest.json`

Dashboard viewer:

- `dashboard/app/eda/page.tsx` renders the latest run from `eda_runs/latest.json`.

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
eda_runs/
scripts/
visuals/
  hs_table1/
dashboard/
fixtures/
ingestion/
transform/
tests/
```
