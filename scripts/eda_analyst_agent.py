from __future__ import annotations

from eda_agent import (
    DatasetResolver,
    EDARunConfig,
    Finding,
    REQUIRED_FINDING_CATEGORIES,
    StoryboardStep,
    VisualSuggestion,
    build_findings,
    build_storyboard,
    infer_profile_name,
    load_profile,
    main,
    polish_with_llm,
    run_agent,
)
from eda_agent.profiles import load_profile
from eda_agent.runners import _build_findings as _v2_build_findings, _build_storyboard as _v2_build_storyboard, _polish_with_llm as _v2_polish_with_llm

__all__ = [
    "DatasetResolver",
    "EDARunConfig",
    "Finding",
    "REQUIRED_FINDING_CATEGORIES",
    "StoryboardStep",
    "VisualSuggestion",
    "build_findings",
    "build_storyboard",
    "infer_profile_name",
    "load_profile",
    "polish_with_llm",
    "run_agent",
]


def _build_findings(teams, players, min_player_ab=30, min_player_ip=20.0, max_findings=8):
    profile = load_profile("softball")
    config = EDARunConfig(min_player_ab=min_player_ab, min_player_ip=min_player_ip, max_findings=max_findings)
    return _v2_build_findings(teams, players, profile, max_findings=max_findings)


def _build_storyboard(findings):
    profile = load_profile("softball")
    return _v2_build_storyboard(findings, profile)


def _polish_with_llm(findings, model="gpt-4o-mini"):
    return _v2_polish_with_llm(findings, model)


if __name__ == "__main__":
    main()
