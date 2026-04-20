from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .contracts import DomainProfile


def coerce_numeric_frame(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in result.columns:
        if result[col].dtype == object:
            maybe_numeric = pd.to_numeric(result[col], errors="coerce")
            if maybe_numeric.notna().any():
                result[col] = maybe_numeric
    return result


def resolve_column(df: pd.DataFrame, profile: DomainProfile, entity: str, canonical_name: str) -> str | None:
    if canonical_name in df.columns:
        return canonical_name

    alias_rules = profile.alias_rules.get(entity, {})
    for alias in alias_rules.get(canonical_name, []):
        if alias in df.columns:
            return alias
    return None


def choose_metric_column(df: pd.DataFrame) -> str | None:
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    for preferred in ("composite_score", "net_rating", "points", "ops", "score", "rating"):
        if preferred in numeric_cols:
            return preferred
    for col in numeric_cols:
        if col not in {"season", "run_date"}:
            return col
    return None


def add_ratio_column(df: pd.DataFrame, numerator: str, denominator: str, output_name: str, scale: float = 1.0) -> pd.DataFrame:
    result = df.copy()
    if numerator not in result.columns or denominator not in result.columns:
        return result

    num = pd.to_numeric(result[numerator], errors="coerce")
    den = pd.to_numeric(result[denominator], errors="coerce").replace(0, pd.NA)
    result[output_name] = (num / den) * scale
    return result


def add_sum_column(df: pd.DataFrame, columns: list[str], output_name: str, *, direction: str = "higher") -> pd.DataFrame:
    result = df.copy()
    available = [col for col in columns if col in result.columns]
    if not available:
        return result
    values = pd.DataFrame({col: pd.to_numeric(result[col], errors="coerce") for col in available})
    summed = values.sum(axis=1, min_count=1)
    result[output_name] = summed if direction == "higher" else -summed
    return result


def add_abs_diff_column(df: pd.DataFrame, left: str, right: str, output_name: str) -> pd.DataFrame:
    result = df.copy()
    if left not in result.columns or right not in result.columns:
        return result
    lval = pd.to_numeric(result[left], errors="coerce")
    rval = pd.to_numeric(result[right], errors="coerce")
    result[output_name] = (lval - rval).abs()
    return result


def add_z_scores(df: pd.DataFrame, columns: list[str], prefix: str = "z_") -> pd.DataFrame:
    result = df.copy()
    for col in columns:
        if col not in result.columns:
            continue
        series = pd.to_numeric(result[col], errors="coerce")
        std = series.std(ddof=0)
        if pd.isna(std) or std == 0:
            continue
        result[f"{prefix}{col}"] = (series - series.mean()) / std
    return result


def detect_data_root(repo_root: Path | None = None) -> Path:
    return repo_root or Path.cwd()


def find_latest_processed_dataset(data_root: Path) -> tuple[Path, Path, Path]:
    processed_root = data_root / "data" / "processed"
    if not processed_root.exists():
        raise RuntimeError(f"{processed_root} directory not found.")

    candidates: list[Path] = []
    for folder in processed_root.iterdir():
        if not folder.is_dir():
            continue
        teams_csv = folder / "teams.csv"
        players_csv = folder / "players.csv"
        if teams_csv.exists() and players_csv.exists():
            candidates.append(folder)

    if not candidates:
        raise RuntimeError(f"No processed datasets found under {processed_root}.")

    latest = sorted(candidates, key=lambda p: p.name)[-1]
    return latest / "teams.csv", latest / "players.csv", latest


def read_columns(path: Path) -> set[str]:
    df = pd.read_csv(path, nrows=0)
    return {str(col) for col in df.columns.tolist()}


def infer_profile_from_paths(teams_path: Path, players_path: Path) -> str:
    headers = read_columns(teams_path) | read_columns(players_path)
    from .profiles import infer_profile_name

    return infer_profile_name(headers)


def dataframe_head_preview(df: pd.DataFrame, rows: int = 10) -> str:
    return df.head(rows).to_string(index=False)
