from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nbformat
import pandas as pd
import requests

SCHEMA_VERSION = "eda_agent_v1"
DEFAULT_OUTPUT_ROOT = Path("eda_runs")
DEFAULT_MODEL = "gpt-4o-mini"
REQUIRED_FINDING_CATEGORIES = ("analytical", "elite_talent", "coaching", "fan_first")


@dataclass
class EDARunConfig:
    teams_path: Path | None
    players_path: Path | None
    run_label: str
    output_root: Path
    min_player_ab: int
    min_player_ip: float
    max_findings: int
    llm_enabled: bool
    llm_model: str


@dataclass
class VisualSuggestion:
    chart_type: str
    x: str
    y: str
    segment: str
    why: str


@dataclass
class Finding:
    id: str
    title: str
    category: str
    insight: str
    evidence: dict[str, Any]
    confidence: float
    audience_tags: list[str]
    visual_suggestions: list[VisualSuggestion]
    provenance: dict[str, Any]


@dataclass
class StoryboardStep:
    order: int
    finding_id: str
    step_type: str
    narrative: str
    transition: str


@dataclass
class DeeperAnalysisItem:
    question: str
    importance: str
    needed_data: list[str]
    method: str
    priority: str


class DatasetResolver:
    """Path-based resolver with hooks for future cross-repo adapters."""

    @staticmethod
    def resolve(teams_path: Path | None, players_path: Path | None) -> tuple[Path, Path, str]:
        if teams_path and players_path:
            return teams_path, players_path, "explicit"

        if teams_path or players_path:
            raise RuntimeError("Provide both --teams-path and --players-path, or neither.")

        processed_root = Path("data/processed")
        if not processed_root.exists():
            raise RuntimeError("data/processed directory not found.")

        candidates = []
        for folder in processed_root.iterdir():
            if not folder.is_dir():
                continue
            teams_csv = folder / "teams.csv"
            players_csv = folder / "players.csv"
            if teams_csv.exists() and players_csv.exists():
                candidates.append(folder)

        if not candidates:
            raise RuntimeError("No data/processed/* folders with teams.csv and players.csv found.")

        latest = sorted(candidates, key=lambda p: p.name)[-1]
        return latest / "teams.csv", latest / "players.csv", "latest_processed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EDA analyst agent on team/player datasets.")
    parser.add_argument("--teams-path", type=Path)
    parser.add_argument("--players-path", type=Path)
    parser.add_argument("--run-label", type=str, default="default")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--min-player-ab", type=int, default=30)
    parser.add_argument("--min-player-ip", type=float, default=20.0)
    parser.add_argument("--max-findings", type=int, default=8)
    parser.add_argument("--llm-model", type=str, default=DEFAULT_MODEL)
    return parser.parse_args()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return _json_ready(value.item())
        except Exception:
            pass
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2))


def _profile_dataframe(df: pd.DataFrame, label: str) -> dict[str, Any]:
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    missing = (df.isna().mean().sort_values(ascending=False) * 100).round(2)
    nonzero_counts = {
        str(col): int((pd.to_numeric(df[col], errors="coerce").fillna(0) != 0).sum())
        for col in numeric_cols
    }

    return {
        "dataset": label,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": [str(c) for c in df.columns.tolist()],
        "missing_pct": {str(k): float(v) for k, v in missing.to_dict().items()},
        "nonzero_counts": nonzero_counts,
        "numeric_summary": (
            df[numeric_cols].describe().round(4).to_dict() if numeric_cols else {}
        ),
        "duplicates": int(df.duplicated().sum()),
    }


