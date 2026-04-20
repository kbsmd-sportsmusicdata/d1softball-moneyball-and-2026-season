from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import nbformat
import requests

from .config import EDARunConfig
from .contracts import DeeperAnalysisItem, DomainProfile, Finding, StoryboardStep, VisualSuggestion
from .metrics import (
    add_abs_diff_column,
    add_ratio_column,
    add_sum_column,
    add_z_scores,
    coerce_numeric_frame,
    resolve_column,
)
from .notebook_log import build_notebook
from .outputs import json_ready, write_json
from .profiles import load_profile
from .resolvers import DatasetResolver, resolve_bundle

SCHEMA_VERSION = "eda_agent_v2"
DEFAULT_MODEL = "gpt-4o-mini"
REQUIRED_FINDING_CATEGORIES = ("analytical", "elite_talent", "coaching", "fan_first")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
        "numeric_summary": df[numeric_cols].describe().round(4).to_dict() if numeric_cols else {},
        "duplicates": int(df.duplicated().sum()),
    }


def _load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


def _build_findings(teams: pd.DataFrame, players: pd.DataFrame, profile: DomainProfile, max_findings: int = 8) -> list[Finding]:
    teams = coerce_numeric_frame(teams)
    players = coerce_numeric_frame(players)
    findings: list[Finding] = []

    qualification_rules = profile.thresholds.get("qualification_rules", [])
    role_filters = {rule["role"]: rule for rule in qualification_rules if isinstance(rule, dict) and "role" in rule}

    def entity_df(name: str) -> pd.DataFrame:
        return teams.copy() if name == "teams" else players.copy()

    def resolve_metric(df: pd.DataFrame, entity: str, metric: str) -> str | None:
        return resolve_column(df, profile, entity, metric)

    def build_visuals(spec: dict[str, Any], row_context: dict[str, Any]) -> list[VisualSuggestion]:
        visuals = []
        for visual_spec in spec.get("visual_suggestions", [])[:2]:
            visuals.append(
                VisualSuggestion(
                    chart_type=str(visual_spec["chart_type"]).format(**row_context),
                    x=str(visual_spec["x"]).format(**row_context),
                    y=str(visual_spec["y"]).format(**row_context),
                    segment=str(visual_spec["segment"]).format(**row_context),
                    why=str(visual_spec["why"]).format(**row_context),
                )
            )
        if not visuals:
            visuals.append(
                VisualSuggestion("table", "column", "value", "dataset_profile", "Show the supporting values behind the finding.")
            )
        return visuals[:2]

    def make_context(row: pd.Series, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        context: dict[str, Any] = {str(k): (v.item() if hasattr(v, "item") else v) for k, v in row.to_dict().items()}
        if extra:
            context.update(extra)
        return context

    def add_finding(spec: dict[str, Any], row: pd.Series, evidence: dict[str, Any]) -> None:
        context = make_context(row, evidence)
        findings.append(
            Finding(
                id=str(spec["id"]),
                title=str(spec["title_template"]).format(**context),
                category=str(spec["category"]),
                insight=str(spec["insight_template"]).format(**context),
                evidence=evidence,
                confidence=float(spec.get("confidence", 0.75)),
                audience_tags=[str(tag) for tag in spec.get("audience_tags", ["analyst"])],
                visual_suggestions=build_visuals(spec, context),
                provenance={
                    "metrics_used": spec.get("metrics_used", []),
                    "generation": "deterministic",
                    "profile": profile.name,
                },
            )
        )

    for spec in profile.finding_specs:
        entity = spec.get("entity", "teams")
        df = entity_df(entity)
        if df.empty:
            continue

        kind = spec.get("kind")
        if kind == "team_rank":
            metric = resolve_metric(df, "teams", str(spec["sort_by"]))
            if metric is None:
                continue
            ranked = df.dropna(subset=[metric]).sort_values(metric, ascending=False)
            if ranked.empty:
                continue
            row = ranked.iloc[0]
            add_finding(spec, row, {"team": str(row.get("team_name", row.get("team_id", "unknown"))), spec["sort_by"]: _safe_float(row[metric])})

        elif kind == "team_balance":
            left = resolve_metric(df, "teams", str(spec["left_metric"]))
            right = resolve_metric(df, "teams", str(spec["right_metric"]))
            if not left or not right:
                continue
            tmp = add_abs_diff_column(df, left, right, "_balance_gap")
            ranked = tmp.dropna(subset=["_balance_gap"]).sort_values(["_balance_gap", left], ascending=[True, False])
            if ranked.empty:
                continue
            row = ranked.iloc[0]
            add_finding(
                spec,
                row,
                {
                    "team": str(row.get("team_name", row.get("team_id", "unknown"))),
                    left: _safe_float(row[left]),
                    right: _safe_float(row[right]),
                    "balance_gap": _safe_float(row["_balance_gap"]),
                },
            )

        elif kind == "player_rank":
            role = str(spec.get("role", ""))
            rule = role_filters.get(role, {})
            if "column" in rule:
                filter_col = resolve_metric(df, "players", str(rule["column"]))
                if filter_col is None:
                    continue
                min_value = float(rule.get("minimum", 0))
                qualified = df[pd.to_numeric(df[filter_col], errors="coerce") >= min_value].copy()
            else:
                qualified = df.copy()
            metric = resolve_metric(qualified, "players", str(spec["sort_by"]))
            if metric is None:
                continue
            ranked = qualified.dropna(subset=[metric]).sort_values(metric, ascending=False)
            if ranked.empty:
                continue
            row = ranked.iloc[0]
            evidence = {
                "player": str(row.get("player_name", row.get("player_id", "unknown"))),
                "team": str(row.get("team_name", row.get("team_id", "unknown"))),
                spec["sort_by"]: _safe_float(row[metric]),
            }
            if "column" in rule:
                evidence[rule["column"]] = _safe_float(row[filter_col]) if filter_col else None
            add_finding(spec, row, evidence)

        elif kind == "player_rate":
            role = str(spec.get("role", ""))
            rule = role_filters.get(role, {})
            qualified = df.copy()
            if "column" in rule:
                filter_col = resolve_metric(df, "players", str(rule["column"]))
                if filter_col is None:
                    continue
                qualified = qualified[pd.to_numeric(qualified[filter_col], errors="coerce") >= float(rule.get("minimum", spec.get("minimum", 0)))]
            numerator = resolve_metric(qualified, "players", str(spec["numerator"]))
            denominator = resolve_metric(qualified, "players", str(spec["denominator"]))
            if numerator is None or denominator is None:
                continue
            metric_name = spec.get("metric_name") or f"{spec['numerator']}_per_{spec['denominator']}"
            enriched = add_ratio_column(qualified, numerator, denominator, metric_name, scale=float(spec.get("scale", 1.0)))
            ranked = enriched.dropna(subset=[metric_name]).sort_values(metric_name, ascending=False)
            if ranked.empty:
                continue
            row = ranked.iloc[0]
            evidence = {
                "player": str(row.get("player_name", row.get("player_id", "unknown"))),
                "team": str(row.get("team_name", row.get("team_id", "unknown"))),
                metric_name: _safe_float(row[metric_name]),
                spec["numerator"]: _safe_float(row[numerator]),
                spec["denominator"]: _safe_float(row[denominator]),
            }
            add_finding(spec, row, evidence)

        elif kind == "combo":
            metrics = [resolve_metric(df, entity, str(metric)) for metric in spec.get("metrics", [])]
            metrics = [metric for metric in metrics if metric is not None]
            if not metrics:
                continue
            metric_name = str(spec.get("metric_name", "combo_score"))
            direction = str(spec.get("direction", "higher"))
            combo_df = add_sum_column(df, metrics, metric_name, direction=direction)
            ranked = combo_df.dropna(subset=[metric_name]).sort_values(metric_name, ascending=False)
            if direction == "lower":
                ranked = combo_df.dropna(subset=[metric_name]).sort_values(metric_name, ascending=True)
            if ranked.empty:
                continue
            row = ranked.iloc[0]
            evidence = {
                "entity": entity,
                metric_name: _safe_float(row[metric_name]),
                "metrics": {metric: _safe_float(row[metric]) for metric in metrics},
            }
            if entity == "players":
                evidence["player"] = str(row.get("player_name", row.get("player_id", "unknown")))
                evidence["team"] = str(row.get("team_name", row.get("team_id", "unknown")))
            else:
                evidence["team"] = str(row.get("team_name", row.get("team_id", "unknown")))
            add_finding(spec, row, evidence)

        elif kind == "top_race":
            metric = resolve_metric(df, "teams", str(spec["rank_metric"]))
            if metric is None:
                continue
            top_n = int(spec.get("top_n", 5))
            ascending = bool(spec.get("ascending", True))
            ranked = df.dropna(subset=[metric]).sort_values(metric, ascending=ascending).head(top_n)
            if ranked.empty:
                continue
            row = ranked.iloc[0]
            evidence = {
                "top_teams": ranked[[c for c in ["team_name", "team_id", metric] if c in ranked.columns]].to_dict(orient="records"),
            }
            add_finding(spec, row, evidence)

        elif kind == "dataset_quality":
            evidence = {
                "teams_rows": int(len(teams)),
                "players_rows": int(len(players)),
            }
            row = teams.iloc[0] if not teams.empty else pd.Series(dtype=object)
            add_finding(spec, row, evidence)

    categories = {finding.category for finding in findings}
    missing_categories = [category for category in REQUIRED_FINDING_CATEGORIES if category not in categories]
    for idx, category in enumerate(missing_categories, start=1):
        base_row = teams.iloc[0] if not teams.empty else pd.Series(dtype=object)
        findings.append(
            Finding(
                id=f"FM{idx}",
                title=f"{category.replace('_', ' ').title()} lens is currently data-limited",
                category=category,
                insight="This angle is included via fallback coverage until richer fields are available.",
                evidence={"teams_rows": int(len(teams)), "players_rows": int(len(players))},
                confidence=0.52,
                audience_tags=["analyst"],
                visual_suggestions=[VisualSuggestion("table", "column", "missing_pct", "dataset_profile", "Show data gaps behind this lens.")],
                provenance={"metrics_used": ["row_counts"], "generation": "deterministic_fallback", "profile": profile.name},
            )
        )

    if len(findings) < 5:
        for idx in range(5 - len(findings)):
            base_row = teams.iloc[0] if not teams.empty else pd.Series(dtype=object)
            findings.append(
                Finding(
                    id=f"FX{idx+1}",
                    title=f"Dataset quality checkpoint {idx + 1}",
                    category="analytical",
                    insight="Additional quality/context signal retained to satisfy the minimum finding count.",
                    evidence={"teams_rows": int(len(teams)), "players_rows": int(len(players))},
                    confidence=0.55,
                    audience_tags=["analyst"],
                    visual_suggestions=[VisualSuggestion("table", "column", "missing_pct", "dataset_profile", "Provide quick data reliability scan.")],
                    provenance={"metrics_used": ["row_counts"], "generation": "deterministic_fallback", "profile": profile.name},
                )
            )

    target_count = max(5, min(10, max_findings))
    selected: list[Finding] = []
    for category in REQUIRED_FINDING_CATEGORIES:
        match = next((finding for finding in findings if finding.category == category and finding.id not in {s.id for s in selected}), None)
        if match:
            selected.append(match)
    for finding in findings:
        if len(selected) >= target_count:
            break
        if finding.id in {s.id for s in selected}:
            continue
        selected.append(finding)
    return selected[:target_count]


def _build_storyboard(findings: list[Finding], profile: DomainProfile) -> dict[str, Any]:
    by_cat: dict[str, list[Finding]] = {}
    for finding in findings:
        by_cat.setdefault(finding.category, []).append(finding)

    ordered: list[Finding] = []
    priority = profile.storyboard_template.get("priority_categories", ["fan_first", "analytical", "elite_talent", "coaching"])
    for category in priority:
        ordered.extend(by_cat.get(category, []))
    for finding in findings:
        if finding not in ordered:
            ordered.append(finding)

    max_steps = min(8, max(4, len(ordered)))
    selected = ordered[:max_steps]
    step_types = ["hook", "evidence", "contrast", "implication", "action", "support", "support", "close"]
    transitions = [
        "Start with what the audience immediately cares about.",
        "Ground the hook in measurable context.",
        "Introduce standout individuals to create contrast.",
        "Translate data into strategic implications.",
        "End with a practical watch-list or action cue.",
        "Reinforce with secondary support.",
        "Add context for continuity.",
        "Close with a forward-looking angle.",
    ]

    steps = [
        StoryboardStep(
            order=index + 1,
            finding_id=finding.id,
            step_type=step_types[index] if index < len(step_types) else "support",
            narrative=f"{finding.title}: {finding.insight}",
            transition=transitions[index] if index < len(transitions) else "Carry momentum to the next finding.",
        )
        for index, finding in enumerate(selected)
    ]

    return {
        "arc_title": profile.storyboard_template.get("arc_title", "What stands out in the latest dataset?"),
        "audience_tags": profile.storyboard_template.get("audience_tags", ["analyst", "fan"]),
        "steps": [asdict(step) for step in steps],
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
            importance="Identifies transferable offensive traits under stronger competition.",
            needed_data=["player splits", "high-leverage situations", "postseason samples"],
            method="Feature importance with holdout seasons",
            priority="high",
        ),
        DeeperAnalysisItem(
            question="Where does usage create hidden fatigue or efficiency edges?",
            importance="Supports coaching decisions on rotation, workload, and recovery windows.",
            needed_data=["player usage", "game logs", "days rest"],
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


def _summary_markdown(run_metadata: dict[str, Any], findings: list[Finding], storyboard: dict[str, Any], deeper: list[DeeperAnalysisItem]) -> str:
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
    for index, finding in enumerate(findings, start=1):
        lines.append(f"{index}. **{finding.title}** ({finding.category}) - {finding.insight}")
    lines.extend(
        [
            "",
            "## Storyboard Arc",
            "",
            f"**{storyboard['arc_title']}**",
        ]
    )
    for step in storyboard["steps"]:
        lines.append(f"- Step {step['order']}: `{step['step_type']}` -> {step['narrative']}")
    lines.append("")
    lines.append("## Deeper Analysis Queue")
    lines.append("")
    for item in deeper:
        lines.append(f"- [{item.priority}] {item.question} ({item.method})")
    return "\n".join(lines)


def _polish_with_llm(findings: list[Finding], model: str) -> tuple[list[Finding], str | None]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return findings, "OPENAI_API_KEY not set"

    payload_findings = [{"id": finding.id, "title": finding.title, "category": finding.category, "insight": finding.insight} for finding in findings]
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
    except Exception as exc:  # pragma: no cover
        return findings, f"LLM polish failed: {exc}"


def _ensure_minimum_data_quality(dataset_profile: dict[str, Any], run_metadata: dict[str, Any]) -> None:
    warnings: list[str] = []
    player_nonzero = dataset_profile["players"].get("nonzero_counts", {})
    if player_nonzero.get("ab", 0) == 0:
        warnings.append("player batting production is unavailable in the current player rows: AB=0 for all rows")
    if player_nonzero.get("ops", 0) == 0:
        warnings.append("player OPS is unavailable in the current player rows: OPS=0 for all rows")
    if player_nonzero.get("ip", 0) <= 1:
        warnings.append(f"pitching workload is sparse in the current player rows: IP>0 for only {player_nonzero.get('ip', 0)} row(s)")
    run_metadata.setdefault("warnings", []).extend(warnings)


def run_agent(config: EDARunConfig) -> dict[str, Any]:
    bundle = resolve_bundle(config)
    profile = load_profile(bundle.profile_name if config.profile_name == "auto" else config.profile_name)

    # Apply compatibility overrides from the original softball v1 config if present.
    if config.min_player_ab is not None or config.min_player_ip is not None or config.min_qualified_rows is not None:
        profile = _apply_legacy_threshold_overrides(profile, config)

    teams = _load_csv(bundle.teams_path)
    players = _load_csv(bundle.players_path)
    max_findings = max(5, min(10, config.max_findings))

    generated_at = _utc_now()
    run_id = generated_at.strftime("%Y-%m-%dT%H%M%SZ")
    run_dir = config.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    teams = _enrich_team_frame(teams, profile)
    players = _enrich_player_frame(players, profile)

    dataset_profile = {
        "bundle": {
            "source_root": str(bundle.source_root),
            "teams_path": str(bundle.teams_path),
            "players_path": str(bundle.players_path),
            "dataset_label": bundle.dataset_label,
            "dataset_version": bundle.dataset_version,
            "profile_name": bundle.profile_name,
            "resolution_mode": bundle.resolution_mode,
        },
        "teams": _profile_dataframe(teams, "teams"),
        "players": _profile_dataframe(players, "players"),
    }

    findings = build_findings(teams=teams, players=players, profile=profile, max_findings=max_findings)
    llm_error = None
    if config.llm_enabled if config.llm_enabled is not None else bool(os.getenv("OPENAI_API_KEY", "").strip()):
        findings, llm_error = _polish_with_llm(findings, model=config.llm_model)

    storyboard = build_storyboard(findings=findings, profile=profile)
    deeper = _build_deeper_analysis(teams, players)

    run_metadata = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_label": config.run_label,
        "generated_at_utc": generated_at.isoformat(),
        "source": {
            "mode": bundle.resolution_mode,
            "profile_name": bundle.profile_name,
            "dataset_label": bundle.dataset_label,
            "dataset_version": bundle.dataset_version,
            "source_root": str(bundle.source_root),
            "manifest_path": str(bundle.manifest_path) if bundle.manifest_path is not None else None,
            "teams_path": str(bundle.teams_path),
            "players_path": str(bundle.players_path),
            "teams_rows": int(len(teams)),
            "players_rows": int(len(players)),
        },
        "config": {
            "profile_name": profile.name,
            "max_findings": max_findings,
            "llm_enabled": bool(config.llm_enabled if config.llm_enabled is not None else bool(os.getenv("OPENAI_API_KEY", "").strip())),
            "llm_model": config.llm_model,
            "qualification_rules": profile.thresholds.get("qualification_rules", []),
        },
        "outputs": {
            "findings_count": len(findings),
            "storyboard_steps": len(storyboard["steps"]),
            "deeper_analysis_count": len(deeper),
        },
        "warnings": [msg for msg in [llm_error] if msg],
    }
    _ensure_minimum_data_quality(dataset_profile, run_metadata)

    write_json(run_dir / "run_metadata.json", run_metadata)
    write_json(run_dir / "dataset_profile.json", dataset_profile)
    write_json(run_dir / "findings.json", [asdict(finding) for finding in findings])
    write_json(run_dir / "storyboard.json", storyboard)
    write_json(run_dir / "deeper_analysis.json", [asdict(item) for item in deeper])

    summary_md = _summary_markdown(run_metadata, findings, storyboard, deeper)
    (run_dir / "summary.md").write_text(summary_md)

    notebook = build_notebook(
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
        "profile_name": profile.name,
        "dataset_label": bundle.dataset_label,
        "resolution_mode": bundle.resolution_mode,
        "source_root": str(bundle.source_root),
        "manifest_path": str(bundle.manifest_path) if bundle.manifest_path is not None else None,
    }
    config.output_root.mkdir(parents=True, exist_ok=True)
    write_json(config.output_root / "latest.json", latest_payload)

    return {
        "run_id": run_id,
        "run_path": str(run_dir),
        "teams_rows": int(len(teams)),
        "players_rows": int(len(players)),
        "findings_count": len(findings),
        "storyboard_steps": len(storyboard["steps"]),
        "deeper_analysis_count": len(deeper),
        "llm_used": bool(config.llm_enabled if config.llm_enabled is not None else bool(os.getenv("OPENAI_API_KEY", "").strip())),
        "warnings": run_metadata["warnings"],
    }


def _apply_legacy_threshold_overrides(profile: DomainProfile, config: EDARunConfig) -> DomainProfile:
    profile_copy = DomainProfile(**json.loads(json.dumps(profile.__dict__, default=str)))
    rules = profile_copy.thresholds.setdefault("qualification_rules", [])
    for rule in rules:
        if rule.get("role") in {"qualified_hitters", "qualified_scorers"} and config.min_player_ab is not None:
            rule["minimum"] = float(config.min_player_ab)
        if rule.get("role") in {"qualified_pitchers", "qualified_rotation"} and config.min_player_ip is not None:
            rule["minimum"] = float(config.min_player_ip)
        if config.min_qualified_rows is not None and "minimum" not in rule:
            rule["minimum"] = float(config.min_qualified_rows)
    return profile_copy


def _enrich_team_frame(teams: pd.DataFrame, profile: DomainProfile) -> pd.DataFrame:
    teams = coerce_numeric_frame(teams)
    if profile.name == "softball":
        teams = add_z_scores(teams, [col for col in ["composite_score", "offense_z", "pitching_z", "discipline_z", "defense_z", "era", "whip"] if col in teams.columns], prefix="z_")
        if "discipline_z" in teams.columns and "defense_z" in teams.columns:
            teams["coaching_signal"] = pd.to_numeric(teams["discipline_z"], errors="coerce") + pd.to_numeric(teams["defense_z"], errors="coerce")
        if "era" in teams.columns and "whip" in teams.columns:
            teams["run_prevention_index"] = -(pd.to_numeric(teams["era"], errors="coerce") + pd.to_numeric(teams["whip"], errors="coerce"))
    elif profile.name == "basketball":
        teams = add_z_scores(teams, [col for col in ["net_rating", "off_rating", "def_rating", "assist_rate", "turnover_rate"] if col in teams.columns], prefix="z_")
        if "assist_rate" in teams.columns and "turnover_rate" in teams.columns:
            teams["playmaking_signal"] = pd.to_numeric(teams["assist_rate"], errors="coerce") + pd.to_numeric(teams["turnover_rate"], errors="coerce")
        if "def_rating" in teams.columns and "opp_fg_pct" in teams.columns:
            teams["defensive_signal"] = -(pd.to_numeric(teams["def_rating"], errors="coerce") + pd.to_numeric(teams["opp_fg_pct"], errors="coerce"))
    return teams


def _enrich_player_frame(players: pd.DataFrame, profile: DomainProfile) -> pd.DataFrame:
    players = coerce_numeric_frame(players)
    if profile.name == "softball":
        if "ab" in players.columns and "so" in players.columns:
            players["so_rate"] = pd.to_numeric(players["so"], errors="coerce") / pd.to_numeric(players["ab"], errors="coerce").replace(0, pd.NA)
        if "k" in players.columns and "ip" in players.columns:
            players["k_per_7"] = pd.to_numeric(players["k"], errors="coerce") / pd.to_numeric(players["ip"], errors="coerce").replace(0, pd.NA) * 7.0
        if "iso" in players.columns and "so_rate" in players.columns:
            players["boom_bust"] = pd.to_numeric(players["iso"], errors="coerce").fillna(0) + pd.to_numeric(players["so_rate"], errors="coerce").fillna(0)
    elif profile.name == "basketball":
        if "points" in players.columns and "minutes" in players.columns:
            players["points_per_minute"] = pd.to_numeric(players["points"], errors="coerce") / pd.to_numeric(players["minutes"], errors="coerce").replace(0, pd.NA)
        if "assists" in players.columns and "minutes" in players.columns:
            players["assists_per_minute"] = pd.to_numeric(players["assists"], errors="coerce") / pd.to_numeric(players["minutes"], errors="coerce").replace(0, pd.NA)
        if "rebounds" in players.columns and "minutes" in players.columns:
            players["rebounds_per_minute"] = pd.to_numeric(players["rebounds"], errors="coerce") / pd.to_numeric(players["minutes"], errors="coerce").replace(0, pd.NA)
    return players


def build_findings(teams: pd.DataFrame, players: pd.DataFrame, profile: DomainProfile, max_findings: int = 8) -> list[Finding]:
    return _build_findings(teams, players, profile, max_findings=max_findings)


def build_storyboard(findings: list[Finding], profile: DomainProfile) -> dict[str, Any]:
    return _build_storyboard(findings, profile)


def polish_with_llm(findings: list[Finding], model: str) -> tuple[list[Finding], str | None]:
    return _polish_with_llm(findings, model)
