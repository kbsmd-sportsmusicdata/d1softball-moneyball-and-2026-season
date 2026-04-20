from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import EDARunConfig
from .contracts import DatasetBundle
from .metrics import detect_data_root, find_latest_processed_dataset, infer_profile_from_paths


class DatasetResolver:
    """Path-based resolver with hooks for future cross-repo adapters."""

    @staticmethod
    def resolve(teams_path: Path | None, players_path: Path | None) -> tuple[Path, Path, str]:
        bundle = resolve_bundle(EDARunConfig(teams_path=teams_path, players_path=players_path))
        return bundle.teams_path, bundle.players_path, bundle.resolution_mode

    @staticmethod
    def resolve_bundle(config: EDARunConfig) -> DatasetBundle:
        return resolve_bundle(config)


def _resolve_relative(path_value: str, base_dir: Path) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def _read_manifest(manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"Manifest must be a JSON object: {manifest_path}")
    return payload


def _find_auto_manifest(data_root: Path) -> Path | None:
    candidates = [
        data_root / "eda_agent.manifest.json",
        data_root / "examples" / "eda_agent.manifest.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _common_source_root(*paths: Path | None) -> Path:
    resolved = [path.resolve() for path in paths if path is not None]
    if not resolved:
        return Path.cwd()
    common = Path(resolved[0])
    for path in resolved[1:]:
        while common not in path.parents and common != path:
            common = common.parent
    if common.is_file():
        return common.parent
    return common


def _resolve_manifest_bundle(manifest_path: Path, config: EDARunConfig) -> DatasetBundle:
    manifest_path = manifest_path.resolve()
    payload = _read_manifest(manifest_path)
    manifest_root = Path(payload.get("source_root", manifest_path.parent)).resolve()
    teams_path = _resolve_relative(str(payload["teams_path"]), manifest_root)
    players_path = _resolve_relative(str(payload["players_path"]), manifest_root)
    profile_name = str(payload.get("profile_name", config.profile_name or "auto"))
    if profile_name == "auto":
        profile_name = infer_profile_from_paths(teams_path, players_path)
    extra_files = {
        str(key): _resolve_relative(str(value), manifest_root)
        for key, value in payload.get("extra_files", {}).items()
        if isinstance(value, (str, Path))
    }
    return DatasetBundle(
        source_root=manifest_root,
        teams_path=teams_path,
        players_path=players_path,
        dataset_label=str(payload.get("dataset_label", manifest_root.name)),
        dataset_version=payload.get("dataset_version"),
        profile_name=profile_name,
        resolution_mode="manifest",
        manifest_path=manifest_path,
        extra_files=extra_files,
    )


def resolve_bundle(config: EDARunConfig) -> DatasetBundle:
    if config.teams_path and config.players_path:
        source_root = config.repo_root or _common_source_root(config.teams_path, config.players_path)
        profile_name = config.profile_name
        if profile_name == "auto":
            profile_name = infer_profile_from_paths(config.teams_path, config.players_path)
        return DatasetBundle(
            source_root=source_root,
            teams_path=config.teams_path,
            players_path=config.players_path,
            dataset_label=config.run_label,
            dataset_version=None,
            profile_name=profile_name,
            resolution_mode="explicit",
            manifest_path=None,
        )

    if config.teams_path or config.players_path:
        raise RuntimeError("Provide both --teams-path and --players-path, or neither.")

    data_root = detect_data_root(config.repo_root)
    source_mode = (config.source_mode or "auto").strip().lower()
    if source_mode not in {"auto", "repo_layout", "manifest"}:
        raise RuntimeError(f"Invalid source_mode: {config.source_mode}")

    manifest_path = config.manifest_path
    if source_mode != "repo_layout" and manifest_path is None:
        manifest_path = _find_auto_manifest(data_root)

    if manifest_path is not None and source_mode != "repo_layout":
        return _resolve_manifest_bundle(manifest_path, config)

    if source_mode == "manifest":
        raise RuntimeError(
            "source_mode=manifest but no manifest was found. Provide --manifest or add eda_agent.manifest.json."
        )

    teams_path, players_path, latest_folder = find_latest_processed_dataset(data_root)
    profile_name = config.profile_name
    if profile_name == "auto":
        profile_name = infer_profile_from_paths(teams_path, players_path)
    return DatasetBundle(
        source_root=data_root,
        teams_path=teams_path,
        players_path=players_path,
        dataset_label=latest_folder.name,
        dataset_version=latest_folder.name,
        profile_name=profile_name,
        resolution_mode="latest_processed",
        manifest_path=None,
    )