def _build_findings(
    teams: pd.DataFrame,
    players: pd.DataFrame,
    min_player_ab: int,
    min_player_ip: float,
    max_findings: int,
) -> list[Finding]:
    findings: list[Finding] = []

    def add(finding: Finding) -> None:
        findings.append(finding)

    t = teams.copy()
    p = players.copy()

    for col in ["composite_score", "offense_z", "pitching_z", "discipline_z", "defense_z", "runs_per_game", "whip", "era", "bb_k_ratio", "fielding_pct"]:
        if col in t.columns:
            t[col] = pd.to_numeric(t[col], errors="coerce")

    for col in ["ab", "hr", "ops", "iso", "k", "ip", "ha", "er", "bb", "h", "so"]:
        if col in p.columns:
            p[col] = pd.to_numeric(p[col], errors="coerce")

    if "composite_score" in t.columns and not t["composite_score"].dropna().empty:
        top = t.sort_values("composite_score", ascending=False).iloc[0]
        add(
            Finding(
                id="F01",
                title=f"{top['team_name']} leads the all-around team profile",
                category="analytical",
                insight=f"{top['team_name']} ranks first by composite score, signaling balanced strength across offense, pitching, discipline, and defense.",
                evidence={
                    "team": str(top["team_name"]),
                    "composite_score": float(top["composite_score"]),
                    "composite_rank": int(top.get("composite_rank", 1)),
                },
                confidence=0.91,
                audience_tags=["analyst", "coaching", "fan"],
                visual_suggestions=[
                    VisualSuggestion("bar", "team_name", "composite_score", "top_10_teams", "Show overall separation among top teams."),
                    VisualSuggestion("radar", "component", "z_score", str(top["team_name"]), "Show component balance shape for the leader."),
                ],
                provenance={"metrics_used": ["composite_score", "composite_rank"], "generation": "deterministic"},
            )
        )

    if all(c in t.columns for c in ["offense_z", "pitching_z"]) and not t[["offense_z", "pitching_z"]].dropna().empty:
        tmp = t.copy()
        tmp["balance_gap"] = (tmp["offense_z"] - tmp["pitching_z"]).abs()
        balanced = tmp.sort_values(["balance_gap", "composite_score"], ascending=[True, False]).iloc[0]
        add(
            Finding(
                id="F02",
                title=f"{balanced['team_name']} shows one of the most balanced profiles",
                category="analytical",
                insight=f"{balanced['team_name']} has near-matching offense and pitching z-scores, which usually translates to stable game-to-game performance.",
                evidence={
                    "team": str(balanced["team_name"]),
                    "offense_z": float(balanced["offense_z"]),
                    "pitching_z": float(balanced["pitching_z"]),
                    "balance_gap": float(balanced["balance_gap"]),
                },
                confidence=0.84,
                audience_tags=["analyst", "coaching"],
                visual_suggestions=[
                    VisualSuggestion("scatter", "offense_z", "pitching_z", "all_teams", "Identify balanced teams near the diagonal."),
                    VisualSuggestion("dumbbell", "team_name", "offense_vs_pitching", "top_25_teams", "Highlight internal gap between unit strengths."),
                ],
                provenance={"metrics_used": ["offense_z", "pitching_z"], "generation": "deterministic"},
            )
        )

    hitters = p[p.get("ab", 0) >= min_player_ab].copy() if "ab" in p.columns else pd.DataFrame()
    if not hitters.empty and "ops" in hitters.columns and not hitters["ops"].dropna().empty:
        elite = hitters.sort_values("ops", ascending=False).iloc[0]
        add(
            Finding(
                id="F03",
                title=f"{elite['player_name']} is the top OPS impact bat",
                category="elite_talent",
                insight=f"{elite['player_name']} currently sets the pace in OPS among qualified hitters, indicating elite on-base plus power production.",
                evidence={
                    "player": str(elite["player_name"]),
                    "team": str(elite.get("team_name", elite.get("team_id", "unknown"))),
                    "ops": float(elite["ops"]),
                    "ab": float(elite["ab"]),
                },
                confidence=0.89,
                audience_tags=["analyst", "fan"],
                visual_suggestions=[
                    VisualSuggestion("bar", "player_name", "ops", "qualified_hitters_top15", "Rank elite OPS profiles."),
                    VisualSuggestion("scatter", "iso", "ops", "qualified_hitters", "Separate pure power from overall production."),
                ],
                provenance={"metrics_used": ["ops", "ab", "iso"], "generation": "deterministic"},
            )
        )

    if not hitters.empty and "hr" in hitters.columns and not hitters["hr"].dropna().empty:
        slugger = hitters.sort_values("hr", ascending=False).iloc[0]
        add(
            Finding(
                id="F04",
                title=f"{slugger['player_name']} leads the long-ball race",
                category="elite_talent",
                insight=f"{slugger['player_name']} leads qualified hitters in home runs, creating game-changing swing outcomes.",
                evidence={
                    "player": str(slugger["player_name"]),
                    "team": str(slugger.get("team_name", slugger.get("team_id", "unknown"))),
                    "hr": float(slugger["hr"]),
                    "ab": float(slugger["ab"]),
                },
                confidence=0.86,
                audience_tags=["fan", "coaching"],
                visual_suggestions=[
                    VisualSuggestion("bar", "player_name", "hr", "qualified_hitters_top15", "Highlight top home-run threats."),
                    VisualSuggestion("scatter", "ab", "hr", "qualified_hitters", "Compare volume and power conversion."),
                ],
                provenance={"metrics_used": ["hr", "ab"], "generation": "deterministic"},
            )
        )

    pitchers = p[p.get("ip", 0) >= min_player_ip].copy() if "ip" in p.columns else pd.DataFrame()
    if not pitchers.empty and all(c in pitchers.columns for c in ["k", "ip"]):
        pitchers = pitchers[pitchers["ip"] > 0].copy()
        if not pitchers.empty:
            pitchers["k_per_7"] = pitchers["k"] / pitchers["ip"] * 7.0
            arm = pitchers.sort_values("k_per_7", ascending=False).iloc[0]
            add(
                Finding(
                    id="F05",
                    title=f"{arm['player_name']} is the top bat-missing arm",
                    category="elite_talent",
                    insight=f"On a workload-adjusted basis, {arm['player_name']} leads qualified pitchers in strikeouts per 7 innings.",
                    evidence={
                        "player": str(arm["player_name"]),
                        "team": str(arm.get("team_name", arm.get("team_id", "unknown"))),
                        "k_per_7": float(arm["k_per_7"]),
                        "ip": float(arm["ip"]),
                    },
                    confidence=0.82,
                    audience_tags=["analyst", "coaching"],
                    visual_suggestions=[
                        VisualSuggestion("bar", "player_name", "k_per_7", "qualified_pitchers_top15", "Rank bat-missing profiles."),
                        VisualSuggestion("scatter", "ip", "k_per_7", "qualified_pitchers", "Separate strikeout dominance from workload."),
                    ],
                    provenance={"metrics_used": ["k", "ip", "k_per_7"], "generation": "deterministic"},
                )
            )

    if all(c in t.columns for c in ["discipline_z", "defense_z"]):
        coach = t.copy()
        coach["coaching_signal"] = coach["discipline_z"] + coach["defense_z"]
        top_coach = coach.sort_values("coaching_signal", ascending=False).iloc[0]
        add(
            Finding(
                id="F06",
                title=f"{top_coach['team_name']} profiles as a coaching-efficiency standout",
                category="coaching",
                insight=f"{top_coach['team_name']} combines strong discipline and defensive execution, a common marker of repeatable coaching impact.",
                evidence={
                    "team": str(top_coach["team_name"]),
                    "discipline_z": float(top_coach["discipline_z"]),
                    "defense_z": float(top_coach["defense_z"]),
                    "coaching_signal": float(top_coach["coaching_signal"]),
                },
                confidence=0.8,
                audience_tags=["coaching", "analyst"],
                visual_suggestions=[
                    VisualSuggestion("scatter", "discipline_z", "defense_z", "all_teams", "Show which teams pair clean ABs with clean defense."),
                    VisualSuggestion("bar", "team_name", "coaching_signal", "top_10_teams", "Rank combined discipline/defense signal."),
                ],
                provenance={"metrics_used": ["discipline_z", "defense_z"], "generation": "deterministic"},
            )
        )

    if all(c in t.columns for c in ["era", "whip"]):
        run_prev = t.copy()
        run_prev = run_prev.dropna(subset=["era", "whip"]).copy()
        if not run_prev.empty:
            run_prev["run_prevention_index"] = -(run_prev["era"] + run_prev["whip"])
            rp = run_prev.sort_values("run_prevention_index", ascending=False).iloc[0]
            add(
                Finding(
                    id="F07",
                    title=f"{rp['team_name']} owns the strongest run-prevention signal",
                    category="coaching",
                    insight=f"{rp['team_name']} ranks near the top in both ERA and WHIP, suggesting dependable prevention quality.",
                    evidence={"team": str(rp["team_name"]), "era": float(rp["era"]), "whip": float(rp["whip"])},
                    confidence=0.85,
                    audience_tags=["coaching", "fan"],
                    visual_suggestions=[
                        VisualSuggestion("scatter", "whip", "era", "all_teams", "Locate true run-prevention outliers."),
                        VisualSuggestion("bar", "team_name", "runs_allowed_proxy", "top_10_teams", "Translate prevention edge into fan-facing ranking."),
                    ],
                    provenance={"metrics_used": ["era", "whip"], "generation": "deterministic"},
                )
            )

    if all(c in t.columns for c in ["composite_rank", "team_name"]):
        contenders = t.sort_values("composite_rank").head(5)
        if not contenders.empty:
            add(
                Finding(
                    id="F08",
                    title="Top-5 race is primed for fan-facing weekly drama",
                    category="fan_first",
                    insight="The top of the board is tight enough to produce meaningful weekly movement and marquee matchups.",
                    evidence={
                        "top_5": contenders[["team_name", "composite_rank", "composite_score"]].to_dict(orient="records")
                        if "composite_score" in contenders.columns
                        else contenders[["team_name", "composite_rank"]].to_dict(orient="records")
                    },
                    confidence=0.77,
                    audience_tags=["fan", "analyst"],
                    visual_suggestions=[
                        VisualSuggestion("line", "week_or_run_date", "composite_rank", "top_5_teams", "Track volatility over updates."),
                        VisualSuggestion("bar", "team_name", "composite_score", "top_5_teams", "Show current race separation."),
                    ],
                    provenance={"metrics_used": ["composite_rank", "composite_score"], "generation": "deterministic"},
                )
            )

    if "iso" in p.columns and "so" in p.columns and "ab" in p.columns:
        fun = p[p["ab"] >= min_player_ab].copy()
        if not fun.empty:
            fun["boom_bust"] = fun["iso"].fillna(0) + (fun["so"].fillna(0) / fun["ab"].replace(0, pd.NA)).fillna(0)
            boom = fun.sort_values("boom_bust", ascending=False).iloc[0]
            add(
                Finding(
                    id="F09",
                    title=f"{boom['player_name']} is a classic high-variance watch",
                    category="fan_first",
                    insight=f"{boom['player_name']} combines loud power indicators with swing-and-miss risk, producing volatile but exciting outcomes.",
                    evidence={
                        "player": str(boom["player_name"]),
                        "team": str(boom.get("team_name", boom.get("team_id", "unknown"))),
                        "iso": float(boom.get("iso", 0.0)),
                        "so": float(boom.get("so", 0.0)),
                        "ab": float(boom.get("ab", 0.0)),
                        "boom_bust": float(boom.get("boom_bust", 0.0)),
                    },
                    confidence=0.73,
                    audience_tags=["fan", "coaching"],
                    visual_suggestions=[
                        VisualSuggestion("scatter", "iso", "so_rate", "qualified_hitters", "Highlight volatility profiles."),
                        VisualSuggestion("hexbin", "iso", "ops", "qualified_hitters", "Find explosive vs stable hitters."),
                    ],
                    provenance={"metrics_used": ["iso", "so", "ab"], "generation": "deterministic"},
                )
            )

    missing_categories = [
        category for category in REQUIRED_FINDING_CATEGORIES if category not in {f.category for f in findings}
    ]
    for idx, category in enumerate(missing_categories, start=1):
        findings.append(
            Finding(
                id=f"FM{idx}",
                title=f"{category.replace('_', ' ').title()} lens is currently data-limited",
                category=category,
                insight="This angle is included via fallback contract coverage until richer fields are available.",
                evidence={"teams_rows": int(len(teams)), "players_rows": int(len(players))},
                confidence=0.52,
                audience_tags=["analyst"],
                visual_suggestions=[
                    VisualSuggestion("table", "column", "missing_pct", "dataset_profile", "Show data gaps behind this lens."),
                ],
                provenance={"metrics_used": ["row_counts"], "generation": "deterministic_fallback"},
            )
        )

    # Keep 5-10 findings contract.
    if len(findings) < 5:
        for idx in range(5 - len(findings)):
            findings.append(
                Finding(
                    id=f"FX{idx+1}",
                    title=f"Dataset quality checkpoint {idx+1}",
                    category="analytical",
                    insight="Additional quality/context signal retained to satisfy minimum finding count.",
                    evidence={"teams_rows": int(len(teams)), "players_rows": int(len(players))},
                    confidence=0.55,
                    audience_tags=["analyst"],
                    visual_suggestions=[
                        VisualSuggestion(
                            "table", "column", "missing_pct", "dataset_profile", "Provide quick data reliability scan."
                        ),
                    ],
                    provenance={"metrics_used": ["row_counts"], "generation": "deterministic_fallback"},
                )
            )

    target_count = max(5, min(10, max_findings))
    selected: list[Finding] = []

    # Guarantee category coverage first.
    for category in REQUIRED_FINDING_CATEGORIES:
        match = next((f for f in findings if f.category == category and f.id not in {s.id for s in selected}), None)
        if match:
            selected.append(match)

    # Fill remaining slots preserving deterministic order.
    for finding in findings:
        if len(selected) >= target_count:
            break
        if finding.id in {s.id for s in selected}:
            continue
        selected.append(finding)

    return selected[:target_count]


