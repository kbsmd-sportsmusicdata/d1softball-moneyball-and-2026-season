from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build social-ready assets from H&S outputs.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/hs_table1"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/hs_table1/social"))
    parser.add_argument("--top-n", type=int, default=5, help="Top N over/under performers to highlight.")
    parser.add_argument("--min-games", type=int, default=30, help="Minimum games for over/under eligibility.")
    return parser.parse_args()


def _load_inputs(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    team_inputs = pd.read_csv(input_dir / "team_season_hs_inputs.csv")
    table1 = pd.read_csv(input_dir / "table1_results.csv")

    for col in ["wpc", "obpfor", "obpagn", "slgfor", "slgagn", "year", "games"]:
        team_inputs[col] = pd.to_numeric(team_inputs[col], errors="coerce")
    team_inputs = team_inputs.dropna(subset=["wpc", "obpfor", "obpagn", "slgfor", "slgagn", "year", "games"]).copy()

    return team_inputs, table1


def _fit_model_and_residuals(team_inputs: pd.DataFrame) -> tuple[pd.DataFrame, any]:
    formula = "wpc ~ obpfor + obpagn + slgfor + slgagn"
    fit = smf.ols(formula=formula, data=team_inputs).fit()

    df = team_inputs.copy()
    df["predicted_wpc"] = fit.predict(df)
    df["residual_wpc"] = df["wpc"] - df["predicted_wpc"]
    df["obp_diff"] = df["obpfor"] - df["obpagn"]
    return df, fit


def _build_over_under(df: pd.DataFrame, top_n: int, min_games: int) -> pd.DataFrame:
    eligible = df[df["games"] >= min_games].copy()
    if eligible.empty:
        eligible = df.copy()

    over = eligible.sort_values("residual_wpc", ascending=False).head(top_n).copy()
    under = eligible.sort_values("residual_wpc", ascending=True).head(top_n).copy()

    over["bucket"] = "overperformer"
    under["bucket"] = "underperformer"

    out = pd.concat([over, under], ignore_index=True)
    out["label"] = out["Team"].astype(str) + " (" + out["year"].astype(int).astype(str) + ")"
    out = out[[
        "bucket",
        "year",
        "Team",
        "wpc",
        "predicted_wpc",
        "residual_wpc",
        "obpfor",
        "obpagn",
        "slgfor",
        "slgagn",
        "label",
    ]]
    return out


def _save_table1_card(table1: pd.DataFrame, output_path: Path) -> None:
    model_order = ["1", "2", "3", "4"]
    summary_rows: list[str] = []

    for model in model_order:
        subset = table1[table1["model"].astype(str) == model].copy()
        if subset.empty:
            continue
        formula = subset["formula"].iloc[0]
        r2 = subset["r_squared"].iloc[0]
        coeffs = []
        for _, row in subset.iterrows():
            if row["term"] == "Intercept":
                continue
            coeffs.append(f"{row['term']}={row['coef']:.3f}")
        coeff_txt = ", ".join(coeffs)
        summary_rows.append(f"Model {model}: {formula}")
        summary_rows.append(f"R²={r2:.3f} | {coeff_txt}")
        summary_rows.append("")

    plt.figure(figsize=(13, 7), dpi=180)
    ax = plt.gca()
    ax.axis("off")

    plt.text(0.02, 0.93, "D1 Softball: H&S Table-1 Rebuild (2021-2025)", fontsize=22, fontweight="bold")
    plt.text(
        0.02,
        0.86,
        "Win% regressions using OBP/SLG for and against, aggregated from game logs with home/away splits.",
        fontsize=12,
        color="#333333",
    )

    y = 0.74
    for line in summary_rows:
        style = dict(fontsize=11, color="#1f1f1f")
        if line.startswith("Model"):
            style = dict(fontsize=12, fontweight="bold", color="#102a43")
        plt.text(0.03, y, line, **style)
        y -= 0.065 if line else 0.03

    plt.text(0.02, 0.06, "Source: sportsdataverse/softballR-data | Build: scripts/build_social_outputs.py", fontsize=9, color="#666")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


def _save_trend_chart(df: pd.DataFrame, output_path: Path) -> None:
    plt.figure(figsize=(11, 7), dpi=180)
    ax = plt.gca()

    years = sorted(df["year"].dropna().astype(int).unique().tolist())
    cmap = plt.get_cmap("viridis", len(years))
    year_to_color = {year: cmap(i) for i, year in enumerate(years)}

    for year in years:
        sub = df[df["year"] == year]
        ax.scatter(sub["obp_diff"], sub["wpc"], s=24, alpha=0.55, color=year_to_color[year], label=str(year))

    x = df["obp_diff"].to_numpy()
    y = df["wpc"].to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    x_line = np.linspace(x.min(), x.max(), 200)
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, color="#111111", linewidth=2.2, label="All-season fit")

    corr = np.corrcoef(x, y)[0, 1]
    ax.set_title("Season Trend: OBP Edge vs Win% (2021-2025)", fontsize=16, fontweight="bold")
    ax.set_xlabel("OBP Differential (OBPFOR - OBPAGN)")
    ax.set_ylabel("Winning Percentage (wpc)")
    ax.grid(alpha=0.2)
    ax.text(0.02, 0.96, f"Correlation: {corr:.3f}", transform=ax.transAxes, fontsize=10, va="top")

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[: len(years)] + [handles[-1]], labels[: len(years)] + [labels[-1]], ncol=3, fontsize=9, frameon=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


