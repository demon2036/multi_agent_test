#!/usr/bin/env python3
"""
Sync prompt files from prompts/ directory to target locations.

- prompts/MASTER.md -> root/{AGENTS.md, GEMINI.md, CLAUDE.md}
- prompts/WORKER.md -> workdir/{AGENTS.md, GEMINI.md, CLAUDE.md}
"""

import shutil
from pathlib import Path


def main():
    # Get project root (parent of scripts/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    prompts_dir = project_root / "prompts"
    workdir = project_root / "workdir"

    # Source files
    master_src = prompts_dir / "MASTER.md"
    worker_src = prompts_dir / "WORKER.md"

    # Target filenames
    target_names = ["AGENTS.md", "GEMINI.md", "CLAUDE.md"]

    # Ensure workdir exists
    workdir.mkdir(exist_ok=True)

    # Copy MASTER.md to root
    if master_src.exists():
        for name in target_names:
            dst = project_root / name
            shutil.copy2(master_src, dst)
            print(f"Copied {master_src} -> {dst}")
    else:
        print(f"Warning: {master_src} not found")

    # Copy WORKER.md to workdir
    if worker_src.exists():
        for name in target_names:
            dst = workdir / name
            shutil.copy2(worker_src, dst)
            print(f"Copied {worker_src} -> {dst}")
    else:
        print(f"Warning: {worker_src} not found")

    print("\nSync complete!")


if __name__ == "__main__":
    main()
