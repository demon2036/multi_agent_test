#!/usr/bin/env python3
"""Agent configuration: paths, constants, and agent backend definitions."""

import os
import re
from pathlib import Path

# ============================================================
# Path Configuration
# ============================================================
ROOT = Path(__file__).resolve().parent.parent.parent  # project root
LOGS = ROOT / "logs"
META_DIR = Path("/tmp/agent_meta")  # .pid, .codex_sid 等辅助文件
WORKDIR = ROOT / os.environ.get("WORKER_WORKDIR", "workdir")
ANSWERS_DIR = WORKDIR / "answers"
SOP_DIR = WORKDIR / "sop"

# Worker prompt file path (can override via env var)
WORKER_PROMPT_FILE = os.environ.get("WORKER_PROMPT_FILE", "prompts/WORKER.md")

# Regex for parsing codex session ID from output
SID_RE = re.compile(r"session id: ([a-f0-9-]+)")

# ============================================================
# Agent Backend Definitions
# ============================================================
AGENTS = {
    "codex": {
        "launch_cmd": lambda sid, prompt: [
            "codex", "-a", "never", "exec",
            "-s", "danger-full-access",
            "--skip-git-repo-check", prompt
        ],
        "resume_cmd": lambda sid, prompt: [
            "codex", "-a", "never", "exec", "--skip-git-repo-check",
            "-s", "danger-full-access", "resume", sid, prompt
        ],
        "sid_from_output": True,  # Must parse session_id from output
    },
    "claude": {
        "launch_cmd": lambda sid, prompt: [
            "claude", "-p", prompt, "--session-id", sid,
            "--dangerously-skip-permissions"
        ],
        "resume_cmd": lambda sid, prompt: [
            "claude", "-p", prompt, "--resume", sid,
            "--dangerously-skip-permissions"
        ],
        "sid_from_output": False,  # Uses pre-generated UUID
    },
}


def get_agent():
    """Get current agent backend based on AGENT_TYPE env var."""
    name = os.environ.get("AGENT_TYPE", "codex").lower()
    if name not in AGENTS:
        raise ValueError(f"Unknown AGENT_TYPE: {name}, must be one of {list(AGENTS.keys())}")
    return AGENTS[name]


def ensure_dirs():
    """Create required directories if they don't exist."""
    LOGS.mkdir(exist_ok=True)
    META_DIR.mkdir(exist_ok=True)
    WORKDIR.mkdir(exist_ok=True)
    ANSWERS_DIR.mkdir(exist_ok=True)
    SOP_DIR.mkdir(exist_ok=True)
