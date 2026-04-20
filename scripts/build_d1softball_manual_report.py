from __future__ import annotations

import argparse
import json
import math
import sys
from html import escape
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.manual_notebook import render_notebook_html

PALETTE = {
    "navy": "#1B3A52",
    "copper": "#C88F5A",
    "teal": "#7A9B9E",
    "sand": "#B8956A",
    "slate": "#4F6D7A",
    "green": "#5C8A72",
    "red": "#B1554F",
    "bg": "#F5F2EE",
    "light": "#F5F2EE",
    "muted": "#6C757D",
}

REPORT_DIR = ROOT / "reports" / "d1softball_manual_april2026"
SVG_NS = "http://www.w3.org/2000/svg"


@dataclass
class FigureRef:
    path: Path
    caption: str


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*[max(0, min(255, int(v))) for v in rgb])


def _blend(color_a: str, color_b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    a = _hex_to_rgb(color_a)
    b = _hex_to_rgb(color_b)
    return _rgb_to_hex(tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))


def _write_svg(path: Path, width: int, height: int, body: list[str]) -> None:
    svg = [
        f'<svg xmlns="{SVG_NS}" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="D1 Softball report figure">',
        f'<rect width="100%" height="100%" fill="{PALETTE["bg"]}"/>',
        *body,
        "</svg>",
    ]
    path.write_text("\n".join(svg))


def _svg_text(x: float, y: float, text: str, *, size: int = 16, weight: int = 400, fill: str = None, anchor: str = "start", family: str = "Inter, Arial, sans-serif", italic: bool = False) -> str:
    fill = fill or PALETTE["navy"]
    style = "font-style:italic;" if italic else ""
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" style="{style}">'
        f"{escape(text)}"
        "</text>"
    )


def _svg_line(x1: float, y1: float, x2: float, y2: float, *, stroke: str, stroke_width: float = 1.0, dasharray: Optional[str] = None, opacity: float = 1.0) -> str:
    dash = f' stroke-dasharray="{dasharray}"' if dasharray else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{stroke_width}" stroke-opacity="{opacity}"{dash}/>'


def _svg_rect(x: float, y: float, width: float, height: float, *, fill: str, rx: float = 0.0, opacity: float = 1.0, stroke: Optional[str] = None, stroke_width: float = 1.0) -> str:
    stroke_attr = f' stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{rx}" fill="{fill}" fill-opacity="{opacity}"{stroke_attr}/>'


def _svg_circle(cx: float, cy: float, r: float, *, fill: str, stroke: str = "none", stroke_width: float = 0.0, opacity: float = 1.0) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{stroke_width}"/>'


def _svg_header(title: str, subtitle: str, *, width: int, height: int) -> list[str]:
    body = [
        _svg_rect(0, 0, width, 6, fill=PALETTE["copper"]),
        _svg_rect(0, 6, width, 92, fill=PALETTE["navy"]),
        _svg_text(44, 40, title, size=24, weight=800, fill=PALETTE["bg"], family="Montserrat, Inter, Arial, sans-serif"),
        _svg_text(44, 68, subtitle, size=12, weight=500, fill="#D6E3E3"),
    ]
    return body


def _scale(value: float, src_min: float, src_max: float, dst_min: float, dst_max: float) -> float:
    if src_max == src_min:
        return (dst_min + dst_max) / 2
    ratio = (value - src_min) / (src_max - src_min)
    return dst_min + ratio * (dst_max - dst_min)