def _save_over_under_card(over_under: pd.DataFrame, output_path: Path, top_n: int) -> None:
    over = over_under[over_under["bucket"] == "overperformer"].sort_values("residual_wpc", ascending=False).head(top_n)
    under = over_under[over_under["bucket"] == "underperformer"].sort_values("residual_wpc", ascending=True).head(top_n)

    plot_df = pd.concat([under, over], ignore_index=True)
    labels = plot_df["label"].tolist()
    values = plot_df["residual_wpc"].tolist()
    colors = ["#b91c1c" if v < 0 else "#166534" for v in values]

    plt.figure(figsize=(12, 8), dpi=180)
    ax = plt.gca()
    ypos = np.arange(len(labels))
    ax.barh(ypos, values, color=colors, alpha=0.9)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=10)
    ax.axvline(0, color="#111111", linewidth=1.2)
    ax.set_xlabel("Actual WPC - Model-Predicted WPC")
    ax.set_title("Top Over/Under Performers vs Model Expectation", fontsize=16, fontweight="bold")
    ax.grid(axis="x", alpha=0.2)

    for i, v in enumerate(values):
        offset = 0.004 if v >= 0 else -0.004
        ha = "left" if v >= 0 else "right"
        ax.text(v + offset, i, f"{v:+.3f}", va="center", ha=ha, fontsize=9)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, bbox_inches="tight")
    plt.close()


def _write_over_under_markdown(over_under: pd.DataFrame, path: Path) -> None:
    lines = [
        "# Top Over/Under Performers (Actual WPC minus Predicted WPC)",
        "",
        "| bucket | year | team | wpc | predicted_wpc | residual_wpc |",
        "|---|---:|---|---:|---:|---:|",
    ]

    for _, row in over_under.sort_values(["bucket", "residual_wpc"], ascending=[True, False]).iterrows():
        lines.append(
            f"| {row['bucket']} | {int(row['year'])} | {row['Team']} | {row['wpc']:.3f} | {row['predicted_wpc']:.3f} | {row['residual_wpc']:+.3f} |"
        )

    path.write_text("\n".join(lines))


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    team_inputs, table1 = _load_inputs(input_dir)
    with_resid, _ = _fit_model_and_residuals(team_inputs)
    over_under = _build_over_under(with_resid, top_n=args.top_n, min_games=args.min_games)

    over_under.to_csv(output_dir / "top_over_under_performers.csv", index=False)
    _write_over_under_markdown(over_under, output_dir / "top_over_under_performers.md")

    _save_table1_card(table1, output_dir / "table1_card.png")
    _save_trend_chart(with_resid, output_dir / "season_trend_obp_diff_vs_wpc.png")
    _save_over_under_card(over_under, output_dir / "top_over_under_performers.png", top_n=args.top_n)

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "team_season_rows": int(len(team_inputs)),
        "min_games_threshold": int(args.min_games),
        "eligible_team_rows": int((with_resid["games"] >= args.min_games).sum()),
        "over_under_rows": int(len(over_under)),
        "artifacts": [
            "table1_card.png",
            "season_trend_obp_diff_vs_wpc.png",
            "top_over_under_performers.png",
            "top_over_under_performers.csv",
            "top_over_under_performers.md",
        ],
    }
    payload = json.dumps(summary, indent=2)
    (output_dir / "social_summary.json").write_text(payload)
    print(payload)


if __name__ == "__main__":
    main()