def _polish_with_llm(findings: list[Finding], model: str) -> tuple[list[Finding], str | None]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return findings, "OPENAI_API_KEY not set"

    payload_findings = [
        {"id": f.id, "title": f.title, "category": f.category, "insight": f.insight} for f in findings
    ]

    prompt = {
        "task": "Polish sports-analytics findings for clarity and concise analyst voice.",
        "rules": [
            "Keep facts unchanged.",
            "Do not invent numbers.",
            "Return JSON object with key 'findings'.",
            "Each finding must contain: id, title, insight.",
            "Keep title <= 14 words, insight <= 45 words.",
        ],
        "findings": payload_findings,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "You rewrite findings into concise, high-signal analyst language."},
                    {"role": "user", "content": json.dumps(prompt)},
                ],
            },
            timeout=45,
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        polished = {item["id"]: item for item in parsed.get("findings", []) if isinstance(item, dict) and "id" in item}

        for finding in findings:
            if finding.id in polished:
                item = polished[finding.id]
                finding.title = str(item.get("title", finding.title))
                finding.insight = str(item.get("insight", finding.insight))
                finding.provenance["generation"] = "deterministic_plus_llm"
        return findings, None
    except Exception as exc:  # pragma: no cover - network-dependent
        return findings, f"LLM polish failed: {exc}"


