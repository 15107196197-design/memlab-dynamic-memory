#!/usr/bin/env python3
"""Build a slim, self-contained bundle for a ModelScope Docker Studio.

The repository is ~2 GB because it keeps experiment databases under ``runs/``.
The public workbench only needs the web shell, the Python packages, the course
data, and the report/archive JSON.  This script copies that subset into a clean
directory so the Docker build context stays small.

Usage:
    python deploy/modelscope/build_bundle.py
    python deploy/modelscope/build_bundle.py --out /tmp/memlab-studio
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT.parent / "modelscope-studio" / "memlab"

DIRS = (
    "memlab",
    "memwb",
    "configs",
    "data",
    "web",
    "reports/experiments",
    "eval/archive",
)
FILES = (
    "server.py",
    "LICENSE",
    "DATA-SOURCE.md",
    "LOCOMO-LICENSE.txt",
)
IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".DS_Store", "*.tmp", "*.log", "._*",
)


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise SystemExit(f"missing bundle input: {src}")
    shutil.copytree(src, dst, ignore=IGNORE, dirs_exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for rel in DIRS:
        copy_tree(ROOT / rel, out / rel)
    for rel in FILES:
        src = ROOT / rel
        if not src.is_file():
            raise SystemExit(f"missing bundle input: {src}")
        shutil.copy2(src, out / rel)
    # eval/archive is enough for the report page; keep the top-level evaluation.
    shutil.copy2(ROOT / "eval" / "results.json", out / "eval" / "results.json")
    shutil.copy2(ROOT / "deploy" / "modelscope" / "Dockerfile", out / "Dockerfile")
    shutil.copy2(ROOT / "deploy" / "modelscope" / "README.md", out / "README.md")
    # Never ship a nested git repository: the destination Studio repo has its
    # own .git and must keep its origin remote.
    if (out / ".git").exists():
        shutil.rmtree(out / ".git")
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"bundle: {out}")
    print(f"files: {sum(1 for p in out.rglob('*') if p.is_file())}")
    print(f"size: {total / 1024 / 1024:.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