def _axis_ticks(min_value: float, max_value: float, *, count: int = 5) -> list[float]:
    if count <= 1 or min_value == max_value:
        return [min_value]
    step = (max_value - min_value) / (count - 1)
    return [min_value + step * i for i in range(count)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a polished markdown report for the manual D1Softball workbook.")
    parser.add_argument("--teams-path", type=Path, default=ROOT / "data" / "processed" / "2026-04-16" / "teams.csv")
    parser.add_argument("--players-path", type=Path, default=ROOT / "data" / "processed" / "2026-04-16" / "players.csv")
    parser.add_argument(
        "--rpi-path",
        type=Path,
        default=ROOT / "data" / "raw" / "2026-02-17" / "D1Softball_Manual_April2026.xlsx",
    )
    parser.add_argument("--eda-run-dir", type=Path, default=ROOT / "eda_runs" / "2026-04-16T074017Z")
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    teams = pd.read_csv(args.teams_path)
    players = pd.read_csv(args.players_path)
    rpi = pd.read_excel(args.rpi_path, sheet_name="rpi_041526")
    rpi.columns = [str(c) for c in rpi.columns]

    teams = _prepare_teams(teams)
    players = _prepare_players(players)

    findings = build_findings(teams, players, rpi)
    storyboard = build_storyboard(findings)
    deeper_analysis = build_deeper_analysis(args.eda_run_dir)
    chart_refs = build_figures(teams, players, figures_dir)
    report_metadata = {
        "teams_path": str(args.teams_path),
        "players_path": str(args.players_path),
        "rpi_path": str(args.rpi_path),
        "eda_run_dir": str(args.eda_run_dir),
        "figure_count": len(chart_refs),
    }
    report_md = render_report(teams, players, rpi, chart_refs, args.eda_run_dir, output_dir)
    (output_dir / "report.md").write_text(report_md)
    report_data = build_report_data(
        teams=teams,
        players=players,
        rpi=rpi,
        figures=chart_refs,
        findings=findings,
        storyboard=storyboard,
        deeper_analysis=deeper_analysis,
        eda_run_dir=args.eda_run_dir,
        output_dir=output_dir,
        report_metadata=report_metadata,
    )
    (output_dir / "report_data.json").write_text(json.dumps(report_data, indent=2))
    (output_dir / "report_metadata.json").write_text(json.dumps(report_metadata, indent=2))
    (output_dir / "notebook.html").write_text(render_notebook_html(report_data, output_dir), encoding="utf-8")

    print(f"wrote {output_dir / 'report.md'}")
    print(f"wrote {output_dir / 'notebook.html'}")


def _prepare_teams(teams: pd.DataFrame) -> pd.DataFrame:
    out = teams.copy()
    for col in [
        "composite_score",
        "composite_rank",
        "offense_z",
        "pitching_z",
        "discipline_z",
        "defense_z",
        "ops",
        "era",
        "whip",
        "k_bb_ratio",
        "bb_k_ratio",
        "runs_per_game",
        "rpi_rank",
        "sos",
        "ip",
    ]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _prepare_players(players: pd.DataFrame) -> pd.DataFrame:
    out = players.copy()
    for col in ["ops", "ab", "hr", "rbi", "ip", "k", "er", "bb", "h", "so"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def build_figures(teams: pd.DataFrame, players: pd.DataFrame, figures_dir: Path) -> list[FigureRef]:
    figures: list[FigureRef] = []
    figures.append(plot_top_teams(teams, figures_dir / "01_top_teams.svg"))
    figures.append(plot_rpi_vs_composite(teams, figures_dir / "02_rpi_vs_composite.svg"))
    figures.append(plot_team_signal_map(teams, figures_dir / "03_team_signal_map.svg"))
    figures.append(plot_top_players(players, figures_dir / "04_top_players_ops.svg"))
    figures.append(plot_top_pitching_staffs(teams, figures_dir / "05_top_pitching_staffs.svg"))
    return figures


def plot_top_teams(teams: pd.DataFrame, path: Path) -> FigureRef:
    df = teams.dropna(subset=["composite_score"]).sort_values("composite_score", ascending=False).head(10).copy()
    width, height = 1180, 780
    left, right, top, bottom = 320, 60, 140, 80
    plot_width = width - left - right
    row_h = (height - top - bottom) / max(len(df), 1)
    max_val = float(df["composite_score"].max()) * 1.12 if len(df) else 1.0

    body = _svg_header(
        "Top 10 Teams by Composite Score",
        "Texas Tech owns the top spot, but the gap to UCLA and Oklahoma is still narrow enough to matter weekly.",
        width=width,
        height=height,
    )
    body.append(_svg_text(40, 124, "Weighted view across offense, pitching, discipline, and defense. Higher is better.", size=12, weight=500, fill=PALETTE["slate"]))
    body.append(_svg_line(left, top - 8, left, height - bottom, stroke="#D6CEC4", stroke_width=1.2))
    body.append(_svg_line(left, height - bottom, width - right, height - bottom, stroke="#D6CEC4", stroke_width=1.2))

    ticks = _axis_ticks(0.0, max_val, count=5)
    for tick in ticks:
        x = _scale(tick, 0.0, max_val, left, left + plot_width)
        body.append(_svg_line(x, height - bottom, x, height - bottom + 6, stroke="#B7AEA4", stroke_width=1.0))
        body.append(_svg_text(x, height - bottom + 24, f"{tick:.2f}", size=10, weight=500, fill=PALETTE["muted"], anchor="middle"))

    for idx, (_, row) in enumerate(df.iterrows()):
        y = top + idx * row_h + 10
        bar_h = max(18, row_h * 0.52)
        bar_w = _scale(float(row["composite_score"]), 0.0, max_val, 0.0, plot_width)
        if idx == 0:
            color = PALETTE["copper"]
        elif idx == 1:
            color = PALETTE["teal"]
        elif idx == 2:
            color = PALETTE["sand"]
        else:
            color = PALETTE["navy"]
        body.append(_svg_text(34, y + bar_h * 0.72, str(row["team_name"]), size=14, weight=700, fill=PALETTE["navy"]))
        body.append(_svg_rect(left, y, bar_w, bar_h, fill=color, rx=8, opacity=0.95))
        body.append(_svg_text(left + bar_w + 10, y + bar_h * 0.72, f"{float(row['composite_score']):.3f}", size=12, weight=700, fill=PALETTE["navy"]))

    top5 = df.head(5).reset_index(drop=True)
    if len(top5) >= 5:
        gap = float(top5.loc[0, "composite_score"] - top5.loc[4, "composite_score"])
        subtitle = f"Top five spread: {gap:.3f}. The leaders are strong, but not stretched apart."
    else:
        subtitle = "The top tier clusters tightly around the lead."
    body.append(_svg_text(width - 60, 124, subtitle, size=11, weight=500, fill=PALETTE["slate"], anchor="end"))

    _write_svg(path, width, height, body)
    return FigureRef(path=path, caption="Texas Tech leads the composite board, with UCLA and Oklahoma close enough to keep the top tier live.")


def plot_rpi_vs_composite(teams: pd.DataFrame, path: Path) -> FigureRef:
    df = teams.dropna(subset=["rpi_rank", "composite_rank"]).copy()
    df["rpi_rank"] = pd.to_numeric(df["rpi_rank"], errors="coerce")
    df["composite_rank"] = pd.to_numeric(df["composite_rank"], errors="coerce")
    df = df.dropna(subset=["rpi_rank", "composite_rank"])

    highlight = {"Arkansas", "Texas Tech", "UCLA", "Oklahoma", "Florida", "Alabama", "Nebraska"}
    width, height = 1080, 860
    left, right, top, bottom = 120, 80, 130, 110
    plot_w = width - left - right
    plot_h = height - top - bottom
    min_rank = 1.0
    max_rank = float(max(df["rpi_rank"].max(), df["composite_rank"].max()))
    corr = df[["rpi_rank", "composite_rank"]].corr().iloc[0, 1]

    body = _svg_header(
        "RPI and Composite Rank Tell Different Top-10 Stories",
        f"Correlation between the two rank systems: r = {corr:.2f}. Arkansas leads RPI; Texas Tech leads composite.",
        width=width,
        height=height,
    )
    body.append(_svg_text(40, 124, "Each point is a team. Smaller ranks are better; the 45-degree line marks agreement.", size=12, weight=500, fill=PALETTE["slate"]))
    body.append(_svg_rect(left, top, plot_w, plot_h, fill="#FFFDFC", rx=10, opacity=1.0, stroke="#D8D1C6", stroke_width=1.0))

    for tick in _axis_ticks(min_rank, max_rank, count=5):
        x = _scale(tick, min_rank, max_rank, left, left + plot_w)
        y = _scale(tick, min_rank, max_rank, top + plot_h, top)
        body.append(_svg_line(x, top + plot_h, x, top + plot_h + 6, stroke="#B7AEA4", stroke_width=1.0))
        body.append(_svg_text(x, top + plot_h + 24, f"{int(round(tick))}", size=10, weight=500, fill=PALETTE["muted"], anchor="middle"))
        body.append(_svg_line(left - 6, y, left, y, stroke="#B7AEA4", stroke_width=1.0))
        body.append(_svg_text(left - 12, y + 4, f"{int(round(tick))}", size=10, weight=500, fill=PALETTE["muted"], anchor="end"))

    body.append(_svg_line(left, top, left + plot_w, top + plot_h, stroke=PALETTE["teal"], stroke_width=1.4, dasharray="6,6", opacity=0.85))
    body.append(_svg_text(width - 62, top + plot_h + 56, "RPI rank", size=11, weight=700, fill=PALETTE["navy"], anchor="end"))
    body.append(_svg_text(22, top + plot_h / 2, "Composite rank", size=11, weight=700, fill=PALETTE["navy"], anchor="middle"))

    for _, row in df.iterrows():
        x = _scale(float(row["rpi_rank"]), min_rank, max_rank, left, left + plot_w)
        y = _scale(float(row["composite_rank"]), min_rank, max_rank, top + plot_h, top)
        color = PALETTE["copper"] if row["team_name"] in highlight else PALETTE["slate"]
        body.append(_svg_circle(x, y, 6.0, fill=color, stroke="#FFFFFF", stroke_width=1.2, opacity=0.92))

    for _, row in df[df["team_name"].isin(highlight)].iterrows():
        x = _scale(float(row["rpi_rank"]), min_rank, max_rank, left, left + plot_w)
        y = _scale(float(row["composite_rank"]), min_rank, max_rank, top + plot_h, top)
        body.append(_svg_text(x + 10, y - 8, str(row["team_name"]), size=10, weight=700, fill=PALETTE["navy"]))

    body.append(_svg_text(left, 102, "Arkansas is the RPI leader, but Texas Tech and UCLA look stronger in the composite framework.", size=11, weight=500, fill=PALETTE["slate"]))
    _write_svg(path, width, height, body)
    return FigureRef(path=path, caption="RPI and the composite model only partially agree, which is why Arkansas and Texas Tech split the top-line story.")


def plot_team_signal_map(teams: pd.DataFrame, path: Path) -> FigureRef:
    df = teams.dropna(subset=["ops", "era"]).copy()
    df["ops"] = pd.to_numeric(df["ops"], errors="coerce")
    df["era"] = pd.to_numeric(df["era"], errors="coerce")
    df["composite_score"] = pd.to_numeric(df["composite_score"], errors="coerce")
    df = df[df["ip"].fillna(0) > 0].copy()

    width, height = 1120, 760
    left, right, top, bottom = 110, 90, 130, 110
    plot_w = width - left - right
    plot_h = height - top - bottom
    min_ops, max_ops = float(df["ops"].min()) * 0.97, float(df["ops"].max()) * 1.03
    min_era, max_era = float(df["era"].min()) * 0.90, float(df["era"].max()) * 1.08

    body = _svg_header(
        "Offense vs. Run Prevention",
        "Texas Tech, UCLA, and Oklahoma all live in the rare zone where the bat is loud and the staff still controls games.",
        width=width,
        height=height,
    )
    body.append(_svg_text(40, 124, "Points are color-weighted by composite score. Higher OPS and lower ERA push a team toward the upper-right corner.", size=12, weight=500, fill=PALETTE["slate"]))
    body.append(_svg_rect(left, top, plot_w, plot_h, fill="#FFFDFC", rx=10, opacity=1.0, stroke="#D8D1C6", stroke_width=1.0))

    for tick in _axis_ticks(min_ops, max_ops, count=5):
        x = _scale(tick, min_ops, max_ops, left, left + plot_w)
        body.append(_svg_line(x, top + plot_h, x, top + plot_h + 6, stroke="#B7AEA4", stroke_width=1.0))
        body.append(_svg_text(x, top + plot_h + 24, f"{tick:.2f}", size=10, weight=500, fill=PALETTE["muted"], anchor="middle"))
    for tick in _axis_ticks(min_era, max_era, count=5):
        y = _scale(tick, min_era, max_era, top + plot_h, top)
        body.append(_svg_line(left - 6, y, left, y, stroke="#B7AEA4", stroke_width=1.0))
        body.append(_svg_text(left - 12, y + 4, f"{tick:.2f}", size=10, weight=500, fill=PALETTE["muted"], anchor="end"))

    body.append(_svg_text(left + plot_w / 2, height - 36, "Team OPS", size=11, weight=700, fill=PALETTE["navy"], anchor="middle"))
    body.append(_svg_text(26, top + plot_h / 2, "Team ERA", size=11, weight=700, fill=PALETTE["navy"], anchor="middle"))

    for _, row in df.iterrows():
        x = _scale(float(row["ops"]), min_ops, max_ops, left, left + plot_w)
        y = _scale(float(row["era"]), min_era, max_era, top + plot_h, top)
        score = float(row["composite_score"])
        score_min, score_max = float(df["composite_score"].min()), float(df["composite_score"].max())
        t = 0.5 if score_max == score_min else (score - score_min) / (score_max - score_min)
        color = _blend(PALETTE["teal"], PALETTE["copper"], t)
        radius = 6.0 + 3.0 * t
        body.append(_svg_circle(x, y, radius, fill=color, stroke="#FFFFFF", stroke_width=1.2, opacity=0.92))

    for team in ["Texas Tech", "UCLA", "Oklahoma", "Alabama", "Nebraska", "Tennessee", "Florida", "Arkansas"]:
        subset = df[df["team_name"] == team]
        if not subset.empty:
            row = subset.iloc[0]
            x = _scale(float(row["ops"]), min_ops, max_ops, left, left + plot_w)
            y = _scale(float(row["era"]), min_era, max_era, top + plot_h, top)
            body.append(_svg_text(x + 10, y - 8, team, size=10, weight=700, fill=PALETTE["navy"]))

    body.append(_svg_text(left, 102, "Teams in the upper-right are doing the most in one frame: producing runs and preventing them.", size=11, weight=500, fill=PALETTE["slate"]))
    _write_svg(path, width, height, body)
    return FigureRef(path=path, caption="The best teams pair a real offense with enough run prevention to keep the run differential alive.")


def plot_top_players(players: pd.DataFrame, path: Path) -> FigureRef:
    df = players.dropna(subset=["ops"]).copy()
    df = df[pd.to_numeric(df["ab"], errors="coerce") > 80].sort_values("ops", ascending=False).head(10)
    width, height = 1180, 760
    left, right, top, bottom = 350, 60, 140, 80
    plot_width = width - left - right
    row_h = (height - top - bottom) / max(len(df), 1)
    max_val = float(df["ops"].max()) * 1.12 if len(df) else 1.0

    body = _svg_header(
        "Top 10 Players by OPS",
        "The board is top-heavy: Megan Grant and Jordan Woolery separate from the rest of the class.",
        width=width,
        height=height,
    )
    body.append(_svg_text(40, 124, "Only players with more than 80 AB are included so the leaderboard stays meaningful.", size=12, weight=500, fill=PALETTE["slate"]))
    body.append(_svg_line(left, top - 8, left, height - bottom, stroke="#D6CEC4", stroke_width=1.2))
    body.append(_svg_line(left, height - bottom, width - right, height - bottom, stroke="#D6CEC4", stroke_width=1.2))

    for tick in _axis_ticks(0.0, max_val, count=5):
        x = _scale(tick, 0.0, max_val, left, left + plot_width)
        body.append(_svg_line(x, height - bottom, x, height - bottom + 6, stroke="#B7AEA4", stroke_width=1.0))
        body.append(_svg_text(x, height - bottom + 24, f"{tick:.2f}", size=10, weight=500, fill=PALETTE["muted"], anchor="middle"))

    for idx, (_, row) in enumerate(df.sort_values("ops", ascending=False).iterrows()):
        y = top + idx * row_h + 10
        bar_h = max(18, row_h * 0.52)
        bar_w = _scale(float(row["ops"]), 0.0, max_val, 0.0, plot_width)
        color = PALETTE["copper"] if idx < 2 else PALETTE["navy"]
        label = f"{row['player_name']}  ({row['team_name']})"
        body.append(_svg_text(30, y + bar_h * 0.72, label, size=13, weight=700, fill=PALETTE["navy"]))
        body.append(_svg_rect(left, y, bar_w, bar_h, fill=color, rx=8, opacity=0.95))
        body.append(_svg_text(left + bar_w + 10, y + bar_h * 0.72, f"{float(row['ops']):.3f} | {int(row['hr'])} HR", size=11, weight=700, fill=PALETTE["navy"]))

    body.append(_svg_text(width - 60, 124, "The peak bats are unmistakable, and the next tier is still elite.", size=11, weight=500, fill=PALETTE["slate"], anchor="end"))
    _write_svg(path, width, height, body)
    return FigureRef(path=path, caption="Megan Grant and Jordan Woolery anchor the player leaderboard, with Katie Stewart and Emily LeGette in the next cluster.")


def plot_top_pitching_staffs(teams: pd.DataFrame, path: Path) -> FigureRef:
    df = teams[pd.to_numeric(teams["ip"], errors="coerce") > 0].copy()
    df["era"] = pd.to_numeric(df["era"], errors="coerce")
    df["whip"] = pd.to_numeric(df["whip"], errors="coerce")
    df["k_bb_ratio"] = pd.to_numeric(df["k_bb_ratio"], errors="coerce")
    era_df = df.sort_values("era", ascending=True).head(10).reset_index(drop=True)
    kbb_df = df.sort_values("k_bb_ratio", ascending=False).head(10).reset_index(drop=True)

    width, height = 1400, 800
    panel_top, panel_bottom = 150, 90
    panel_left, gap, panel_width = 70, 50, 600
    panel_h = height - panel_top - panel_bottom

    body = _svg_header(
        "Tennessee Sets the Run-Prevention Standard",
        "Among innings-qualified staffs, Tennessee is the cleanest prevention unit; Texas Tech, Alabama, and Mississippi State stay close behind.",
        width=width,
        height=height,
    )
    body.append(_svg_text(40, 124, "Left: lowest ERA. Right: best K/BB. The two views tell the same story from different angles.", size=12, weight=500, fill=PALETTE["slate"]))
    body.append(_svg_rect(panel_left, panel_top, panel_width, panel_h, fill="#FFFDFC", rx=10, opacity=1.0, stroke="#D8D1C6", stroke_width=1.0))
    body.append(_svg_rect(panel_left + panel_width + gap, panel_top, panel_width, panel_h, fill="#FFFDFC", rx=10, opacity=1.0, stroke="#D8D1C6", stroke_width=1.0))

    def draw_bar_panel(df_panel: pd.DataFrame, *, x0: float, y0: float, w: float, h: float, metric: str, label: str, color: str, ascending: bool, format_value: str) -> None:
        body.append(_svg_text(x0 + 24, y0 + 34, label, size=18, weight=800, fill=PALETTE["navy"], family="Montserrat, Inter, Arial, sans-serif"))
        max_val = float(df_panel[metric].max()) * 1.12 if len(df_panel) else 1.0
        row_h = (h - 80) / max(len(df_panel), 1)
        for tick in _axis_ticks(0.0, max_val, count=5):
            x = _scale(tick, 0.0, max_val, x0 + 210, x0 + w - 24)
            body.append(_svg_line(x, y0 + h - 26, x, y0 + h - 20, stroke="#B7AEA4", stroke_width=1.0))
            body.append(_svg_text(x, y0 + h - 2, f"{tick:.2f}", size=9, weight=500, fill=PALETTE["muted"], anchor="middle"))
        body.append(_svg_line(x0 + 210, y0 + 52, x0 + 210, y0 + h - 26, stroke="#D6CEC4", stroke_width=1.0))
        body.append(_svg_line(x0 + 210, y0 + h - 26, x0 + w - 24, y0 + h - 26, stroke="#D6CEC4", stroke_width=1.0))
        ordered = df_panel.sort_values(metric, ascending=ascending)
        for idx, (_, row) in enumerate(ordered.iterrows()):
            yy = y0 + 66 + idx * row_h
            bar_h = max(17, row_h * 0.54)
            bw = _scale(float(row[metric]), 0.0, max_val, 0.0, w - 234)
            body.append(_svg_text(x0 + 24, yy + bar_h * 0.72, str(row["team_name"]), size=12, weight=700, fill=PALETTE["navy"]))
            body.append(_svg_rect(x0 + 210, yy, bw, bar_h, fill=color, rx=7, opacity=0.95))
            body.append(_svg_text(x0 + 210 + bw + 8, yy + bar_h * 0.72, format_value.format(float(row[metric])), size=10, weight=700, fill=PALETTE["navy"]))

    draw_bar_panel(era_df, x0=panel_left, y0=panel_top, w=panel_width, h=panel_h, metric="era", label="Lowest ERA", color=PALETTE["teal"], ascending=True, format_value="{:.2f}")
    draw_bar_panel(kbb_df, x0=panel_left + panel_width + gap, y0=panel_top, w=panel_width, h=panel_h, metric="k_bb_ratio", label="Best K/BB", color=PALETTE["copper"], ascending=False, format_value="{:.2f}")
    _write_svg(path, width, height, body)
    return FigureRef(path=path, caption="Tennessee owns the cleanest prevention profile, while Texas Tech and Alabama stay close enough to matter.")


def build_report_data(
    *,
    teams: pd.DataFrame,
    players: pd.DataFrame,
    rpi: pd.DataFrame,
    figures: list[FigureRef],
    findings: list[dict[str, Any]],
    storyboard: list[dict[str, Any]],
    deeper_analysis: list[dict[str, Any]],
    eda_run_dir: Path,
    output_dir: Path,
    report_metadata: dict[str, Any],
) -> dict[str, Any]:
    valid_pitch = teams[pd.to_numeric(teams["ip"], errors="coerce") > 0].copy()
    valid_pitch["era"] = pd.to_numeric(valid_pitch["era"], errors="coerce")
    comp_rpi_corr = teams[["composite_rank", "rpi_rank"]].dropna().corr().iloc[0, 1]

    top = teams.sort_values("composite_rank").reset_index(drop=True)
    top5 = top.head(5)

    return {
        "schema_version": "d1softball_manual_report_v1",
        "report_id": "d1softball_manual_april2026",
        "title": "D1 Softball Manual Workbook Report",
        "subtitle": "April 2026 manual workbook import, translated into a publishable markdown brief.",
        "intro_note": "This report follows the notebook's editorial structure, but swaps in cleaner team-level angles for findings 02 and 07.",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "at_a_glance": [
            {"label": "Team rows", "value": int(len(teams))},
            {"label": "Player rows", "value": int(len(players))},
            {"label": "Batting players with AB > 0", "value": int((players["ab"] > 0).sum())},
            {"label": "Pitching players with IP > 0", "value": int((players["ip"] > 0).sum())},
            {"label": "Teams with innings-qualified pitching", "value": int(len(valid_pitch))},
            {"label": "Composite vs. RPI correlation", "value": round(float(comp_rpi_corr), 2)},
        ],
        "executive_summary": "The imported workbook makes one thing clear immediately: the top end is crowded, but not random. Texas Tech owns the composite crown, UCLA and Oklahoma stay right on its heels, and the RPI table tells a different story with Arkansas at No. 1. At the player level, Megan Grant is the loudest bat in the file, while Tennessee's staff gives the cleanest prevention profile among innings-qualified teams.",
        "key_scoreboard": [
            {
                "team": str(row["team_name"]),
                "composite": float(row["composite_score"]),
                "ops": float(row["ops"]),
                "era": None if pd.isna(row["era"]) or float(row.get("ip", 0)) <= 0 else float(row["era"]),
                "has_pitching": bool(float(row.get("ip", 0)) > 0),
                "rpi": None if pd.isna(row["rpi_rank"]) else float(row["rpi_rank"]),
            }
            for _, row in top5.iterrows()
        ],
        "storyboard": {
            "arc_title": "A tight top tier with split ranking signals",
            "audience_tags": ["analyst", "coaching", "fan"],
            "steps": storyboard,
        },
        "findings": findings,
        "deeper_analysis": deeper_analysis,
        "figures": [
            {
                "filename": figure.path.name,
                "title": title,
                "caption": figure.caption,
                "alt": title,
            }
            for figure, title in zip(
                figures,
                [
                    "Top 10 Teams by Composite Score",
                    "RPI and Composite Rank Tell Different Top-10 Stories",
                    "Offense vs. Run Prevention",
                    "Top 10 Players by OPS",
                    "Tennessee Sets the Run-Prevention Standard",
                ],
            )
        ],
        "data_notes": [
            "The workbook is partial by design: batting and pitching rows are not fully overlapped, so player-level analysis is better treated as two complementary slices rather than a single joined table.",
            "Team-level claims are strongest where both batting and pitching coverage exist, especially among the innings-qualified staffs used in the prevention charts.",
            "The report uses the workbook as a snapshot, not a season-complete game-log feed.",
            "Player batting and player pitching do not need to overlap for this workbook to be useful.",
        ],
        "source_artifacts": {
            "eda_run_dir": str(eda_run_dir),
            "report_dir": str(output_dir),
            "report_markdown_path": str(output_dir / "report.md"),
            "report_metadata_path": str(output_dir / "report_metadata.json"),
            "report_notebook_path": str(output_dir / "notebook.html"),
            "public_notebook_path": "/reports/d1softball_manual_april2026/notebook.html",
            "public_bundle_dir": "/reports/d1softball_manual_april2026",
            "public_report_markdown_path": "/reports/d1softball_manual_april2026/report.md",
            "public_report_metadata_path": "/reports/d1softball_manual_april2026/report_metadata.json",
            "public_figures_dir": "/reports/d1softball_manual_april2026/figures",
        },
        "report_metadata": report_metadata,
        "coverage": {
            "team_rows": int(len(teams)),
            "player_rows": int(len(players)),
            "teams_with_pitching": int(len(valid_pitch)),
            "composite_vs_rpi_correlation": round(float(comp_rpi_corr), 4),
        },
    }


def _fmt(num: Any, digits: int = 3) -> str:
    try:
        if num is None or (isinstance(num, float) and math.isnan(num)):
            return "n/a"
        return f"{float(num):.{digits}f}"
    except Exception:
        return str(num)


def render_report(
    teams: pd.DataFrame,
    players: pd.DataFrame,
    rpi: pd.DataFrame,
    charts: list[FigureRef],
    eda_run_dir: Path,
    output_dir: Path,
) -> str:
    valid_pitch = teams[pd.to_numeric(teams["ip"], errors="coerce") > 0].copy()
    valid_pitch["era"] = pd.to_numeric(valid_pitch["era"], errors="coerce")
    valid_pitch["whip"] = pd.to_numeric(valid_pitch["whip"], errors="coerce")
    valid_pitch["k_bb_ratio"] = pd.to_numeric(valid_pitch["k_bb_ratio"], errors="coerce")
    valid_pitch["offense_z"] = pd.to_numeric(valid_pitch["offense_z"], errors="coerce")
    valid_pitch["pitching_z"] = pd.to_numeric(valid_pitch["pitching_z"], errors="coerce")
    comp_rpi_corr = teams[["composite_rank", "rpi_rank"]].dropna().corr().iloc[0, 1]

    top = teams.sort_values("composite_rank").reset_index(drop=True)
    top5 = top.head(5)
    top_pitch = valid_pitch.sort_values("era").head(5)
    top_bats = players.dropna(subset=["ops"]).sort_values("ops", ascending=False).head(5)

    findings = build_findings(teams, players, rpi)
    storyboard = build_storyboard(findings)
    deeper = build_deeper_analysis(eda_run_dir)

    lines: list[str] = []
    lines.append("# D1 Softball Manual Workbook Report")
    lines.append("")
    lines.append("April 2026 manual workbook import, translated into a publishable markdown brief.")
    lines.append("")
    lines.append("> This report follows the notebook's editorial structure, but swaps in cleaner team-level angles for findings 02 and 07.")
    lines.append("")
    lines.append("## At a Glance")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Team rows | {len(teams)} |")
    lines.append(f"| Player rows | {len(players)} |")
    lines.append(f"| Batting players with AB > 0 | {(players['ab'] > 0).sum()} |")
    lines.append(f"| Pitching players with IP > 0 | {(players['ip'] > 0).sum()} |")
    lines.append(f"| Teams with innings-qualified pitching | {len(valid_pitch)} |")
    lines.append(f"| Composite vs. RPI correlation | {_fmt(comp_rpi_corr, 2)} |")
    lines.append("")
    lines.append("## Dataset & Method")
    lines.append("")
    lines.append("The workbook arrives as five tabs: team batting, team pitching, player batting, player pitching, and RPI. The player batting and player pitching tabs do **not** need to overlap; they are treated as separate source slices and summarized on their own terms.")
    lines.append("")
    lines.append("For the report, I:")
    lines.append("")
    lines.append("- merged the team tabs into a single team snapshot with batting, pitching, and composite fields")
    lines.append("- kept batting and pitching player tables separate, because the workbook only partially overlaps them")
    lines.append("- used the RPI tab as schedule-strength context")
    lines.append("- filtered pitching leaderboards to innings-qualified staffs so the prevention story stays credible")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("The imported workbook makes one thing clear immediately: the top end is crowded, but not random. Texas Tech owns the composite crown, UCLA and Oklahoma stay right on its heels, and the RPI table tells a different story with Arkansas at No. 1. At the player level, Megan Grant is the loudest bat in the file, while Tennessee's staff gives the cleanest prevention profile among innings-qualified teams.")
    lines.append("")
    lines.append("### Key Scoreboard")
    lines.append("")
    lines.append("| Team | Composite | OPS | ERA | RPI |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for _, row in top5.iterrows():
        has_pitching = float(row.get("ip", 0)) > 0
        lines.append(
            f"| {row['team_name']} | {_fmt(row['composite_score'])} | {_fmt(row['ops'])} | {_fmt(row['era'] if has_pitching else None, 2)} | {_fmt(row['rpi_rank'])} |"
        )
    lines.append("")
    lines.append("### Story Arc")
    lines.append("")
    for step in storyboard:
        lines.append(f"- **{step['step_type'].capitalize()}** - {step['title']}: {step['transition']}")
    lines.append("")
    lines.append("## Figures")
    lines.append("")
    for idx, chart in enumerate(charts, start=1):
        rel = chart.path.relative_to(output_dir)
        lines.append(f"### Figure {idx}")
        lines.append("")
        lines.append(f"![Figure {idx}]({rel.as_posix()})")
        lines.append("")
        lines.append(f"*{chart.caption}*")
        lines.append("")

    lines.append("## Findings")
    lines.append("")
    for finding in findings:
        lines.append(f"### {finding['id']}. {finding['title']}")
        lines.append("")
        lines.append(f"**Takeaway:** {finding['insight']}")
        lines.append("")
        lines.append("**Evidence:**")
        for key, value in finding["evidence"].items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
        if finding.get("visuals"):
            lines.append("**Visuals:**")
            for visual in finding["visuals"]:
                lines.append(f"- {visual}")
            lines.append("")

    lines.append("## Deeper Analysis Queue")
    lines.append("")
    for item in deeper:
        lines.append(f"### {item['question']}")
        lines.append("")
        lines.append(f"- **Why it matters:** {item['importance']}")
        lines.append(f"- **Needed data:** {', '.join(item['needed_data'])}")
        lines.append(f"- **Method:** {item['method']}")
        lines.append(f"- **Priority:** {item['priority']}")
        lines.append("")

    lines.append("## Data Notes")
    lines.append("")
    lines.append("- The workbook is partial by design: batting and pitching rows are not fully overlapped, so player-level analysis is better treated as two complementary slices rather than a single joined table.")
    lines.append("- Team-level claims are strongest where both batting and pitching coverage exist, especially among the innings-qualified staffs used in the prevention charts.")
    lines.append("- The report uses the workbook as a snapshot, not a season-complete game-log feed.")
    lines.append("")
    lines.append("## Source Artifacts")
    lines.append("")
    lines.append(f"- EDA run: `{eda_run_dir}`")
    lines.append(f"- Report files: `{REPORT_DIR}`")
    lines.append("")
    return "\n".join(lines)


def build_findings(teams: pd.DataFrame, players: pd.DataFrame, rpi: pd.DataFrame) -> list[dict[str, Any]]:
    t = teams.copy()
    for col in ["composite_score", "composite_rank", "offense_z", "pitching_z", "discipline_z", "defense_z", "ops", "era", "whip", "k_bb_ratio", "bb_k_ratio", "rpi_rank", "sos", "ip"]:
        if col in t.columns:
            t[col] = pd.to_numeric(t[col], errors="coerce")
    p = players.copy()
    for col in ["ops", "hr", "ab", "rbi", "ip", "k", "era"]:
        if col in p.columns:
            p[col] = pd.to_numeric(p[col], errors="coerce")

    findings: list[dict[str, Any]] = []

    top = t.sort_values("composite_score", ascending=False).iloc[0]
    findings.append(
        {
            "id": "01",
            "title": f"{top['team_name']} leads the all-around team profile",
            "insight": f"{top['team_name']} ranks first by composite score, signaling balanced strength across offense, pitching, discipline, and defense.",
            "evidence": {
                "team": top["team_name"],
                "composite_score": round(float(top["composite_score"]), 4),
                "composite_rank": int(top["composite_rank"]),
            },
            "visuals": ["Top-10 composite bar chart", "Team-signal map"],
        }
    )

    arkansas = t[t["team_name"] == "Arkansas"].iloc[0]
    tech = t[t["team_name"] == "Texas Tech"].iloc[0]
    corr = t[["rpi_rank", "composite_rank"]].dropna().corr().iloc[0, 1]
    findings.append(
        {
            "id": "02",
            "title": "Arkansas owns the RPI crown, but Texas Tech owns the composite crown",
            "insight": f"RPI and the composite model are only moderately aligned here, with correlation at {corr:.2f}; Arkansas is No. 1 in RPI, but Texas Tech is No. 1 in composite.",
            "evidence": {
                "arkansas_rpi_rank": int(arkansas["rpi_rank"]),
                "arkansas_composite_rank": int(arkansas["composite_rank"]),
                "texas_tech_rpi_rank": int(tech["rpi_rank"]),
                "texas_tech_composite_rank": int(tech["composite_rank"]),
                "rank_correlation": round(float(corr), 4),
            },
            "visuals": ["RPI vs composite scatter", "Rank-difference highlight table"],
        }
    )

    findings.append(
        {
            "id": "03",
            "title": "Texas Tech profiles as a coaching-efficiency standout",
            "insight": f"Texas Tech combines elite discipline with strong run-prevention markers, a profile that usually signals repeatable coaching value rather than one-off luck.",
            "evidence": {
                "discipline_z": round(float(tech["discipline_z"]), 4),
                "pitching_z": round(float(tech["pitching_z"]), 4),
                "k_bb_ratio": round(float(tech["k_bb_ratio"]), 4),
                "whip": round(float(tech["whip"]), 4),
            },
            "visuals": ["Offense vs. pitching scatter", "Texas Tech callout card"],
        }
    )

    top5 = t.sort_values("composite_score", ascending=False).head(5).reset_index(drop=True)
    gap = float(top5.loc[0, "composite_score"] - top5.loc[4, "composite_score"])
    findings.append(
        {
            "id": "04",
            "title": "Top-5 race is primed for fan-facing weekly drama",
            "insight": f"The top five teams sit within {gap:.3f} composite points, which is tight enough for weekly movement to matter.",
            "evidence": {
                "top5_teams": ", ".join(top5["team_name"].tolist()),
                "top1_score": round(float(top5.loc[0, "composite_score"]), 4),
                "top5_score": round(float(top5.loc[4, "composite_score"]), 4),
                "gap": round(gap, 4),
            },
            "visuals": ["Top-10 composite bars", "Top-5 gap callout"],
        }
    )

    nebraska = t[t["team_name"] == "Nebraska"].iloc[0]
    findings.append(
        {
            "id": "05",
            "title": "Nebraska shows one of the cleanest balanced profiles",
            "insight": f"Among innings-qualified teams, Nebraska keeps offense and pitching relatively close together, which usually travels better than a one-sided profile.",
            "evidence": {
                "offense_z": round(float(nebraska["offense_z"]), 4),
                "pitching_z": round(float(nebraska["pitching_z"]), 4),
                "balance_gap": round(abs(float(nebraska["offense_z"]) - float(nebraska["pitching_z"])), 4),
            },
            "visuals": ["Offense vs. pitching scatter", "Balance-gap mini table"],
        }
    )

    megan = p[p["player_name"] == "Megan Grant"].iloc[0]
    findings.append(
        {
            "id": "06",
            "title": "Megan Grant leads the long-ball race",
            "insight": f"Megan Grant is the loudest individual bat in the workbook, pairing a huge OPS with a home run total that sits far above the next tier.",
            "evidence": {
                "team": megan["team_name"],
                "ops": round(float(megan["ops"]), 4),
                "hr": int(megan["hr"]),
                "ab": int(megan["ab"]),
            },
            "visuals": ["Top player OPS bars", "Home-run leaderboard"],
        }
    )

    valid_pitch = t[pd.to_numeric(t["ip"], errors="coerce") > 0].copy()
    valid_pitch["era"] = pd.to_numeric(valid_pitch["era"], errors="coerce")
    valid_pitch["whip"] = pd.to_numeric(valid_pitch["whip"], errors="coerce")
    valid_pitch["k_bb_ratio"] = pd.to_numeric(valid_pitch["k_bb_ratio"], errors="coerce")
    tennessee = valid_pitch[valid_pitch["team_name"] == "Tennessee"].iloc[0]
    findings.append(
        {
            "id": "07",
            "title": "Tennessee owns the strongest run-prevention staff",
            "insight": "Among innings-qualified staffs, Tennessee sits at the top of both ERA and WHIP, which gives it the cleanest prevention profile in the workbook.",
            "evidence": {
                "era": round(float(tennessee["era"]), 4),
                "whip": round(float(tennessee["whip"]), 4),
                "k_bb_ratio": round(float(tennessee["k_bb_ratio"]), 4),
                "ip": round(float(tennessee["ip"]), 1),
            },
            "visuals": ["Pitching-staff leaderboard", "Prevention profile card"],
        }
    )

    top_offense = t.sort_values("ops", ascending=False).head(4)
    findings.append(
        {
            "id": "08",
            "title": "The offensive leaderboard is top-heavy, but not singular",
            "insight": "Oklahoma, UCLA, Texas Tech, and Florida form the clearest offensive tier; the next few schools are good, but the gap to the top four is real.",
            "evidence": {
                "top_4": ", ".join(top_offense["team_name"].tolist()),
                "top_4_ops": ", ".join(f"{v:.3f}" for v in top_offense["ops"].tolist()),
            },
            "visuals": ["Top-10 team OPS chart", "Offense-vs-pitching map"],
        }
    )

    return findings


def build_storyboard(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {f["id"]: f for f in findings}
    order = ["04", "01", "02", "06", "03", "07", "05", "08"]
    step_types = ["hook", "evidence", "contrast", "action", "implication", "support", "support", "close"]
    transitions = [
        "Start with the story fans feel first: the board is tight enough that weekly movement matters.",
        "Show why Texas Tech sits at the top of the all-around leaderboard.",
        "Introduce the main contradiction: RPI crowns one team, the composite crowns another.",
        "Move from team shape to star power with the loudest bat in the workbook.",
        "Translate the bat into a broader coaching and execution signal.",
        "Bring in the run-prevention staff that most clearly controls the game.",
        "Add the balance note that explains why some teams hold their shape.",
        "Close with the offensive tier that sets the ceiling for the whole board.",
    ]
    steps = []
    for idx, fid in enumerate(order):
        finding = by_id[fid]
        steps.append(
            {
                "order": idx + 1,
                "finding_id": fid,
                "step_type": step_types[idx],
                "title": finding["title"],
                "narrative": finding["insight"],
                "transition": transitions[idx],
            }
        )
    return steps


def build_deeper_analysis(eda_run_dir: Path) -> list[dict[str, Any]]:
    path = eda_run_dir / "deeper_analysis.json"
    if path.exists():
        data = json.loads(path.read_text())
        return data
    return [
        {
            "question": "Which teams overperform expected results once schedule strength is introduced?",
            "importance": "Separates true strength from context effects and improves ranking stability.",
            "needed_data": ["team-level game logs", "opponent quality", "home/away"],
            "method": "Schedule-adjusted residual modeling",
            "priority": "high",
        },
        {
            "question": "Which player profiles are most predictive of postseason run production?",
            "importance": "Identifies transferable offensive traits under stronger pitching.",
            "needed_data": ["player splits", "high-leverage situations", "postseason samples"],
            "method": "Feature importance with holdout seasons",
            "priority": "high",
        },
        {
            "question": "Where does pitching usage create hidden fatigue or efficiency edges?",
            "importance": "Supports coaching decisions on rotation, bullpen leverage, and recovery windows.",
            "needed_data": ["pitching appearances", "days rest", "opponent strength"],
            "method": "Usage clustering + rolling trend decomposition",
            "priority": "medium",
        },
        {
            "question": "Which fan-facing storylines have the highest week-to-week volatility?",
            "importance": "Improves content planning around credible, high-interest swings.",
            "needed_data": ["weekly rankings", "individual performance deltas", "team outcomes"],
            "method": "Volatility index + change-point detection",
            "priority": "medium",
        },
    ]


if __name__ == "__main__":
    main()
