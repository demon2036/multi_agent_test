#!/usr/bin/env python3
"""Core launcher logic for agent tasks."""

import io
import subprocess
import time
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from .config import ROOT, LOGS, META_DIR, WORKDIR, SID_RE, get_agent, ensure_dirs
from .prompts import wrap_prompt


def _run_sync_prompts():
    """Run sync_prompts silently (suppress stdout)."""
    try:
        # Import sync_prompts from parent directory
        import sys
        scripts_dir = Path(__file__).parent.parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from sync_prompts import main as sync_prompts_main

        with redirect_stdout(io.StringIO()):
            sync_prompts_main()
    except Exception:
        pass  # Don't fail launch if sync fails


def launch(prompt: str, output_name: str = None, sop_name: str = None) -> dict:
    """
    Launch a new agent task.

    Key design: Always pre-generate session_id (UUID) for log file naming.
    This fixes Windows compatibility where rename fails on open files.
    For codex, we still parse its internal session_id for resume capability.

    Args:
        prompt: Task prompt
        output_name: Answer file name (without .md)
        sop_name: SOP file name (without .md)

    Returns:
        dict with session_id, pid, log path, and optionally answer/sop paths
    """
    # Step 1: Sync prompts before launch
    _run_sync_prompts()

    # Step 2: Ensure directories exist
    ensure_dirs()

    agent = get_agent()
    wrapped = wrap_prompt(prompt, output_name, sop_name)

    # Step 3: Pre-generate session_id (fixes Windows rename issue)
    our_sid = str(uuid.uuid4())
    log_file = LOGS / f"{our_sid}.log"
    pid_file = META_DIR / f"{our_sid}.pid"

    # Step 4: Launch subprocess - write directly to final log file
    with open(log_file, "w") as f:
        proc = subprocess.Popen(
            agent["launch_cmd"](our_sid, wrapped),
            stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
            cwd=WORKDIR,
        )

    # Step 5: For codex, parse real session_id from output (for resume)
    # We wait up to 10 seconds but DON'T rename the log file
    if agent["sid_from_output"]:
        codex_sid = None
        for _ in range(40):
            time.sleep(0.25)
            try:
                content = log_file.read_text(encoding="utf-8", errors="ignore")
                m = SID_RE.search(content)
            except FileNotFoundError:
                m = None
            if m:
                codex_sid = m.group(1)
                break

        # Store codex's real session_id in a separate file for resume
        if codex_sid:
            codex_sid_file = META_DIR / f"{our_sid}.codex_sid"
            codex_sid_file.write_text(codex_sid)

    pid_file.write_text(str(proc.pid))

    # Build result
    result = {
        "session_id": our_sid,
        "pid": proc.pid,
        "log": str(log_file.relative_to(ROOT))
    }
    if output_name:
        result["answer"] = f"workdir/answers/{output_name}.md"
    if sop_name:
        result["sop"] = f"workdir/sop/{sop_name}.md"

    return result


def resume(session_id: str, prompt: str, output_name: str = None, sop_name: str = None) -> dict:
    """
    Resume an existing session.

    Args:
        session_id: Session ID to resume (our UUID, not codex's internal sid)
        prompt: New prompt for continuation
        output_name: Answer file name
        sop_name: SOP file name

    Returns:
        dict with session_id, pid, log path, and optionally answer/sop paths
    """
    # Sync prompts on resume too
    _run_sync_prompts()
    ensure_dirs()

    agent = get_agent()
    log_file = LOGS / f"{session_id}.log"
    pid_file = META_DIR / f"{session_id}.pid"

    # For codex, use the real codex session_id for resume
    resume_sid = session_id
    if agent["sid_from_output"]:
        codex_sid_file = META_DIR / f"{session_id}.codex_sid"
        if codex_sid_file.exists():
            resume_sid = codex_sid_file.read_text().strip()

    with open(log_file, "a") as f:
        f.write("\n\n# --- resume ---\n\n")
        proc = subprocess.Popen(
            agent["resume_cmd"](resume_sid, wrap_prompt(prompt, output_name, sop_name)),
            stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
            cwd=WORKDIR,
        )

    pid_file.write_text(str(proc.pid))

    result = {
        "session_id": session_id,
        "pid": proc.pid,
        "log": str(log_file.relative_to(ROOT))
    }
    if output_name:
        result["answer"] = f"workdir/answers/{output_name}.md"
    if sop_name:
        result["sop"] = f"workdir/sop/{sop_name}.md"

    return result
