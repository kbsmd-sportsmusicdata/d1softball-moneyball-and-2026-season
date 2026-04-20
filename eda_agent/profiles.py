from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .contracts import DomainProfile


BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "generic": {
        "name": "generic",
        "sport": "generic",
        "entity_names": {"team": "team", "player": "player"},
        "required_files": ["teams.csv", "players.csv"],
        "thresholds": {"qualification_rules": []},
        "metric_map": {},
        "finding_categories": ["analytical", "elite_talent", "coaching", "fan_first"],
        "storyboard_template": {
            "arc_title": "What stands out in the latest dataset?",
            "audience_tags": ["analyst", "fan"],
            "priority_categories": ["fan_first", "analytical", "elite_talent", "coaching"],
        },
        "alias_rules": {"teams": {}, "players": {}},
        "finding_specs": [],
        "description": "Fallback profile for arbitrary row-based team/player datasets.",
    },
    "softball": {
        "name": "softball",
        "sport": "softball",
        "entity_names": {"team": "team", "player": "player", "game": "game"},
        "required_files": ["teams.csv", "players.csv"],
        "thresholds": {
            "qualification_rules": [
                {"role": "qualified_hitters", "entity": "players", "column": "ab", "minimum": 30},
                {"role": "qualified_pitchers", "entity": "players", "column": "ip", "minimum": 20.0},
            ]
        },
        "metric_map": {
            "team_rank": "composite_score",
            "team_balance_left": "offense_z",
            "team_balance_right": "pitching_z",
            "team_coaching_a": "discipline_z",
            "team_coaching_b": "defense_z",
            "player_power": "ops",
            "player_slug": "hr",
            "player_workload": "ab",
            "pitcher_workload": "ip",
            "pitcher_k": "k",
            "player_volatility_a": "iso",
            "player_volatility_b": "so_rate",
            "team_prevention_a": "era",
            "team_prevention_b": "whip",
        },
        "finding_categories": ["analytical", "elite_talent", "coaching", "fan_first"],
        "storyboard_template": {
            "arc_title": "Who is built to sustain performance and who can swing a series?",
            "audience_tags": ["analyst", "coaching", "fan"],
            "priority_categories": ["fan_first", "analytical", "elite_talent", "coaching"],
        },
        "alias_rules": {
            "teams": {
                "composite_score": ["composite_score"],
                "offense_z": ["offense_z"],
                "pitching_z": ["pitching_z"],
                "discipline_z": ["discipline_z"],
                "defense_z": ["defense_z"],
                "era": ["era"],
                "whip": ["whip"],
            },
            "players": {
                "ab": ["ab"],
                "ops": ["ops"],
                "hr": ["hr"],
                "ip": ["ip"],
                "k": ["k"],
                "iso": ["iso"],
                "so_rate": ["so_rate", "so"],
            },
        },
        "finding_specs": [
            {
                "id": "F01",
                "kind": "team_rank",
                "category": "analytical",
                "entity": "teams",
                "sort_by": "composite_score",
                "title_template": "{team_name} leads the all-around profile",
                "insight_template": "{team_name} ranks first by composite score, signaling balanced strength across offense, pitching, discipline, and defense.",
                "confidence": 0.91,
                "audience_tags": ["analyst", "coaching", "fan"],
                "visual_suggestions": [
                    {"chart_type": "bar", "x": "team_name", "y": "composite_score", "segment": "top_10_teams", "why": "Show overall separation among top teams."},
                    {"chart_type": "radar", "x": "component", "y": "z_score", "segment": "{team_name}", "why": "Show component balance shape for the leader."},
                ],
            },
            {
                "id": "F02",
                "kind": "team_balance",
                "category": "analytical",
                "entity": "teams",
                "left_metric": "offense_z",
                "right_metric": "pitching_z",
                "title_template": "{team_name} shows one of the most balanced profiles",
                "insight_template": "{team_name} has near-matching offense and pitching z-scores, which usually translates to stable game-to-game performance.",
                "confidence": 0.84,
                "audience_tags": ["analyst", "coaching"],
                "visual_suggestions": [
                    {"chart_type": "scatter", "x": "offense_z", "y": "pitching_z", "segment": "all_teams", "why": "Identify balanced teams near the diagonal."},
                    {"chart_type": "dumbbell", "x": "team_name", "y": "offense_vs_pitching", "segment": "top_25_teams", "why": "Highlight internal gap between unit strengths."},
                ],
            },
            {
                "id": "F03",
                "kind": "player_rank",
                "category": "elite_talent",
                "entity": "players",
                "role": "qualified_hitters",
                "sort_by": "ops",
                "title_template": "{player_name} is the top OPS impact bat",
                "insight_template": "{player_name} currently sets the pace in OPS among qualified hitters, indicating elite on-base plus power production.",
                "confidence": 0.89,
                "audience_tags": ["analyst", "fan"],
                "visual_suggestions": [
                    {"chart_type": "bar", "x": "player_name", "y": "ops", "segment": "qualified_hitters_top15", "why": "Rank elite OPS profiles."},
                    {"chart_type": "scatter", "x": "iso", "y": "ops", "segment": "qualified_hitters", "why": "Separate pure power from overall production."},
                ],
            },
            {
                "id": "F04",
                "kind": "player_rank",
                "category": "elite_talent",
                "entity": "players",
                "role": "qualified_hitters",
                "sort_by": "hr",
                "title_template": "{player_name} leads the long-ball race",
                "insight_template": "{player_name} leads qualified hitters in home runs, creating game-changing swing outcomes.",
                "confidence": 0.86,
                "audience_tags": ["fan", "coaching"],
                "visual_suggestions": [
                    {"chart_type": "bar", "x": "player_name", "y": "hr", "segment": "qualified_hitters_top15", "why": "Highlight top home-run threats."},
                    {"chart_type": "scatter", "x": "ab", "y": "hr", "segment": "qualified_hitters", "why": "Compare volume and power conversion."},
                ],
            },
            {
                "id": "F05",
                "kind": "player_rate",
                "category": "elite_talent",
                "entity": "players",
                "role": "qualified_pitchers",
                "numerator": "k",
                "denominator": "ip",
                "scale": 7.0,
                "minimum": 20.0,
                "title_template": "{player_name} is the top bat-missing arm",
                "insight_template": "On a workload-adjusted basis, {player_name} leads qualified pitchers in strikeouts per 7 innings.",
                "confidence": 0.82,
                "audience_tags": ["analyst", "coaching"],
                "visual_suggestions": [
                    {"chart_type": "bar", "x": "player_name", "y": "k_per_7", "segment": "qualified_pitchers_top15", "why": "Rank bat-missing profiles."},
                    {"chart_type": "scatter", "x": "ip", "y": "k_per_7", "segment": "qualified_pitchers", "why": "Separate strikeout dominance from workload."},
                ],
            },
            {
                "id": "F06",
                "kind": "combo",
                "category": "coaching",
                "entity": "teams",
                "metrics": ["discipline_z", "defense_z"],
                "direction": "higher",
                "title_template": "{team_name} profiles as a coaching-efficiency standout",
                "insight_template": "{team_name} combines strong discipline and defensive execution, a common marker of repeatable coaching impact.",
                "confidence": 0.8,
                "audience_tags": ["coaching", "analyst"],
                "visual_suggestions": [
                    {"chart_type": "scatter", "x": "discipline_z", "y": "defense_z", "segment": "all_teams", "why": "Show which teams pair clean ABs with clean defense."},
                    {"chart_type": "bar", "x": "team_name", "y": "coaching_signal", "segment": "top_10_teams", "why": "Rank combined discipline/defense signal."},
                ],
            },
            {
                "id": "F07",
                "kind": "combo",
                "category": "coaching",
                "entity": "teams",
                "metrics": ["era", "whip"],
                "direction": "lower",
                "title_template": "{team_name} owns the strongest run-prevention signal",
                "insight_template": "{team_name} ranks near the top in both ERA and WHIP, suggesting dependable prevention quality.",
                "confidence": 0.85,
                "audience_tags": ["coaching", "fan"],
                "visual_suggestions": [
                    {"chart_type": "scatter", "x": "whip", "y": "era", "segment": "all_teams", "why": "Locate true run-prevention outliers."},
                    {"chart_type": "bar", "x": "team_name", "y": "run_prevention_index", "segment": "top_10_teams", "why": "Translate prevention edge into fan-facing ranking."},
                ],
            },
            {
                "id": "F08",
                "kind": "top_race",
                "category": "fan_first",
                "entity": "teams",
                "rank_metric": "composite_rank",
                "top_n": 5,
                "ascending": True,
                "title_template": "Top-5 race is primed for fan-facing weekly drama",
                "insight_template": "The top of the board is tight enough to produce meaningful weekly movement and marquee matchups.",
                "confidence": 0.77,
                "audience_tags": ["fan", "analyst"],
                "visual_suggestions": [
                    {"chart_type": "line", "x": "week_or_run_date", "y": "composite_rank", "segment": "top_5_teams", "why": "Track volatility over updates."},
                    {"chart_type": "bar", "x": "team_name", "y": "composite_score", "segment": "top_5_teams", "why": "Show current race separation."},
                ],
            },
            {
                "id": "F09",
                "kind": "combo",
                "category": "fan_first",
                "entity": "players",
                "role": "qualified_hitters",
                "metrics": ["iso", "so_rate"],
                "direction": "higher",
                "title_template": "{player_name} is a classic high-variance watch",
                "insight_template": "{player_name} combines loud power indicators with swing-and-miss risk, producing volatile but exciting outcomes.",
                "confidence": 0.73,
                "audience_tags": ["fan", "coaching"],
                "visual_suggestions": [
                    {"chart_type": "scatter", "x": "iso", "y": "so_rate", "segment": "qualified_hitters", "why": "Highlight volatility profiles."},
                    {"chart_type": "hexbin", "x": "iso", "y": "ops", "segment": "qualified_hitters", "why": "Find explosive vs stable hitters."},
                ],
            },
        ],
    },
    "basketball": {
        "name": "basketball",
        "sport": "basketball",
        "entity_names": {"team": "team", "player": "player", "game": "game"},
        "required_files": ["teams.csv", "players.csv"],
        "thresholds": {
            "qualification_rules": [
                {"role": "qualified_scorers", "entity": "players", "column": "minutes", "minimum": 10.0},
                {"role": "qualified_rotation", "entity": "players", "column": "minutes", "minimum": 15.0},
            ]
        },
        "metric_map": {
            "team_rank": "net_rating",
            "team_balance_left": "off_rating",
            "team_balance_right": "def_rating",
            "team_coaching_a": "assist_rate",
            "team_coaching_b": "turnover_rate",
            "player_power": "points",
            "player_slug": "three_pointers",
            "player_workload": "minutes",
            "pitcher_workload": "minutes",
            "pitcher_k": "steals",
            "player_volatility_a": "usage_rate",
            "player_volatility_b": "turnover_rate",
            "team_prevention_a": "def_rating",
            "team_prevention_b": "opp_fg_pct",
        },
        "finding_categories": ["analytical", "elite_talent", "coaching", "fan_first"],
        "storyboard_template": {
            "arc_title": "Who controls the game when the pace gets high?",
            "audience_tags": ["analyst", "coaching", "fan"],
            "priority_categories": ["fan_first", "analytical", "elite_talent", "coaching"],
        },
        "alias_rules": {
            "teams": {
                "net_rating": ["net_rating", "rating"],
                "off_rating": ["off_rating", "ortg", "offense_rating"],
                "def_rating": ["def_rating", "drtg", "defense_rating"],
                "assist_rate": ["assist_rate", "ast_rate"],
                "turnover_rate": ["turnover_rate", "to_rate"],
                "opp_fg_pct": ["opp_fg_pct", "opp_fg", "opponent_fg_pct"],
            },
            "players": {
                "minutes": ["minutes", "min", "mpg"],
                "points": ["points", "pts"],
                "assists": ["assists", "ast"],
                "rebounds": ["rebounds", "reb"],
                "usage_rate": ["usage_rate", "usg_rate"],
                "turnover_rate": ["turnover_rate", "tov_rate"],
                "three_pointers": ["three_pointers", "3pm", "threes"],
                "steals": ["steals", "stl"],
            },
        },
        "finding_specs": [
            {
                "id": "B01",
                "kind": "team_rank",
                "category": "analytical",
                "entity": "teams",
                "sort_by": "net_rating",
                "title_template": "{team_name} leads the net-rating board",
                "insight_template": "{team_name} sits atop the efficiency margin, which is usually the cleanest summary of team strength.",
                "confidence": 0.9,
                "audience_tags": ["analyst", "fan"],
                "visual_suggestions": [
                    {"chart_type": "bar", "x": "team_name", "y": "net_rating", "segment": "top_10_teams", "why": "Show efficiency separation."},
                    {"chart_type": "scatter", "x": "off_rating", "y": "def_rating", "segment": "all_teams", "why": "Show balance between scoring and prevention."},
                ],
            },
            {
                "id": "B02",
                "kind": "team_balance",
                "category": "analytical",
                "entity": "teams",
                "left_metric": "off_rating",
                "right_metric": "def_rating",
                "title_template": "{team_name} shows one of the most balanced profiles",
                "insight_template": "{team_name} has tight offensive and defensive efficiency, a sign of portable winning form.",
                "confidence": 0.84,
                "audience_tags": ["analyst", "coaching"],
                "visual_suggestions": [
                    {"chart_type": "scatter", "x": "off_rating", "y": "def_rating", "segment": "all_teams", "why": "Locate balanced teams near the diagonal."},
                    {"chart_type": "dumbbell", "x": "team_name", "y": "offense_vs_defense", "segment": "top_25_teams", "why": "Highlight efficiency gap by team."},
                ],
            },
            {
                "id": "B03",
                "kind": "player_rank",
                "category": "elite_talent",
                "entity": "players",
                "role": "qualified_scorers",
                "sort_by": "points",
                "title_template": "{player_name} is the top scoring engine",
                "insight_template": "{player_name} leads the qualified player pool in points, giving the offense a true primary creator.",
                "confidence": 0.89,
                "audience_tags": ["analyst", "fan"],
                "visual_suggestions": [
                    {"chart_type": "bar", "x": "player_name", "y": "points", "segment": "qualified_players_top15", "why": "Rank top scorers."},
                    {"chart_type": "scatter", "x": "minutes", "y": "points", "segment": "qualified_players", "why": "Compare workload to scoring output."},
                ],
            },
            {
                "id": "B04",
                "kind": "player_rank",
                "category": "elite_talent",
                "entity": "players",
                "role": "qualified_rotation",
                "sort_by": "assists",
                "title_template": "{player_name} drives the table-setting role",
                "insight_template": "{player_name} ranks at the top in assists among rotation players, signaling reliable creation for teammates.",
                "confidence": 0.83,
                "audience_tags": ["coaching", "fan"],
                "visual_suggestions": [
                    {"chart_type": "bar", "x": "player_name", "y": "assists", "segment": "qualified_rotation_top15", "why": "Highlight playmakers."},
                    {"chart_type": "scatter", "x": "usage_rate", "y": "assists", "segment": "qualified_rotation", "why": "Separate creators from usage-driven scorers."},
                ],
            },
            {
                "id": "B05",
                "kind": "player_rate",
                "category": "elite_talent",
                "entity": "players",
                "role": "qualified_rotation",
                "numerator": "points",
                "denominator": "minutes",
                "scale": 1.0,
                "title_template": "{player_name} creates points efficiently",
                "insight_template": "{player_name} is among the best point-per-minute producers, which is a strong translation signal across lineup contexts.",
                "confidence": 0.8,
                "audience_tags": ["analyst", "coaching"],
                "visual_suggestions": [
                    {"chart_type": "bar", "x": "player_name", "y": "points_per_minute", "segment": "qualified_rotation_top15", "why": "Rank scoring efficiency."},
                    {"chart_type": "scatter", "x": "minutes", "y": "points_per_minute", "segment": "qualified_rotation", "why": "Show efficient volume players."},
                ],
            },
            {
                "id": "B06",
                "kind": "combo",
                "category": "coaching",
                "entity": "teams",
                "metrics": ["assist_rate", "turnover_rate"],
                "direction": "higher",
                "title_template": "{team_name} shows the cleanest playmaking profile",
                "insight_template": "{team_name} pairs strong assist creation with careful ball control, a classic coaching efficiency signal.",
                "confidence": 0.79,
                "audience_tags": ["coaching", "analyst"],
                "visual_suggestions": [
                    {"chart_type": "scatter", "x": "assist_rate", "y": "turnover_rate", "segment": "all_teams", "why": "Identify clean offensive systems."},
                    {"chart_type": "bar", "x": "team_name", "y": "playmaking_signal", "segment": "top_10_teams", "why": "Rank offensive organization."},
                ],
            },
            {
                "id": "B07",
                "kind": "combo",
                "category": "coaching",
                "entity": "teams",
                "metrics": ["def_rating", "opp_fg_pct"],
                "direction": "lower",
                "title_template": "{team_name} is the strongest prevention profile",
                "insight_template": "{team_name} combines a strong defensive rating with opponent shot suppression, a dependable indicator of structured defense.",
                "confidence": 0.82,
                "audience_tags": ["coaching", "fan"],
                "visual_suggestions": [
                    {"chart_type": "scatter", "x": "opp_fg_pct", "y": "def_rating", "segment": "all_teams", "why": "Locate prevention outliers."},
                    {"chart_type": "bar", "x": "team_name", "y": "defensive_signal", "segment": "top_10_teams", "why": "Show the best defensive systems."},
                ],
            },
            {
                "id": "B08",
                "kind": "top_race",
                "category": "fan_first",
                "entity": "teams",
                "rank_metric": "net_rating",
                "top_n": 5,
                "ascending": False,
                "title_template": "Top-5 race is ready for weekly movement",
                "insight_template": "The best teams are close enough together that one strong week can materially reshuffle the table.",
                "confidence": 0.76,
                "audience_tags": ["fan", "analyst"],
                "visual_suggestions": [
                    {"chart_type": "line", "x": "week_or_run_date", "y": "net_rating", "segment": "top_5_teams", "why": "Track movement over time."},
                    {"chart_type": "bar", "x": "team_name", "y": "net_rating", "segment": "top_5_teams", "why": "Show current separation."},
                ],
            },
        ],
    },
}


