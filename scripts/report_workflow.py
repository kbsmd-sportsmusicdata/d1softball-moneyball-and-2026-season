from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

ROOT = Path(__file__).resolve().parents[1]
REPORT_SCRIPT = ROOT / "scripts" / "build_d1softball_manual_report.py"
SYNC_SCRIPT = ROOT / "scripts" / "sync_manual_report_bundle.py"
REPORT_DIR = ROOT / "reports" / "d1softball_manual_april2026"
HANDOFF_ROOT = ROOT / "handoffs" / "d1softball_manual_april2026"

HandoffMode = Literal["none", "related", "full"]

RELATED_SOURCE_FILES = [
    "scripts/build_d1softball_manual_report.py",
    "scripts/manual_notebook.py",
    "scripts/sync_manual_report_bundle.py",
    "scripts/report_workflow.py",
    "dashboard/app/report/page.tsx",
    "dashboard/lib/report.ts",
    "dashboard/lib/types.ts",
    "dashboard/app/layout.tsx",
    "dashboard/app/globals.css",
    "dashboard/package.json",
    "Makefile",
    "README.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the manual report and optionally emit a handoff bundle.")
    parser.add_argument(
        "--handoff-mode",
        choices=["prompt", "none", "related", "full"],
        default="prompt",
        help="Choose whether to generate a handoff bundle and how broad the file manifest should be.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_subprocess([sys.executable, "-B", str(REPORT_SCRIPT)])
    run_subprocess([sys.executable, "-B", str(SYNC_SCRIPT)])

    mode = resolve_handoff_mode(args.handoff_mode)
    if mode == "none":
        print("handoff bundle skipped")
        return

    bundle_dir, zip_path = create_handoff_bundle(mode)
    print(f"handoff bundle written to {bundle_dir}")
    print(f"handoff zip written to {zip_path}")


def run_subprocess(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


def resolve_handoff_mode(mode: str) -> HandoffMode:
    env_value = os.environ.get("REPORT_HANDOFF_MODE", "").strip().lower()
    if env_value in {"none", "related", "full"}:
        return env_value  # type: ignore[return-value]

    if mode in {"none", "related", "full"}:
        return mode  # type: ignore[return-value]

    if not sys.stdin.isatty():
        return "none"

    print()
    print("Generate a handoff bundle for this run?")
    print("  [r] Related files + report bundle (recommended)")
    print("  [f] Full repo manifest + report bundle")
    print("  [n] No handoff bundle")
    response = input("Choose [r/f/n] (default: r): ").strip().lower()
    if response in {"n", "no"}:
        return "none"
    if response in {"f", "full"}:
        return "full"
    return "related"


def create_handoff_bundle(mode: HandoffMode) -> tuple[Path, Path]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    bundle_dir = HANDOFF_ROOT / timestamp
    report_copy_dir = bundle_dir / "report_bundle"
    report_copy_dir.mkdir(parents=True, exist_ok=True)

    if REPORT_DIR.exists():
        copy_tree(REPORT_DIR, report_copy_dir)
    else:
        raise FileNotFoundError(f"Report directory not found: {REPORT_DIR}")

    source_paths = collect_source_paths(mode)
    manifest = build_manifest(mode, source_paths, report_copy_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "file_manifest.json").write_text(manifest["json"])
    (bundle_dir / "file_manifest.md").write_text(manifest["markdown"])
    (bundle_dir / "handoff.md").write_text(build_handoff_doc(bundle_dir, mode, source_paths, report_copy_dir))
    zip_path = zip_handoff_bundle(bundle_dir)

    return bundle_dir, zip_path


def copy_tree(source: Path, destination: Path) -> None:
    for src in source.rglob("*"):
        if not src.is_file():
            continue
        dest = destination / src.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def zip_handoff_bundle(bundle_dir: Path) -> Path:
    zip_path = bundle_dir.with_suffix('.zip')
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, mode='w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle_dir.rglob('*')):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(bundle_dir.parent))

    return zip_path


def collect_source_paths(mode: HandoffMode) -> list[Path]:
    if mode == "full":
        return collect_tracked_paths()
    return [ROOT / rel for rel in RELATED_SOURCE_FILES if (ROOT / rel).exists()]


def collect_tracked_paths() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        paths = [ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [path for path in paths if path.exists()]
    except Exception:
        paths: list[Path] = []
        for path in ROOT.rglob("*"):
            if path.is_file() and ".git" not in path.parts and "node_modules" not in path.parts and ".next" not in path.parts:
                paths.append(path)
        return paths


def build_manifest(mode: HandoffMode, source_paths: Iterable[Path], report_copy_dir: Path) -> dict[str, str]:
    records: list[dict[str, object]] = []

    for path in sorted(report_copy_dir.rglob("*")):
        if path.is_file():
            records.append(
                {
                    "kind": "report_bundle",
                    "path": str(path.relative_to(report_copy_dir.parent)),
                    "size_bytes": path.stat().st_size,
                }
            )

    for path in source_paths:
        records.append(
            {
                "kind": "source",
                "path": str(path.relative_to(ROOT)),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }
        )

    lines = [
        "# File Manifest",
        "",
        f"- Mode: `{mode}`",
        f"- Generated: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Report bundle: `{report_copy_dir}`",
        "",
    ]
    for record in records:
        lines.append(f"- `{record['kind']}`: `{record['path']}` ({record['size_bytes']} bytes)")

    return {
        "json": _json_dumps({
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "report_bundle": str(report_copy_dir),
            "records": records,
        }),
        "markdown": "\n".join(lines),
    }


def build_handoff_doc(bundle_dir: Path, mode: HandoffMode, source_paths: Iterable[Path], report_copy_dir: Path) -> str:
    related_files = [str(path.relative_to(ROOT)) for path in source_paths]
    report_md = report_copy_dir / "report.md"
    report_data = report_copy_dir / "report_data.json"
    report_metadata = report_copy_dir / "report_metadata.json"
    report_notebook = report_copy_dir / "notebook.html"
    figures_dir = report_copy_dir / "figures"

    lines = [
        "# D1 Softball Manual Workbook Handoff",
        "",
        "This bundle is designed for copy/paste into another AI tool or design/build workflow.",
        "",
        "## What this contains",
        "",
        f"- Hand-off mode: `{mode}`",
        f"- Bundle folder: `{bundle_dir}`",
        f"- Zip archive: `{bundle_dir.with_suffix('.zip')}`",
        f"- Report folder: `{report_copy_dir}`",
        f"- Report markdown: `{report_md}`",
        f"- Report data JSON: `{report_data}`",
        f"- Report metadata JSON: `{report_metadata}`",
        f"- Notebook HTML: `{report_notebook}`",
        f"- Figures folder: `{figures_dir}`",
        "",
        "## Why it matters",
        "",
        "- The report page is now self-contained for static deployment.",
        "- The handoff package includes the live report artifacts plus a file manifest.",
        "- The manifest can be dropped into another AI tool as a context bundle for future analysis or redesign.",
        "",
        "## Related source files",
        "",
    ]
    for rel in related_files:
        lines.append(f"- `{rel}`")

    lines.extend(
        [
            "",
            "## Rebuild commands",
            "",
            "```bash",
            "make report",
            "cd dashboard && npm run build",
            "```",
            "",
            "## Suggested next analysis prompts",
            "",
            "- Extend the report into a dedicated social asset pack.",
            "- Add deeper season trend analysis and schedule-adjusted residual models.",
            "- Build a Figma-ready visual concept for the report page.",
        ]
    )
    return "\n".join(lines)


def _json_dumps(obj: object) -> str:
    import json

    return json.dumps(obj, indent=2)


if __name__ == "__main__":
    main()