def _build_storyboard(findings: list[Finding]) -> dict[str, Any]:
    by_cat: dict[str, list[Finding]] = {}
    for f in findings:
        by_cat.setdefault(f.category, []).append(f)

    ordered: list[Finding] = []
    priority = ["fan_first", "analytical", "elite_talent", "coaching"]
    for cat in priority:
        ordered.extend(by_cat.get(cat, []))
    for f in findings:
        if f not in ordered:
            ordered.append(f)

    max_steps = min(8, max(4, len(ordered)))
    selected = ordered[:max_steps]

    step_types = ["hook", "evidence", "contrast", "implication", "action", "support", "support", "close"]
    transitions = [
        "Start with what fans immediately care about.",
        "Ground the hook in measurable team context.",
        "Introduce standout individuals to create contrast.",
        "Translate data into strategic implications.",
        "End with a practical watch-list/action cue.",
        "Reinforce with secondary support.",
        "Add context for continuity.",
        "Close with forward-looking angle.",
    ]

    steps = [
        StoryboardStep(
            order=i + 1,
            finding_id=f.id,
            step_type=step_types[i] if i < len(step_types) else "support",
            narrative=f"{f.title}: {f.insight}",
            transition=transitions[i] if i < len(transitions) else "Carry momentum to the next finding.",
        )
        for i, f in enumerate(selected)
    ]

    return {
        "arc_title": "Who is built to sustain performance and who can swing a series?",
        "audience_tags": ["analyst", "coaching", "fan"],
        "steps": [asdict(s) for s in steps],
    }


