from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


def _safe(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num != num:  # NaN
        return "n/a"
    if abs(num - round(num)) < 1e-9:
        return str(int(round(num)))
    return f"{num:.{digits}f}"


def _render_stat(label: str, value: Any) -> str:
    return (
        '<article class="kpi">'
        f'<div class="meta">{_safe(label)}</div>'
        f'<div class="kpi-value">{_safe(_fmt(value, 2))}</div>'
        "</article>"
    )


def _render_badges(values: list[str]) -> str:
    return "".join(f'<span class="badge">{_safe(value)}</span>' for value in values)


def _render_top_five_bars(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="mini-chart-empty">No top-five rows available.</div>'

    max_value = max(float(row["composite"]) for row in rows) or 1.0
    body = ['<div class="mini-chart" aria-label="Top five composite score bars">']
    for row in rows:
        width_pct = max(6, round((float(row["composite"]) / max_value) * 100))
        body.append(
            '<div class="mini-chart-row">'
            f'<div class="mini-chart-label">{_safe(row["team"])}</div>'
            '<div class="mini-chart-track"><span style="width: '
            f'{width_pct}%"></span></div>'
            f'<div class="mini-chart-value">{_safe(_fmt(row["composite"], 3))}</div>'
            "</div>"
        )
    body.append("</div>")
    return "".join(body)


def _render_split_signal(finding_map: dict[str, dict[str, Any]]) -> str:
    f = finding_map["02"]
    evidence = f["evidence"]
    rows = [
        ("Arkansas", evidence["arkansas_rpi_rank"], evidence["arkansas_composite_rank"]),
        ("Texas Tech", evidence["texas_tech_rpi_rank"], evidence["texas_tech_composite_rank"]),
    ]
    body = ['<div class="split-signal" aria-label="RPI and composite split signal">']
    body.append('<div class="split-signal-head"><span>School</span><span>RPI</span><span>Composite</span></div>')
    for school, rpi_rank, composite_rank in rows:
        body.append(
            '<div class="split-signal-row">'
            f'<span class="split-signal-team">{_safe(school)}</span>'
            f'<span class="rank-pill">#{_safe(rpi_rank)}</span>'
            f'<span class="rank-pill">#{_safe(composite_rank)}</span>'
            "</div>"
        )
    body.append(
        f'<div class="split-signal-foot">Correlation {_safe(_fmt(evidence["rank_correlation"], 2))} '
        "means the two systems agree only part of the time.</div>"
    )
    body.append("</div>")
    return "".join(body)


def _render_watch_list(finding_map: dict[str, dict[str, Any]]) -> str:
    f06 = finding_map["06"]["evidence"]
    f07 = finding_map["07"]["evidence"]
    f05 = finding_map["05"]["evidence"]
    items = [
        ("Megan Grant", f'{_fmt(f06["ops"], 3)} OPS, {int(f06["hr"])} HR'),
        ("Tennessee", f'{_fmt(f07["era"], 2)} ERA, {_fmt(f07["whip"], 3)} WHIP'),
        ("Nebraska", f'Balance gap {_fmt(f05["balance_gap"], 3)}'),
    ]
    body = ['<div class="watch-list" aria-label="What to watch next">']
    for label, value in items:
        body.append(
            '<div class="watch-row">'
            f'<span class="watch-label">{_safe(label)}</span>'
            f'<span class="watch-value">{_safe(value)}</span>'
            "</div>"
        )
    body.append("</div>")
    return "".join(body)


def _render_figure_cards(figures: list[dict[str, Any]]) -> str:
    body = ['<div class="figure-grid">']
    for idx, figure in enumerate(figures, start=1):
        body.append(
            '<article class="figure-card">'
            f'<div class="section-label">Figure {idx}</div>'
            f'<h3>{_safe(figure["title"])}</h3>'
            f'<img src="figures/{_safe(figure["filename"])}" alt="{_safe(figure["alt"])}" loading="lazy" />'
            f'<p class="figure-caption">{_safe(figure["caption"])}</p>'
            "</article>"
        )
    body.append("</div>")
    return "".join(body)


def _render_storyboard(report: dict[str, Any]) -> str:
    body = ['<div class="storyboard-grid">']
    for step in report["storyboard"]["steps"]:
        body.append(
            '<article class="story-card">'
            '<div class="story-card-topline">'
            f'<span class="story-number">{_safe(step["order"])}</span>'
            f'<span class="story-type">{_safe(step["step_type"])}</span>'
            f'<span class="story-finding">Finding {_safe(step["finding_id"])}</span>'
            "</div>"
            f'<h3>{_safe(step["title"])}</h3>'
            f'<p>{_safe(step["narrative"])}</p>'
            f'<div class="story-transition">{_safe(step["transition"])}</div>'
            "</article>"
        )
    body.append("</div>")
    return "".join(body)


def _render_findings(findings: list[dict[str, Any]]) -> str:
    body = ['<div class="finding-grid">']
    for finding in findings:
        category = finding.get("category", "Workbook")
        confidence = finding.get("confidence")
        provenance = finding.get("provenance") or {}
        confidence_label = (
            "High"
            if isinstance(confidence, (int, float)) and confidence >= 0.85
            else "Medium"
            if isinstance(confidence, (int, float)) and confidence >= 0.7
            else "Workbook"
        )
        provenance_text = provenance.get("generation") if isinstance(provenance, dict) else None
        body.append(
            '<article class="finding-card">'
            '<div class="finding-head">'
            '<div class="pill-row">'
            f'<span class="pill">{_safe(finding["id"])}</span>'
            f'<span class="pill">{_safe(category)}</span>'
            f'<span class="pill">{_safe(confidence_label)} confidence</span>'
            "</div>"
            f'<div class="finding-provenance">{_safe(provenance_text or "Workbook-derived")}</div>'
            "</div>"
            f'<h3>{_safe(finding["title"])}</h3>'
            f'<p class="finding-insight">{_safe(finding["insight"])}</p>'
            '<div class="finding-section">'
            '<div class="section-label">Evidence</div>'
            '<dl class="evidence-grid">'
        )
        for key, value in finding["evidence"].items():
            body.append(f"<div><dt>{_safe(key)}</dt><dd>{_safe(_fmt(value, 4))}</dd></div>")
        body.append("</dl></div>")
        visuals = finding.get("visuals") or []
        if visuals:
            body.append('<div class="finding-section"><div class="section-label">Visual suggestions</div><ul class="visual-list">')
            for visual in visuals:
                body.append(f"<li>{_safe(visual)}</li>")
            body.append("</ul></div>")
        body.append("</article>")
    body.append("</div>")
    return "".join(body)


def _render_deeper_analysis(items: list[dict[str, Any]]) -> str:
    body = ['<div class="analysis-grid">']
    for item in items:
        body.append(
            '<article class="analysis-card">'
            f'<div class="analysis-priority">{_safe(item["priority"])}</div>'
            f'<h3>{_safe(item["question"])}</h3>'
            f'<p>{_safe(item["importance"])}</p>'
            '<div class="analysis-subsection">'
            '<div class="section-label">Needed data</div>'
            f'<p class="analysis-copy">{_safe(", ".join(item["needed_data"]))}</p>'
            "</div>"
            '<div class="analysis-subsection">'
            '<div class="section-label">Method</div>'
            f'<p class="analysis-copy">{_safe(item["method"])}</p>'
            "</div>"
            "</article>"
        )
    body.append("</div>")
    return "".join(body)


def _render_source_notes(report: dict[str, Any]) -> str:
    source = report["source_artifacts"]
    coverage = report["coverage"]
    notes = report["data_notes"]
    body = ['<div class="source-grid">']
    body.append('<article class="info-card"><div class="section-label">Data notes</div><ul class="bullet-list">')
    for note in notes:
        body.append(f"<li>{_safe(note)}</li>")
    body.append("</ul></article>")

    body.append(
        '<article class="info-card">'
        '<div class="section-label">Source artifacts</div>'
        '<dl class="artifact-list">'
        f'<div><dt>Public bundle</dt><dd>{_safe(source["public_bundle_dir"])}</dd></div>'
        f'<div><dt>Public notebook</dt><dd>{_safe(source["public_notebook_path"])}</dd></div>'
        f'<div><dt>Public markdown</dt><dd>{_safe(source["public_report_markdown_path"])}</dd></div>'
        f'<div><dt>Public metadata</dt><dd>{_safe(source["public_report_metadata_path"])}</dd></div>'
        f'<div><dt>Public figures</dt><dd>{_safe(source["public_figures_dir"])}</dd></div>'
        f'<div><dt>Report directory</dt><dd>{_safe(source["report_dir"])}</dd></div>'
        "</dl>"
        f'<div class="artifact-foot">Figures: {_safe(report["report_metadata"]["figure_count"])} | '
        f'Dataset rows: {_safe(coverage["team_rows"])} teams / {_safe(coverage["player_rows"])} players</div>'
        "</article>"
    )
    body.append("</div>")
    return "".join(body)


def render_notebook_html(report: dict[str, Any], output_dir: Path) -> str:
    top5 = report["key_scoreboard"]
    findings = report["findings"]
    finding_map = {finding["id"]: finding for finding in findings}
    figures = report["figures"]
    story = report["storyboard"]
    generated_at = report["generated_at_utc"]
    source = report["source_artifacts"]
    score_gap = float(top5[0]["composite"]) - float(top5[-1]["composite"]) if top5 else 0.0
    top_team = top5[0]["team"] if top5 else "n/a"
    rpi_tech = finding_map["02"]["evidence"]
    texas_tech = finding_map["01"]["evidence"]
    tennessee = finding_map["07"]["evidence"]
    megan = finding_map["06"]["evidence"]

    styles = """
    :root {
      --bg: #f4f0e8;
      --paper: #fffdf9;
      --paper-2: #f9f4eb;
      --ink: #15212c;
      --muted: #5c6670;
      --navy: #1b3a52;
      --navy-2: #224a66;
      --teal: #7a9b9e;
      --copper: #c88f5a;
      --sand: #b8956a;
      --line: #d8d0c3;
      --soft: #ede4d7;
      --shadow: 0 18px 40px rgba(27, 58, 82, 0.12);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 10%, rgba(200, 143, 90, 0.12), transparent 26%),
        radial-gradient(circle at 88% 4%, rgba(122, 155, 158, 0.12), transparent 20%),
        linear-gradient(180deg, #f7f3ec 0%, #f4f0e8 100%);
      font-family: Inter, "Segoe UI", system-ui, sans-serif;
    }
    a { color: inherit; text-decoration: none; }
    img { max-width: 100%; display: block; }
    .notebook-shell {
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 22px 0 56px;
    }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.85fr);
      gap: 16px;
      padding: 28px;
      border-radius: 28px;
      color: #fff;
      background:
        radial-gradient(circle at top right, rgba(239, 179, 33, 0.16), transparent 24%),
        radial-gradient(circle at bottom left, rgba(122, 155, 158, 0.18), transparent 30%),
        linear-gradient(135deg, #1b3a52 0%, #224a66 58%, #162838 100%);
      box-shadow: var(--shadow);
    }
    .hero-copy h1 {
      margin: 8px 0 10px;
      font-family: Oswald, "Arial Narrow", sans-serif;
      font-size: clamp(42px, 6vw, 72px);
      line-height: 0.94;
      letter-spacing: -0.03em;
    }
    .eyebrow, .section-label, .meta, .pill, .badge, .story-type, .story-finding, .analysis-priority {
      font-family: Montserrat, Inter, system-ui, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 11px;
    }
    .eyebrow { color: #f5d5a4; font-weight: 700; }
    .hero-subtitle {
      max-width: 64ch;
      margin: 0;
      font-size: 18px;
      line-height: 1.58;
      color: rgba(255, 255, 255, 0.9);
    }
    .hero-note {
      max-width: 68ch;
      margin: 12px 0 0;
      color: rgba(255, 255, 255, 0.84);
    }
    .badge-row, .chip-row, .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.18);
      color: #fff;
    }
    .hero-panel, .card, .info-card, .story-card, .finding-card, .analysis-card, .figure-card {
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
    }
    .hero-panel {
      padding: 18px;
      color: var(--ink);
    }
    .hero-panel-top {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }
    .hero-panel-note {
      font-family: JetBrains Mono, Menlo, Consolas, monospace;
      font-size: 11px;
      color: var(--muted);
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .kpi {
      padding: 14px;
      border-radius: 16px;
      background: linear-gradient(180deg, #fffdf9 0%, #faf5ee 100%);
      border: 1px solid #e1d8ca;
    }
    .kpi-value {
      margin-top: 6px;
      font-size: 28px;
      line-height: 1;
      font-weight: 800;
      color: var(--ink);
    }
    .hero-callout {
      margin-top: 12px;
      padding: 14px 16px;
      border-radius: 18px;
      background: linear-gradient(180deg, #fdfbf7 0%, #f8f1e6 100%);
      border: 1px solid #eadfce;
    }
    .hero-callout strong, .section-title {
      display: block;
      font-family: Oswald, "Arial Narrow", sans-serif;
      letter-spacing: 0.01em;
      font-size: 20px;
      font-weight: 700;
      color: var(--navy);
      margin-bottom: 8px;
    }
    .hero-callout ul, .bullet-list, .visual-list {
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 8px;
    }
    .hero-callout li, .bullet-list li, .visual-list li {
      line-height: 1.5;
      color: var(--ink);
    }
    .section-rail {
      position: sticky;
      top: 12px;
      z-index: 10;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      margin: 14px 0 18px;
      padding: 10px 12px;
      border-radius: 999px;
      background: rgba(255, 253, 249, 0.88);
      border: 1px solid rgba(216, 208, 195, 0.78);
      backdrop-filter: blur(14px);
      box-shadow: 0 12px 24px rgba(27, 58, 82, 0.07);
    }
    .section-rail a {
      padding: 6px 10px;
      border-radius: 999px;
      color: var(--navy);
      font-weight: 700;
    }
    .section-rail a:hover { background: rgba(200, 143, 90, 0.12); }
    .section-block {
      margin-top: 22px;
      scroll-margin-top: 92px;
    }
    .section-title-wrap {
      margin-bottom: 12px;
    }
    .section-title-wrap h2 {
      margin: 2px 0 0;
      font-family: Oswald, "Arial Narrow", sans-serif;
      font-size: clamp(28px, 3vw, 38px);
      line-height: 1.02;
      letter-spacing: -0.02em;
      color: var(--ink);
    }
    .section-subtitle {
      margin: 8px 0 0;
      max-width: 76ch;
      color: var(--muted);
      line-height: 1.58;
    }
    .story-strip {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .card, .info-card, .story-card, .finding-card, .analysis-card, .figure-card {
      padding: 18px;
    }
    .card h3, .finding-card h3, .analysis-card h3, .figure-card h3 {
      margin: 0 0 8px;
      font-family: Oswald, "Arial Narrow", sans-serif;
      font-size: 22px;
      line-height: 1.02;
      letter-spacing: -0.01em;
      color: var(--navy);
    }
    .card p, .finding-card p, .analysis-card p, .story-card p, .info-card p {
      margin: 0;
      line-height: 1.58;
      color: var(--ink);
    }
    .mini-chart {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }
    .mini-chart-row {
      display: grid;
      grid-template-columns: 1fr minmax(0, 1.5fr) auto;
      gap: 10px;
      align-items: center;
    }
    .mini-chart-label, .mini-chart-value, .watch-label, .watch-value {
      font-size: 12px;
      font-weight: 700;
      color: var(--navy);
    }
    .mini-chart-track {
      height: 10px;
      border-radius: 999px;
      background: rgba(27, 58, 82, 0.08);
      overflow: hidden;
    }
    .mini-chart-track span {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--copper), var(--teal));
    }
    .split-signal, .watch-list {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }
    .split-signal-head, .split-signal-row {
      display: grid;
      grid-template-columns: 1.2fr auto auto;
      gap: 8px;
      align-items: center;
    }
    .split-signal-head {
      font-family: Montserrat, Inter, system-ui, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 10px;
      color: var(--muted);
    }
    .split-signal-row {
      padding: 10px 0;
      border-top: 1px solid var(--soft);
    }
    .split-signal-team {
      font-weight: 800;
      color: var(--ink);
    }
    .rank-pill {
      display: inline-flex;
      justify-content: center;
      align-items: center;
      min-width: 60px;
      padding: 5px 10px;
      border-radius: 999px;
      background: rgba(27, 58, 82, 0.06);
      color: var(--navy);
      font-weight: 800;
    }
    .split-signal-foot {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }
    .watch-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 0;
      border-top: 1px solid var(--soft);
    }
    .storyboard-grid, .finding-grid, .analysis-grid, .figure-grid, .source-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .story-card {
      border-left: 4px solid var(--copper);
    }
    .story-card-topline, .finding-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      margin-bottom: 10px;
    }
    .story-number {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: var(--navy);
      color: #fff;
      font-weight: 800;
      font-size: 12px;
    }
    .story-transition {
      margin-top: 10px;
      color: var(--muted);
      font-style: italic;
    }
    .finding-card {
      border-top: 4px solid var(--navy);
    }
    .pill {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      background: #f4efe8;
      border: 1px solid var(--line);
      color: var(--navy);
      font-weight: 700;
    }
    .finding-provenance {
      color: var(--muted);
      font-family: Montserrat, Inter, system-ui, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.09em;
      font-size: 10px;
      line-height: 1.4;
      text-align: right;
    }
    .finding-insight {
      font-size: 15px;
      margin-bottom: 2px;
    }
    .finding-section { margin-top: 12px; }
    .evidence-grid {
      margin: 0;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .evidence-grid div {
      padding: 10px 12px;
      border-radius: 14px;
      background: linear-gradient(180deg, #fbf8f3 0%, #f7f1e8 100%);
      border: 1px solid #e5dbca;
    }
    .evidence-grid dt {
      margin: 0 0 4px;
      font-family: Montserrat, Inter, system-ui, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-size: 10px;
      color: var(--muted);
    }
    .evidence-grid dd {
      margin: 0;
      font-weight: 800;
      color: var(--ink);
      word-break: break-word;
    }
    .analysis-priority {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(122, 155, 158, 0.12);
      color: var(--navy);
      font-weight: 800;
      margin-bottom: 10px;
    }
    .analysis-copy {
      color: var(--muted);
    }
    .figure-grid {
      align-items: start;
    }
    .figure-card img {
      margin-top: 10px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #fffdf9 0%, #f6f1e8 100%);
    }
    .figure-caption {
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
    }
    .info-card {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .artifact-list {
      margin: 0;
      display: grid;
      gap: 10px;
    }
    .artifact-list div {
      padding: 10px 12px;
      border-radius: 14px;
      background: #fbf8f3;
      border: 1px solid var(--line);
    }
    .artifact-list dt {
      margin: 0 0 4px;
      font-family: Montserrat, Inter, system-ui, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-size: 10px;
      color: var(--muted);
    }
    .artifact-list dd {
      margin: 0;
      font-family: JetBrains Mono, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.5;
      word-break: break-word;
      color: var(--ink);
    }
    .artifact-foot {
      color: var(--muted);
      font-size: 13px;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 12px;
    }
    .summary-card {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .summary-card p { color: var(--ink); }
    .summary-copy {
      font-size: 16px;
      line-height: 1.65;
    }
    .summary-note {
      padding: 14px 16px;
      border-radius: 18px;
      background: linear-gradient(180deg, #fbf8f3 0%, #f7f1e8 100%);
      border: 1px solid #e6dac8;
    }
    .summary-note strong {
      display: block;
      margin-bottom: 6px;
      color: var(--navy);
      font-family: Oswald, "Arial Narrow", sans-serif;
      font-size: 18px;
    }
    .topline-panel {
      margin-top: 12px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .topline-panel .card {
      background: linear-gradient(180deg, #fffdf9 0%, #f8f2e8 100%);
    }
    .topline-panel .section-label {
      color: var(--muted);
      margin-bottom: 10px;
    }
    .table-card {
      overflow: hidden;
    }
    .table-wrap {
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-family: Montserrat, Inter, system-ui, sans-serif;
    }
    thead th {
      text-align: left;
      font-size: 11px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
      background: #f3ede4;
      position: sticky;
      top: 0;
      z-index: 1;
    }
    th, td {
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      white-space: nowrap;
    }
    tbody tr:nth-child(odd) { background: #fcfbf8; }
    .inline-link {
      text-decoration: underline;
      text-underline-offset: 2px;
      font-weight: 700;
      color: var(--navy);
    }
    .section-foot {
      margin-top: 10px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }
    .footer {
      margin-top: 24px;
      color: var(--muted);
      font-size: 12px;
      text-align: center;
    }
    @media (max-width: 980px) {
      .hero, .summary-grid, .topline-panel, .story-strip, .storyboard-grid, .finding-grid, .analysis-grid, .figure-grid, .source-grid {
        grid-template-columns: 1fr;
      }
      .hero { padding: 22px; }
      .section-rail {
        position: static;
        border-radius: 22px;
      }
      .finding-head, .story-card-topline, .hero-panel-top {
        flex-direction: column;
        align-items: flex-start;
      }
      .evidence-grid { grid-template-columns: 1fr; }
      .split-signal-head, .split-signal-row {
        grid-template-columns: 1fr;
      }
      .watch-row {
        flex-direction: column;
      }
    }
    """

    title = _safe(report["title"])
    subtitle = _safe(report["subtitle"])
    intro_note = _safe(report["intro_note"])
    public_notebook = _safe(source["public_notebook_path"])
    public_bundle = _safe(source["public_bundle_dir"])
    public_markdown = _safe(source["public_report_markdown_path"])
    public_metadata = _safe(source["public_report_metadata_path"])
    public_figures = _safe(source["public_figures_dir"])

    top_five_story = top5
    line_items = _render_top_five_bars(top_five_story)
    split_signal = _render_split_signal(finding_map)
    watch_list = _render_watch_list(finding_map)

    body = f"""
    <main class="notebook-shell">
      <section class="hero">
        <div class="hero-copy">
          <div class="eyebrow">Manual workbook / April 2026</div>
          <h1>{title}</h1>
          <p class="hero-subtitle">{subtitle}</p>
          <p class="hero-note">{intro_note}</p>
          <div class="badge-row" aria-label="Report metadata">
            {_render_badges([
                f"Schema {report['schema_version']}",
                f"Generated {generated_at}",
                "Notebook + markdown + SVG",
                f"Source: {report['report_id']}",
            ])}
          </div>
        </div>

        <aside class="hero-panel">
          <div class="hero-panel-top">
            <div class="section-label">At a Glance</div>
            <div class="hero-panel-note">Notebook-style output</div>
          </div>
          <div class="kpi-grid">
            {''.join(_render_stat(metric['label'], metric['value']) for metric in report['at_a_glance'])}
          </div>
          <div class="hero-callout">
            <strong>Why this matters</strong>
            <ul>
              <li>Top five teams are separated by only {_safe(_fmt(score_gap, 3))} composite points.</li>
              <li>RPI and composite only partially agree, so the top-line story splits cleanly.</li>
              <li>Texas Tech, Megan Grant, and Tennessee create the strongest pressure points in the file.</li>
            </ul>
          </div>
        </aside>
      </section>

      <nav class="section-rail" aria-label="Notebook sections">
        <a href="#overview">Overview</a>
        <a href="#signals">Signals</a>
        <a href="#figures">Figures</a>
        <a href="#storyboard">Storyboard</a>
        <a href="#findings">Findings</a>
        <a href="#notes">Notes</a>
      </nav>

      <section id="overview" class="section-block">
        <div class="section-title-wrap">
          <div class="section-label">Editorial bridge</div>
          <h2>{_safe(report["storyboard"]["arc_title"])}</h2>
          <p class="section-subtitle">
            The report keeps the original workbook structure, but the notebook treatment sharpens the sequencing:
            story first, evidence second, and a few additional visual cues to make the split rankings and top-heavy
            player board easier to read.
          </p>
        </div>

        <div class="topline-panel">
          <article class="card">
            <div class="section-label">Top-line note</div>
            <h3>Leadership is live, not locked</h3>
            <p class="summary-copy">
              Texas Tech leads the composite board, but the top five sit close enough together that weekly movement
              still matters. That is what makes this workbook feel like a live story instead of a static ranking.
            </p>
          </article>
          <article class="card">
            <div class="section-label">Story in one glance</div>
            <h3>RPI and composite split the top line</h3>
            <p class="summary-copy">
              Arkansas owns RPI, Texas Tech owns the composite, and the correlation stays only moderate at
              {_safe(_fmt(finding_map["02"]["evidence"]["rank_correlation"], 2))}.
            </p>
          </article>
          <article class="card">
            <div class="section-label">Watch list</div>
            <h3>Bat, staff, balance</h3>
            <p class="summary-copy">
              Megan Grant, Tennessee, and Nebraska each add a different kind of proof: offensive firepower, run
              prevention, and balance.
            </p>
          </article>
        </div>
      </section>

      <section id="signals" class="section-block">
        <div class="section-title-wrap">
          <div class="section-label">Signals</div>
          <h2>What the workbook is really saying</h2>
          <p class="section-subtitle">
            These companion cards add a little more editorial texture to the existing report structure without
            changing the underlying findings.
          </p>
        </div>

        <div class="story-strip">
          <article class="card">
            <div class="section-label">Why this matters</div>
            <h3>Top-five movement is still in play</h3>
            <p>Texas Tech leads, but the spread is tight enough for a weekly shuffle.</p>
            {line_items}
          </article>

          <article class="card">
            <div class="section-label">Split signal</div>
            <h3>RPI and composite do not tell the same story</h3>
            <p>That makes the Arkansas versus Texas Tech contrast the most important ranking split in the file.</p>
            {split_signal}
          </article>

          <article class="card">
            <div class="section-label">What to watch next</div>
            <h3>Big bat, clean staff, balanced profile</h3>
            <p>These are the three most useful follow-up lenses after the headline rankings.</p>
            {watch_list}
          </article>
        </div>
      </section>

      <section class="section-block">
        <div class="section-title-wrap">
          <div class="section-label">Executive summary</div>
          <h2>How the report reads at the top end</h2>
        </div>
        <div class="summary-grid">
          <article class="card summary-card">
            <p class="summary-copy">{_safe(report["executive_summary"])}</p>
            <div class="summary-note">
              <strong>Method note</strong>
              Player batting and player pitching do not need to overlap for the workbook to be useful. They are
              treated as complementary slices rather than a single joined table.
            </div>
            <p class="summary-copy">
              The static notebook lives at <a class="inline-link" href="{public_notebook}">notebook.html</a>, with
              companion markdown at <a class="inline-link" href="{public_markdown}">report.md</a>.
            </p>
          </article>

          <article class="card summary-card">
            <div class="section-label">What the reader should know</div>
            <ul class="bullet-list">
              <li>The composite ranking and the RPI ranking are related, but not interchangeable.</li>
              <li>Tennessee's prevention profile is the cleanest innings-qualified staff story in the workbook.</li>
              <li>The top player board is top-heavy enough to make the individual leaderboard meaningful.</li>
              <li>Coverage gaps matter, so the report keeps batting and pitching views separate where needed.</li>
            </ul>
            <div class="summary-note">
              <strong>Notebook bundle</strong>
              Public bundle: <span style="font-family: JetBrains Mono, Menlo, Consolas, monospace;">{public_bundle}</span>
              <br />
              Figures: <span style="font-family: JetBrains Mono, Menlo, Consolas, monospace;">{public_figures}</span>
            </div>
          </article>
        </div>
      </section>

      <section class="section-block">
        <div class="section-title-wrap">
          <div class="section-label">Key scoreboard</div>
          <h2>Top five by composite score</h2>
          <p class="section-subtitle">
            The table preserves the report payload, while the companion bar chart makes the separation at the top
            easier to read at a glance.
          </p>
        </div>
        <div class="topline-panel">
          <article class="card table-card">
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Team</th>
                    <th>Composite</th>
                    <th>OPS</th>
                    <th>ERA</th>
                    <th>RPI</th>
                  </tr>
                </thead>
                <tbody>
                  {''.join(
                      f"<tr><td>{idx}</td><td>{_safe(row['team'])}</td><td>{_safe(_fmt(row['composite'], 3))}</td>"
                      f"<td>{_safe(_fmt(row['ops'], 3))}</td><td>{_safe(_fmt(row['era'], 2)) if row['has_pitching'] else 'n/a'}</td>"
                      f"<td>{_safe(_fmt(row['rpi'], 0))}</td></tr>"
                      for idx, row in enumerate(top5, start=1)
                  )}
                </tbody>
              </table>
            </div>
          </article>

          <article class="card">
            <div class="section-label">Companion visual</div>
            <h3>Composite separation</h3>
            <p>The leaders are strong, but not stretched apart.</p>
            {line_items}
          </article>

          <article class="card">
            <div class="section-label">Takeaway</div>
            <h3>{_safe(top_team)} is first, but not isolated</h3>
            <p>
              Top-five spread: {_safe(_fmt(score_gap, 3))}. The top tier clusters tightly enough to keep the weekly
              conversation alive.
            </p>
          </article>
        </div>
      </section>

      <section id="figures" class="section-block">
        <div class="section-title-wrap">
          <div class="section-label">Figures</div>
          <h2>Editorial charts from the workbook</h2>
          <p class="section-subtitle">
            The existing SVG figures stay in place, but the notebook presentation gives them more context and a more
            deliberate reading order.
          </p>
        </div>
        {_render_figure_cards(figures)}
      </section>

      <section id="storyboard" class="section-block">
        <div class="section-title-wrap">
          <div class="section-label">Storyboard</div>
          <h2>{_safe(story["arc_title"])}</h2>
          <div class="chip-row" aria-label="Audience tags">
            {_render_badges(story["audience_tags"])}
          </div>
        </div>
        {_render_storyboard(report)}
      </section>

      <section id="findings" class="section-block">
        <div class="section-title-wrap">
          <div class="section-label">Findings</div>
          <h2>Eight publishable insights</h2>
          <p class="section-subtitle">
            The structure stays intact, but the notebook adds a little more spacing, rhythm, and visual hierarchy so
            the findings read like a polished story instead of a raw dump.
          </p>
        </div>
        {_render_findings(findings)}
      </section>

      <section class="section-block">
        <div class="section-title-wrap">
          <div class="section-label">Deep dive queue</div>
          <h2>What to study next</h2>
        </div>
        {_render_deeper_analysis(report["deeper_analysis"])}
      </section>

      <section id="notes" class="section-block">
        <div class="section-title-wrap">
          <div class="section-label">Source notes</div>
          <h2>Coverage and artifact trail</h2>
        </div>
        {_render_source_notes(report)}
      </section>

      <div class="footer">
        Generated {generated_at} from the manual workbook bundle. Public metadata: {public_metadata}
      </div>
    </main>
    """

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"<title>{title}</title>\n"
        f'<meta name="description" content="{subtitle}" />\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Montserrat:wght@500;600;700;800&family=Oswald:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />\n'
        f"<style>{styles}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )
