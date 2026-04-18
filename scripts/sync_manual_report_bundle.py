from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "reports" / "d1softball_manual_april2026"
DEFAULT_TARGET = ROOT / "dashboard" / "public" / "reports" / "d1softball_manual_april2026"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy the manual D1Softball report bundle into dashboard/public.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.source_dir.exists():
        raise FileNotFoundError(f"Source report bundle not found: {args.source_dir}")

    if args.target_dir.exists():
        shutil.rmtree(args.target_dir)
    args.target_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for src in args.source_dir.rglob("*"):
        if not src.is_file():
            continue
        dest = args.target_dir / src.relative_to(args.source_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1

    print(f"copied {copied} files to {args.target_dir}")


if __name__ == "__main__":
    main()