def _build_deeper_analysis(teams: pd.DataFrame, players: pd.DataFrame) -> list[DeeperAnalysisItem]:
    items = [
        DeeperAnalysisItem(
            question="Which teams overperform expected results once schedule strength is introduced?",
            importance="Separates true strength from context effects and improves ranking stability.",
            needed_data=["team-level game logs", "opponent quality", "home/away"],
            method="Schedule-adjusted residual modeling",
            priority="high",
        ),
        DeeperAnalysisItem(
            question="Which player profiles are most predictive of postseason run production?",
            importance="Identifies transferable offensive traits under stronger pitching.",
            needed_data=["player splits", "high-leverage situations", "postseason samples"],
            method="Feature importance with holdout seasons",
            priority="high",
        ),
        DeeperAnalysisItem(
            question="Where does pitching usage create hidden fatigue or efficiency edges?",
            importance="Supports coaching decisions on rotation, bullpen leverage, and recovery windows.",
            needed_data=["pitching appearances", "days rest", "opponent strength"],
            method="Usage clustering + rolling trend decomposition",
            priority="medium",
        ),
        DeeperAnalysisItem(
            question="Which fan-facing storylines have the highest week-to-week volatility?",
            importance="Improves content planning around credible, high-interest swings.",
            needed_data=["weekly rankings", "individual performance deltas", "team outcomes"],
            method="Volatility index + change-point detection",
            priority="medium",
        ),
    ]

    # Small adaptive note when fields missing.
    if "team_name" not in teams.columns or "player_name" not in players.columns:
        items.append(
            DeeperAnalysisItem(
                question="How should entity mapping be hardened before deeper modeling?",
                importance="Prevents identity collisions and improves longitudinal consistency.",
                needed_data=["canonical IDs", "name alias map"],
                method="Entity resolution audit",
                priority="high",
            )
        )

    return items[:6]


