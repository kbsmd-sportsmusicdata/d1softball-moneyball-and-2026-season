from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import statsmodels.formula.api as smf
from bs4 import BeautifulSoup

try:
    import pyreadr
except Exception:  # pragma: no cover - validated in runtime guard
    pyreadr = None

DATA_BASE_URL = "https://raw.githubusercontent.com/sportsdataverse/softballR-data/main/data"
DEFAULT_SEASONS = [2021, 2022, 2023, 2024, 2025]
USER_AGENT = "Mozilla/5.0 (compatible; SoftballStatsBot/1.0)"


@dataclass
class CoverageSummary:
    season: int
    expected_games: int
    parsed_games: int
    dropped_games: int
    coverage_pct: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recreate H&S Table-1 style analysis for D1 softball.")
    parser.add_argument("--start-season", type=int, default=2021)
    parser.add_argument("--end-season", type=int, default=2025)
    parser.add_argument("--output-dir", type=Path, default=Path("data/hs_table1"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/hs_table1_cache"))
    parser.add_argument("--coverage-threshold", type=float, default=0.95)
    parser.add_argument("--timeout", type=int, default=45)
    return parser.parse_args()


def _ensure_pyreadr_installed() -> None:
    if pyreadr is None:
        raise RuntimeError("pyreadr is required. Install dependencies via `pip install -r requirements.txt`.")


def _download(url: str, path: Path, timeout: int = 45) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return path

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def _read_rds_or_csv(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)

    _ensure_pyreadr_installed()
    result = pyreadr.read_r(str(path))
    if not result:
        return pd.DataFrame()
    first_key = next(iter(result.keys()))
    frame = result[first_key]
    if not isinstance(frame, pd.DataFrame):
        return pd.DataFrame()
    return frame


def _clean_team_name(value: Any) -> str:
    text = str(value or "").strip()
    return " ".join(text.split())


def _coerce_numeric(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for col in cols:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out


def _extract_season_from_frame(frame: pd.DataFrame, fallback: int) -> int:
    if "season" not in frame.columns or frame.empty:
        return fallback
    val = pd.to_numeric(frame["season"], errors="coerce").dropna()
    if val.empty:
        return fallback
    return int(val.iloc[0])


def _prepare_hitting_logs(raw: pd.DataFrame, season: int) -> pd.DataFrame:
    col_aliases = {
        "x2b": "x2b",
        "2b": "x2b",
        "double": "x2b",
        "doubles": "x2b",
        "x3b": "x3b",
        "3b": "x3b",
        "triple": "x3b",
        "triples": "x3b",
        "k": "k",
        "so": "k",
    }

    frame = raw.copy()
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    frame = frame.rename(columns={k: v for k, v in col_aliases.items() if k in frame.columns})

    required = ["game_id", "team", "opponent", "ab", "h", "x2b", "x3b", "hr", "bb", "hbp", "sf"]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise RuntimeError(f"Hitting source missing columns: {missing}")

    if "game_date" not in frame.columns:
        frame["game_date"] = pd.NA
    if "season" not in frame.columns:
        frame["season"] = season

    numeric_cols = ["ab", "h", "x2b", "x3b", "hr", "bb", "hbp", "sf"]
    frame = _coerce_numeric(frame, numeric_cols)

    frame["team"] = frame["team"].map(_clean_team_name)
    frame["opponent"] = frame["opponent"].map(_clean_team_name)
    frame["game_id"] = frame["game_id"].astype(str).str.strip()
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce").fillna(season).astype(int)

    grouped = (
        frame.groupby(["season", "game_id", "game_date", "team", "opponent"], as_index=False)[numeric_cols]
        .sum()
        .reset_index(drop=True)
    )
    return grouped


def _prepare_scoreboard(raw: pd.DataFrame, season: int) -> pd.DataFrame:
    frame = raw.copy()
    frame.columns = [str(c).strip().lower() for c in frame.columns]

    for required in ["game_id", "home_team", "away_team", "home_team_runs", "away_team_runs"]:
        if required not in frame.columns:
            raise RuntimeError(f"Scoreboard source missing required column: {required}")

    keep = [c for c in ["game_id", "game_date", "home_team", "away_team", "home_team_runs", "away_team_runs", "status"] if c in frame.columns]
    frame = frame[keep].copy()
    frame["game_id"] = frame["game_id"].astype(str).str.strip()
    frame["home_team"] = frame["home_team"].map(_clean_team_name)
    frame["away_team"] = frame["away_team"].map(_clean_team_name)
    frame["home_team_runs"] = pd.to_numeric(frame["home_team_runs"], errors="coerce").fillna(0.0)
    frame["away_team_runs"] = pd.to_numeric(frame["away_team_runs"], errors="coerce").fillna(0.0)
    frame["season"] = season
    return frame.drop_duplicates(subset=["game_id"]).reset_index(drop=True)


def _scrape_ncaa_hitting_totals(game_id: str, season: int, timeout: int = 45) -> pd.DataFrame:
    url = f"https://stats.ncaa.org/contests/{game_id}/individual_stats"
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    response = session.get(url, timeout=timeout)
    if response.status_code >= 400:
        return pd.DataFrame()

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    rows_out: list[dict[str, Any]] = []

    for table in tables:
        header_cells = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
        if not header_cells:
            continue
        if "ab" not in header_cells or "h" not in header_cells:
            continue

        rows = table.find_all("tr")
        total_row = None
        for row in rows[::-1]:
            cells = [td.get_text(" ", strip=True) for td in row.find_all(["td", "th"])]
            if not cells:
                continue
            if str(cells[0]).strip().lower() in {"totals", "total", "team totals"}:
                total_row = cells
                break
        if total_row is None:
            continue

        col_idx = {name: idx for idx, name in enumerate(header_cells)}

        def read(name: str) -> float:
            idx = col_idx.get(name)
            if idx is None or idx >= len(total_row):
                return 0.0
            txt = str(total_row[idx]).replace("/", "").strip()
            try:
                return float(txt)
            except ValueError:
                return 0.0

        team_name = ""
        caption = table.find("caption")
        if caption:
            team_name = _clean_team_name(caption.get_text(" ", strip=True))
        if not team_name:
            continue

        rows_out.append(
            {
                "season": season,
                "game_id": str(game_id),
                "game_date": pd.NA,
                "team": team_name,
                "opponent": "",
                "ab": read("ab"),
                "h": read("h"),
                "x2b": read("2b"),
                "x3b": read("3b"),
                "hr": read("hr"),
                "bb": read("bb"),
                "hbp": read("hbp"),
                "sf": read("sf"),
            }
        )

    if len(rows_out) < 2:
        return pd.DataFrame()

    out = pd.DataFrame(rows_out)
    if len(out) >= 2:
        out.loc[0, "opponent"] = out.loc[1, "team"]
        out.loc[1, "opponent"] = out.loc[0, "team"]
    return out


def _build_game_team_logs(hitting: pd.DataFrame, scoreboard: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = hitting.merge(scoreboard, on=["season", "game_id"], how="left", suffixes=("", "_sb"))

    merged["is_home"] = merged["team"].eq(merged["home_team"])
    merged["is_away"] = merged["team"].eq(merged["away_team"])
    matched = merged[merged["is_home"] | merged["is_away"]].copy()

    matched["runs_for"] = matched.apply(
        lambda row: row["home_team_runs"] if row["is_home"] else row["away_team_runs"], axis=1
    )
    matched["runs_against"] = matched.apply(
        lambda row: row["away_team_runs"] if row["is_home"] else row["home_team_runs"], axis=1
    )
    matched["win"] = (matched["runs_for"] > matched["runs_against"]).astype(int)

    cols = [
        "season",
        "game_id",
        "game_date",
        "team",
        "opponent",
        "is_home",
        "is_away",
        "ab",
        "h",
        "x2b",
        "x3b",
        "hr",
        "bb",
        "hbp",
        "sf",
        "runs_for",
        "runs_against",
        "win",
    ]
    matched = matched[cols].copy()

    return matched, merged


def _compute_team_season_inputs(game_logs: pd.DataFrame) -> pd.DataFrame:
    if game_logs.empty:
        return pd.DataFrame()

    # For metrics
    grouped = (
        game_logs.groupby(["season", "team"], as_index=False)[
            ["ab", "h", "x2b", "x3b", "hr", "bb", "hbp", "sf", "win"]
        ]
        .sum()
        .rename(columns={"win": "wins"})
    )
    games = game_logs.groupby(["season", "team"], as_index=False)["game_id"].nunique().rename(columns={"game_id": "games"})
    grouped = grouped.merge(games, on=["season", "team"], how="left")

    # Against metrics from opponent rows in same game
    opp = game_logs[["season", "game_id", "team", "ab", "h", "x2b", "x3b", "hr", "bb", "hbp", "sf"]].copy()
    opp = opp.rename(
        columns={
            "team": "opponent_team",
            "ab": "ab_agn",
            "h": "h_agn",
            "x2b": "x2b_agn",
            "x3b": "x3b_agn",
            "hr": "hr_agn",
            "bb": "bb_agn",
            "hbp": "hbp_agn",
            "sf": "sf_agn",
        }
    )

    base = game_logs[["season", "game_id", "team", "opponent"]].copy()
    base = base.merge(
        opp,
        left_on=["season", "game_id", "opponent"],
        right_on=["season", "game_id", "opponent_team"],
        how="left",
    )
    agn = (
        base.groupby(["season", "team"], as_index=False)[
            ["ab_agn", "h_agn", "x2b_agn", "x3b_agn", "hr_agn", "bb_agn", "hbp_agn", "sf_agn"]
        ]
        .sum()
    )

    out = grouped.merge(agn, on=["season", "team"], how="left").fillna(0.0)

    out["wpc"] = out["wins"] / out["games"].replace(0, pd.NA)
    out["obpfor"] = (out["h"] + out["bb"] + out["hbp"]) / (out["ab"] + out["bb"] + out["hbp"] + out["sf"]).replace(0, pd.NA)
    out["obpagn"] = (out["h_agn"] + out["bb_agn"] + out["hbp_agn"]) / (
        out["ab_agn"] + out["bb_agn"] + out["hbp_agn"] + out["sf_agn"]
    ).replace(0, pd.NA)

    singles_for = out["h"] - out["x2b"] - out["x3b"] - out["hr"]
    singles_agn = out["h_agn"] - out["x2b_agn"] - out["x3b_agn"] - out["hr_agn"]

    out["slgfor"] = (singles_for + 2 * out["x2b"] + 3 * out["x3b"] + 4 * out["hr"]) / out["ab"].replace(0, pd.NA)
    out["slgagn"] = (singles_agn + 2 * out["x2b_agn"] + 3 * out["x3b_agn"] + 4 * out["hr_agn"]) / out["ab_agn"].replace(0, pd.NA)

    out = out.rename(columns={"team": "Team", "season": "year", "wins": "wins", "games": "games"})
    out = out[["year", "Team", "wins", "games", "wpc", "obpfor", "obpagn", "slgfor", "slgagn"]]
    out = out.dropna(subset=["wpc", "obpfor", "obpagn", "slgfor", "slgagn"]).reset_index(drop=True)
    return out


def _run_regressions(team_inputs: pd.DataFrame) -> pd.DataFrame:
    frame = team_inputs.copy()
    for col in ["wpc", "obpfor", "obpagn", "slgfor", "slgagn"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["wpc", "obpfor", "obpagn", "slgfor", "slgagn"]).reset_index(drop=True)

    formulas = {
        "1": "wpc ~ obpfor + obpagn",
        "2": "wpc ~ slgfor + slgagn",
        "3": "wpc ~ obpfor + obpagn + slgfor + slgagn",
        "4": "wpc ~ I(obpfor - obpagn) + I(slgfor - slgagn)",
    }

    rows: list[dict[str, Any]] = []
    for model_id, formula in formulas.items():
        fit = smf.ols(formula=formula, data=frame).fit()
        ci = fit.conf_int()
        for term, coef in fit.params.items():
            rows.append(
                {
                    "model": model_id,
                    "formula": formula,
                    "term": term,
                    "coef": float(coef),
                    "std_err": float(fit.bse[term]),
                    "p_value": float(fit.pvalues[term]),
                    "ci_low": float(ci.loc[term, 0]),
                    "ci_high": float(ci.loc[term, 1]),
                    "r_squared": float(fit.rsquared),
                    "n_obs": int(fit.nobs),
                }
            )
    return pd.DataFrame(rows)


def _to_markdown_table(results: pd.DataFrame) -> str:
    if results.empty:
        return "No regression rows produced."

    out = ["# D1 Softball H&S Table-1 Style Results (2021-2025)", ""]
    for model in sorted(results["model"].unique(), key=str):
        chunk = results[results["model"] == model].copy()
        formula = chunk["formula"].iloc[0]
        out.append(f"## Model {model}")
        out.append(f"Formula: `{formula}`")
        out.append("")
        out.append("| term | coef | std_err | p_value | ci_low | ci_high | r_squared | n_obs |")
        out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for _, row in chunk.iterrows():
            out.append(
                "| {term} | {coef:.6f} | {std_err:.6f} | {p_value:.6f} | {ci_low:.6f} | {ci_high:.6f} | {r_squared:.6f} | {n_obs} |".format(
                    **row.to_dict()
                )
            )
        out.append("")
    return "\n".join(out)


def _build_coverage_summary(scoreboard: pd.DataFrame, game_logs: pd.DataFrame) -> CoverageSummary:
    expected_games = int(scoreboard["game_id"].nunique()) if not scoreboard.empty else 0
    parsed_games = int(game_logs["game_id"].nunique()) if not game_logs.empty else 0
    dropped = max(expected_games - parsed_games, 0)
    coverage = (parsed_games / expected_games) if expected_games else 0.0
    season = int(scoreboard["season"].iloc[0]) if not scoreboard.empty else -1
    return CoverageSummary(
        season=season,
        expected_games=expected_games,
        parsed_games=parsed_games,
        dropped_games=dropped,
        coverage_pct=coverage,
    )


def _load_or_download_hitting(season: int, cache_dir: Path, timeout: int) -> pd.DataFrame:
    file_name = f"d1_hitting_box_scores_{season}.RDS"
    local = cache_dir / file_name
    _download(f"{DATA_BASE_URL}/{file_name}", local, timeout=timeout)
    frame = _read_rds_or_csv(local)
    frame["season"] = _extract_season_from_frame(frame, fallback=season)
    return frame


def _load_or_download_scoreboard(season: int, cache_dir: Path, timeout: int) -> pd.DataFrame:
    file_name = f"ncaa_scoreboard_{season}.RDS"
    local = cache_dir / file_name
    _download(f"{DATA_BASE_URL}/{file_name}", local, timeout=timeout)
    frame = _read_rds_or_csv(local)
    return frame


def _write_outputs(
    output_dir: Path,
    game_logs: pd.DataFrame,
    team_inputs: pd.DataFrame,
    regressions: pd.DataFrame,
    coverage_df: pd.DataFrame,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    game_logs_path = output_dir / "game_team_logs_2021_2025.csv"
    game_logs.to_csv(game_logs_path, index=False)

    team_inputs_path = output_dir / "team_season_hs_inputs.csv"
    team_inputs.to_csv(team_inputs_path, index=False)

    chart_ready = team_inputs[["year", "Team", "wpc", "obpfor", "obpagn", "slgfor", "slgagn"]].copy()
    chart_ready.to_csv(output_dir / "chart_ready_team_season.csv", index=False)

    regressions.to_csv(output_dir / "table1_results.csv", index=False)
    (output_dir / "table1_results.md").write_text(_to_markdown_table(regressions))

    coverage_df.to_csv(output_dir / "season_coverage_report.csv", index=False)
    (output_dir / "season_coverage_report.json").write_text(coverage_df.to_json(orient="records", indent=2))

    try:
        game_logs.to_parquet(output_dir / "game_team_logs_2021_2025.parquet", index=False)
        team_inputs.to_parquet(output_dir / "team_season_hs_inputs.parquet", index=False)
    except Exception:
        # CSV outputs are required; parquet is best-effort.
        pass


def run_pipeline(
    start_season: int,
    end_season: int,
    output_dir: Path,
    cache_dir: Path,
    coverage_threshold: float,
    timeout: int,
) -> dict[str, Any]:
    all_game_logs: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, Any]] = []

    for season in range(start_season, end_season + 1):
        hitting_raw = _load_or_download_hitting(season, cache_dir=cache_dir, timeout=timeout)
        scoreboard_raw = _load_or_download_scoreboard(season, cache_dir=cache_dir, timeout=timeout)

        hitting = _prepare_hitting_logs(hitting_raw, season=season)
        scoreboard = _prepare_scoreboard(scoreboard_raw, season=season)

        game_logs, merged = _build_game_team_logs(hitting=hitting, scoreboard=scoreboard)

        summary = _build_coverage_summary(scoreboard=scoreboard, game_logs=game_logs)
        coverage_rows.append(
            {
                "season": summary.season,
                "expected_games": summary.expected_games,
                "parsed_games": summary.parsed_games,
                "dropped_games": summary.dropped_games,
                "coverage_pct": summary.coverage_pct,
            }
        )

        if summary.coverage_pct < coverage_threshold:
            # Fallback attempt for unmatched scoreboard games.
            unmatched = merged[~(merged["is_home"] | merged["is_away"])]["game_id"].dropna().astype(str).unique().tolist()
            fallback_rows: list[pd.DataFrame] = []
            for game_id in unmatched:
                fallback_df = _scrape_ncaa_hitting_totals(game_id=game_id, season=season, timeout=timeout)
                if not fallback_df.empty:
                    fallback_rows.append(fallback_df)
            if fallback_rows:
                fallback_hitting = pd.concat(fallback_rows, ignore_index=True)
                fallback_hitting = _prepare_hitting_logs(fallback_hitting, season=season)
                hitting2 = pd.concat([hitting, fallback_hitting], ignore_index=True)
                hitting2 = hitting2.drop_duplicates(subset=["season", "game_id", "team"], keep="first")
                game_logs2, _ = _build_game_team_logs(hitting=hitting2, scoreboard=scoreboard)
                summary2 = _build_coverage_summary(scoreboard=scoreboard, game_logs=game_logs2)
                coverage_rows[-1] = {
                    "season": summary2.season,
                    "expected_games": summary2.expected_games,
                    "parsed_games": summary2.parsed_games,
                    "dropped_games": summary2.dropped_games,
                    "coverage_pct": summary2.coverage_pct,
                }
                game_logs = game_logs2

        all_game_logs.append(game_logs)

    game_logs_all = pd.concat(all_game_logs, ignore_index=True) if all_game_logs else pd.DataFrame()
    team_inputs = _compute_team_season_inputs(game_logs_all)
    regressions = _run_regressions(team_inputs)
    coverage_df = pd.DataFrame(coverage_rows).sort_values("season")

    _write_outputs(output_dir=output_dir, game_logs=game_logs_all, team_inputs=team_inputs, regressions=regressions, coverage_df=coverage_df)

    failing = coverage_df[coverage_df["coverage_pct"] < coverage_threshold]
    report = {
        "start_season": start_season,
        "end_season": end_season,
        "coverage_threshold": coverage_threshold,
        "seasons": coverage_df.to_dict(orient="records"),
        "failing_seasons": failing["season"].astype(int).tolist(),
        "output_dir": str(output_dir),
        "team_rows": int(len(team_inputs)),
    }

    if not failing.empty:
        raise RuntimeError(f"Coverage gate failed for seasons: {report['failing_seasons']}")

    return report


def main() -> None:
    args = parse_args()
    report = run_pipeline(
        start_season=args.start_season,
        end_season=args.end_season,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        coverage_threshold=args.coverage_threshold,
        timeout=args.timeout,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
