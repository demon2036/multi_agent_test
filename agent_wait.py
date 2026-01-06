#!/usr/bin/env python3
"""等待任意session完成，返回所有session状态"""
import sys, time, os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
MAX_WAIT = 600  # 10分钟

def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def get_status(session_id: str) -> dict:
    pid_file = LOGS / f"{session_id}.pid"
    log_file = LOGS / f"{session_id}.log"

    if not pid_file.exists():
        return {"status": "not_found", "log": str(log_file.relative_to(ROOT))}

    pid = int(pid_file.read_text().strip())
    status = "running" if pid_alive(pid) else "done"
    return {"status": status, "pid": pid, "log": str(log_file.relative_to(ROOT))}

def wait(session_ids: list[str], max_wait: int = MAX_WAIT) -> dict:
    start = time.time()

    while time.time() - start < max_wait:
        result = {}
        has_done = False

        for sid in session_ids:
            info = get_status(sid)
            result[sid] = info
            if info["status"] == "done":
                has_done = True

        if has_done:
            return result

        time.sleep(2)

    # 超时，返回当前状态
    return {sid: get_status(sid) for sid in session_ids}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python agent_wait.py <session_id1> [session_id2] ...')
        sys.exit(1)
    print(json.dumps(wait(sys.argv[1:]), indent=2))