def _findings_markdown(findings: list[Finding]) -> str:
    lines = ["## Key Findings", ""]
    for i, f in enumerate(findings, start=1):
        lines.append(f"### {i}. {f.title}")
        lines.append(f"- Category: `{f.category}`")
        lines.append(f"- Insight: {f.insight}")
        lines.append(f"- Confidence: {f.confidence:.2f}")
        lines.append("- Visual Suggestions:")
        for v in f.visual_suggestions:
            lines.append(f"  - {v.chart_type}: `{v.x}` vs `{v.y}` ({v.segment}) - {v.why}")
        lines.append("")
    return "\n".join(lines)


def _build_notebook(
    run_config: EDARunConfig,
    run_metadata: dict[str, Any],
    dataset_profile: dict[str, Any],
    findings: list[Finding],
    storyboard: dict[str, Any],
    deeper_analysis: list[DeeperAnalysisItem],
    teams: pd.DataFrame,
    players: pd.DataFrame,
) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()

    findings_md = _findings_markdown(findings)

    team_preview = teams.head(10).to_string(index=False)
    player_preview = players.head(10).to_string(index=False)

    nb.cells = [
        nbformat.v4.new_markdown_cell(
            f"# EDA Analyst Run Log\n\n- Run ID: `{run_metadata['run_id']}`\n- Label: `{run_config.run_label}`\n- Schema: `{SCHEMA_VERSION}`"
        ),
        nbformat.v4.new_markdown_cell(
            "## Setup / Config\n\n```json\n" + json.dumps(_json_ready(asdict(run_config)), indent=2) + "\n```"
        ),
        nbformat.v4.new_markdown_cell(
            "## Dataset Profile + Quality Checks\n\n```json\n" + json.dumps(_json_ready(dataset_profile), indent=2) + "\n```"
        ),
        nbformat.v4.new_markdown_cell(
            "## Metric Engineering\n\n"
            "Generated comparative metrics for team balance, elite player impact, run prevention, and fan-facing volatility signals."
            "\n\n### Team Preview\n\n```\n"
            + team_preview
            + "\n```\n\n### Player Preview\n\n```\n"
            + player_preview
            + "\n```"
        ),
        nbformat.v4.new_markdown_cell(
            "## Hypothesis Checks\n\n"
            "- Teams with stronger combined offensive and run-prevention profiles cluster at the top.\n"
            "- Qualified elite player performance can separate otherwise similar teams.\n"
            "- Coaching signals emerge from discipline + defense consistency."
        ),
        nbformat.v4.new_markdown_cell(findings_md),
        nbformat.v4.new_markdown_cell(
            "## Storyboard Synthesis\n\n```json\n" + json.dumps(_json_ready(storyboard), indent=2) + "\n```"
        ),
        nbformat.v4.new_markdown_cell(
            "## Deeper Analysis Suggestions\n\n```json\n"
            + json.dumps(_json_ready([asdict(item) for item in deeper_analysis]), indent=2)
            + "\n```"
        ),
    ]
    return nb


