from __future__ import annotations

from pathlib import Path

from eda_agent.profiles import builtin_profile_names, load_profile


def test_builtin_profiles_load():
    names = builtin_profile_names()
    assert "softball" in names
    assert "basketball" in names
    softball = load_profile("softball")
    basketball = load_profile("basketball")
    assert softball.sport == "softball"
    assert basketball.sport == "basketball"
    assert softball.finding_categories == basketball.finding_categories


def test_profile_can_load_from_json_path():
    profile = load_profile(Path("examples/profiles/softball.json"))
    assert profile.name == "softball"
    assert profile.thresholds["qualification_rules"]
    assert profile.finding_specs
