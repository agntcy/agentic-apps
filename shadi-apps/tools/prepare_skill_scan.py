#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "evals",
    "tests",
}

EXCLUDED_FILES = {
    ".DS_Store",
}


def should_skip(path: Path, source_root: Path) -> bool:
    relative = path.relative_to(source_root)
    for part in relative.parts:
        if part in EXCLUDED_DIRS:
            return True
    return path.name in EXCLUDED_FILES


def copy_skill_tree(source_root: Path, dest_root: Path) -> tuple[int, int]:
    copied_files = 0
    copied_dirs = 0

    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    for path in sorted(source_root.rglob("*")):
        if should_skip(path, source_root):
            continue

        relative = path.relative_to(source_root)
        destination = dest_root / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            copied_dirs += 1
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied_files += 1

    return copied_dirs, copied_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a sanitized skill directory for external scanners."
    )
    parser.add_argument("--source", required=True, help="Source skill directory")
    parser.add_argument("--dest", required=True, help="Destination directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = Path(args.source).resolve()
    dest_root = Path(args.dest).resolve()

    if not source_root.exists() or not source_root.is_dir():
        raise SystemExit(f"Source skill directory not found: {source_root}")

    copied_dirs, copied_files = copy_skill_tree(source_root, dest_root)
    print(
        f"Prepared sanitized skill tree at {dest_root} "
        f"({copied_dirs} directories, {copied_files} files)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())