def _summary_markdown(
    run_metadata: dict[str, Any], findings: list[Finding], storyboard: dict[str, Any], deeper: list[DeeperAnalysisItem]
) -> str:
    lines = [
        "# EDA Analyst Summary",
        "",
        f"- Run ID: `{run_metadata['run_id']}`",
        f"- Generated At: `{run_metadata['generated_at_utc']}`",
        f"- Teams Rows: `{run_metadata['source']['teams_rows']}`",
        f"- Players Rows: `{run_metadata['source']['players_rows']}`",
        "",
        "## Findings",
        "",
    ]

    for i, f in enumerate(findings, start=1):
        lines.append(f"{i}. **{f.title}** ({f.category}) - {f.insight}")

    lines.append("\n## Storyboard Arc\n")
    lines.append(f"**{storyboard['arc_title']}**")
    for step in storyboard["steps"]:
        lines.append(f"- Step {step['order']}: `{step['step_type']}` -> {step['narrative']}")

    lines.append("\n## Deeper Analysis Queue\n")
    for item in deeper:
        lines.append(f"- [{item.priority}] {item.question} ({item.method})")

    return "\n".join(lines)


def run_agent(config: EDARunConfig) -> dict[str, Any]:
    teams_path, players_path, source_mode = DatasetResolver.resolve(config.teams_path, config.players_path)
    teams = pd.read_csv(teams_path)
    players = pd.read_csv(players_path)

    max_findings = max(5, min(10, config.max_findings))

    generated_at = _utc_now()
    run_id = generated_at.strftime("%Y-%m-%dT%H%M%SZ")
    run_dir = config.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    dataset_profile = {
        "teams": _profile_dataframe(teams, "teams"),
        "players": _profile_dataframe(players, "players"),
    }

    player_nonzero = dataset_profile["players"].get("nonzero_counts", {})
    data_warnings: list[str] = []
    if player_nonzero.get("ab", 0) == 0:
        data_warnings.append(
            "player batting production is unavailable in the current player rows: AB=0 for all rows"
        )
    if player_nonzero.get("ops", 0) == 0:
        data_warnings.append("player OPS is unavailable in the current player rows: OPS=0 for all rows")
    if player_nonzero.get("ip", 0) <= 1:
        data_warnings.append(
            f"pitching workload is sparse in the current player rows: IP>0 for only {player_nonzero.get('ip', 0)} row(s)"
        )

    findings = _build_findings(
        teams=teams,
        players=players,
        min_player_ab=config.min_player_ab,
        min_player_ip=config.min_player_ip,
        max_findings=max_findings,
    )

    llm_error = None
    if config.llm_enabled:
        findings, llm_error = _polish_with_llm(findings, model=config.llm_model)

    storyboard = _build_storyboard(findings)
    deeper = _build_deeper_analysis(teams, players)

    run_metadata = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_label": config.run_label,
        "generated_at_utc": generated_at.isoformat(),
        "source": {
            "mode": source_mode,
            "teams_path": str(teams_path),
            "players_path": str(players_path),
            "teams_rows": int(len(teams)),
            "players_rows": int(len(players)),
        },
        "config": {
            "min_player_ab": config.min_player_ab,
            "min_player_ip": config.min_player_ip,
            "max_findings": max_findings,
            "llm_enabled": config.llm_enabled,
            "llm_model": config.llm_model,
        },
        "outputs": {
            "findings_count": len(findings),
            "storyboard_steps": len(storyboard["steps"]),
            "deeper_analysis_count": len(deeper),
        },
        "warnings": [msg for msg in [llm_error] if msg],
    }
    run_metadata["warnings"].extend(data_warnings)

    _write_json(run_dir / "run_metadata.json", run_metadata)
    _write_json(run_dir / "dataset_profile.json", dataset_profile)
    _write_json(run_dir / "findings.json", [asdict(f) for f in findings])
    _write_json(run_dir / "storyboard.json", storyboard)
    _write_json(run_dir / "deeper_analysis.json", [asdict(item) for item in deeper])

    summary_md = _summary_markdown(run_metadata, findings, storyboard, deeper)
    (run_dir / "summary.md").write_text(summary_md)

    notebook = _build_notebook(
        run_config=config,
        run_metadata=run_metadata,
        dataset_profile=dataset_profile,
        findings=findings,
        storyboard=storyboard,
        deeper_analysis=deeper,
        teams=teams,
        players=players,
    )
    nbformat.write(notebook, run_dir / "run_log.ipynb")

    latest_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_path": str(run_dir),
        "generated_at_utc": generated_at.isoformat(),
    }
    config.output_root.mkdir(parents=True, exist_ok=True)
    _write_json(config.output_root / "latest.json", latest_payload)

    result = {
        "run_id": run_id,
        "run_path": str(run_dir),
        "teams_rows": int(len(teams)),
        "players_rows": int(len(players)),
        "findings_count": len(findings),
        "storyboard_steps": len(storyboard["steps"]),
        "deeper_analysis_count": len(deeper),
        "llm_used": config.llm_enabled and llm_error is None,
        "warnings": run_metadata["warnings"],
    }
    return result


def main() -> None:
    args = parse_args()
    llm_enabled = bool(os.getenv("OPENAI_API_KEY", "").strip())

    config = EDARunConfig(
        teams_path=args.teams_path,
        players_path=args.players_path,
        run_label=args.run_label,
        output_root=args.output_root,
        min_player_ab=args.min_player_ab,
        min_player_ip=args.min_player_ip,
        max_findings=args.max_findings,
        llm_enabled=llm_enabled,
        llm_model=args.llm_model,
    )

    result = run_agent(config)
    print(json.dumps(_json_ready(result), indent=2))


if __name__ == "__main__":
    main()