def _load_profile_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_profile(profile_name: str | None, *, repo_root: Path | None = None) -> DomainProfile:
    if profile_name and profile_name not in {"auto", ""}:
        candidate = Path(profile_name)
        if candidate.exists():
            payload = _load_profile_payload(candidate)
            return DomainProfile(**payload)

        key = profile_name.lower()
        if key in BUILTIN_PROFILES:
            return DomainProfile(**deepcopy(BUILTIN_PROFILES[key]))

    return DomainProfile(**deepcopy(BUILTIN_PROFILES["generic"]))


def infer_profile_name(headers: set[str]) -> str:
    lowered = {h.lower() for h in headers}
    scores = {
        "softball": len(lowered & {"ab", "ops", "iso", "hr", "ip", "era", "whip", "bb_k_ratio", "k_per_7"}),
        "basketball": len(lowered & {"pts", "points", "reb", "rebounds", "ast", "assists", "min", "minutes", "ts_pct", "usage_rate", "net_rating", "off_rating", "def_rating"}),
    }
    best = max(scores.items(), key=lambda item: item[1])
    if best[1] == 0:
        return "generic"
    if scores["basketball"] == scores["softball"]:
        return "generic"
    return best[0]


def builtin_profile_names() -> list[str]:
    return sorted(BUILTIN_PROFILES.keys())


def profile_to_dict(profile: DomainProfile) -> dict[str, Any]:
    return asdict(profile)
