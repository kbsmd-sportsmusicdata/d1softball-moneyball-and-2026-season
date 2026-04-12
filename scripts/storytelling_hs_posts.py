from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ready-to-post storytelling insights for H&S softball outputs.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/hs_table1"))
    parser.add_argument("--social-dir", type=Path, default=Path("visuals/hs_table1"))
    parser.add_argument("--output", type=Path, default=Path("visuals/hs_table1/storytelling_posts.md"))
    parser.add_argument("--min-games", type=int, default=30)
    return parser.parse_args()


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _build_posts(
    team: pd.DataFrame, table1: pd.DataFrame, over_under: pd.DataFrame, min_games: int
) -> list[dict[str, str]]:
    team = team.copy()
    team["obp_diff"] = team["obpfor"] - team["obpagn"]
    team["games"] = pd.to_numeric(team["games"], errors="coerce").fillna(0)
    narrative = team[team["games"] >= min_games].copy()
    if narrative.empty:
        narrative = team.copy()

    model3 = table1[(table1["model"].astype(str) == "3") & (table1["term"] != "Intercept")]
    best_coeff = model3.loc[model3["coef"].abs().idxmax()]

    best_obp_edge = narrative.sort_values("obp_diff", ascending=False).iloc[0]
    worst_obp_edge = narrative.sort_values("obp_diff", ascending=True).iloc[0]

    over = over_under[over_under["bucket"] == "overperformer"].sort_values("residual_wpc", ascending=False).iloc[0]
    under = over_under[over_under["bucket"] == "underperformer"].sort_values("residual_wpc", ascending=True).iloc[0]

    by_year = (
        narrative.groupby("year", as_index=False)
        .agg(avg_obp_diff=("obp_diff", "mean"), avg_wpc=("wpc", "mean"))
        .sort_values("avg_obp_diff", ascending=False)
    )
    strongest_year = by_year.iloc[0]

    posts = [
        {
            "title": "Table 1 takeaway",
            "chart": "table1_card.png",
            "caption": (
                f"Across 2021-2025 D1 softball, the strongest coefficient in the combined model is `{best_coeff['term']}` "
                f"({best_coeff['coef']:+.3f}). Getting on base and limiting opponent baserunners still drives wins."
            ),
        },
        {
            "title": "OBP edge vs wins",
            "chart": "season_trend_obp_diff_vs_wpc.png",
            "caption": (
                f"Biggest OBP edge (min {min_games} games): {best_obp_edge['Team']} ({int(best_obp_edge['year'])}) at "
                f"{best_obp_edge['obp_diff']:+.3f} with a {_fmt_pct(best_obp_edge['wpc'])} win rate."
            ),
        },
        {
            "title": "Top overperformer",
            "chart": "top_over_under_performers.png",
            "caption": (
                f"Top overperformer vs model expectation: {over['Team']} ({int(over['year'])}), "
                f"actual {_fmt_pct(over['wpc'])} vs predicted {_fmt_pct(over['predicted_wpc'])} "
                f"(residual {over['residual_wpc']:+.3f})."
            ),
        },
        {
            "title": "Top underperformer",
            "chart": "top_over_under_performers.png",
            "caption": (
                f"Top underperformer vs model expectation: {under['Team']} ({int(under['year'])}), "
                f"actual {_fmt_pct(under['wpc'])} vs predicted {_fmt_pct(under['predicted_wpc'])} "
                f"(residual {under['residual_wpc']:+.3f})."
            ),
        },
        {
            "title": "Season-level context",
            "chart": "season_trend_obp_diff_vs_wpc.png",
            "caption": (
                f"Season with strongest average OBP differential (min {min_games} games): {int(strongest_year['year'])} "
                f"({strongest_year['avg_obp_diff']:+.3f})."
            ),
        },
    ]

    # Add one contrast note using worst OBP edge inside the last post for context.
    posts[-1]["caption"] += (
        f" At the other end, {worst_obp_edge['Team']} ({int(worst_obp_edge['year'])}) posted "
        f"{worst_obp_edge['obp_diff']:+.3f}."
    )

    return posts


def _write_markdown(posts: list[dict[str, str]], path: Path, social_dir: Path) -> None:
    lines = ["# Ready-to-Post Insights", ""]

    for i, post in enumerate(posts, start=1):
        chart_path = social_dir / post["chart"]
        lines.append(f"## Post {i}: {post['title']}")
        lines.append(f"Chart: `{chart_path}`")
        lines.append("")
        lines.append("Caption:")
        lines.append(post["caption"])
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def main() -> None:
    args = parse_args()

    team = pd.read_csv(args.input_dir / "team_season_hs_inputs.csv")
    table1 = pd.read_csv(args.input_dir / "table1_results.csv")
    over_under = pd.read_csv(args.social_dir / "top_over_under_performers.csv")

    posts = _build_posts(team, table1, over_under, min_games=args.min_games)

    _write_markdown(posts, args.output, args.social_dir)
    json_out = args.output.with_suffix(".json")
    json_out.write_text(json.dumps(posts, indent=2))

    print(json.dumps({"posts": len(posts), "markdown": str(args.output), "json": str(json_out)}, indent=2))


if __name__ == "__main__":
    main()
