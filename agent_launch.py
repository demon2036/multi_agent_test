#!/usr/bin/env python3
"""启动codex后台任务，返回session_id（支持resume）"""
import subprocess, sys, re, time, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

_SID_RE = re.compile(r"session id: ([a-f0-9-]+)")

PROMPT_PREFIX = """\
输出要求（只约束最终回答）：
- 不要输出思维链/内心推理。
- 最终回答必须“详细且贴合任务类型”，不要为了格式硬凑“建议/下一步”。
- 如果是代码解析/讲解：必须结合代码逐段解释（关键函数/关键分支/数据流/边界条件），必要时引用少量关键片段（短片段即可）。
- 如果是复杂任务且改了多处代码：必须逐文件逐点说明“改了哪里、为什么改、改前是什么行为、改后是什么行为”，并尽可能给出充分的 before/after 代码片段或直接贴出完整 diff（越多越好）。
- 如果只改了很小的东西：也要解释清楚改动的影响范围与行为变化。
"""

def _wrap_prompt(user_prompt: str) -> str:
    return f"{PROMPT_PREFIX}\n\n用户任务：\n{user_prompt}\n"

def launch(prompt: str) -> dict:
    tmp_log = LOGS / f"tmp_{int(time.time()*1000)}.log"

    with open(tmp_log, "w") as f:
        proc = subprocess.Popen(
            ["codex", "-a", "never", "exec", "-s", "danger-full-access", "--skip-git-repo-check", _wrap_prompt(prompt)],
            stdout=f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    session_id = None
    for _ in range(40):
        time.sleep(0.25)
        try:
            m = _SID_RE.search(tmp_log.read_text(encoding="utf-8", errors="ignore"))
        except FileNotFoundError:
            m = None
        if m:
            session_id = m.group(1)
            break

    if not session_id:
        return {"session_id": None, "pid": proc.pid, "log": str(tmp_log.relative_to(ROOT))}

    log_file = LOGS / f"{session_id}.log"
    pid_file = LOGS / f"{session_id}.pid"
    tmp_log.rename(log_file)
    pid_file.write_text(str(proc.pid))
    return {"session_id": session_id, "pid": proc.pid, "log": str(log_file.relative_to(ROOT))}

def resume(session_id: str, prompt: str) -> dict:
    log_file = LOGS / f"{session_id}.log"
    pid_file = LOGS / f"{session_id}.pid"

    with open(log_file, "a") as f:
        f.write("\n\n# --- resume ---\n\n")
        proc = subprocess.Popen(
            ["codex", "-a", "never", "exec", "--skip-git-repo-check", "-s", "danger-full-access", "resume", session_id, _wrap_prompt(prompt)],
            stdout=f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    pid_file.write_text(str(proc.pid))
    return {"session_id": session_id, "pid": proc.pid, "log": str(log_file.relative_to(ROOT))}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python agent_launch.py "prompt"')
        print('   or: python agent_launch.py --resume <session_id> "prompt"')
        sys.exit(1)
    if sys.argv[1] == "--resume":
        if len(sys.argv) < 4:
            print('Usage: python agent_launch.py --resume <session_id> "prompt"')
            sys.exit(1)
        print(json.dumps(resume(sys.argv[2], sys.argv[3])))
    else:
        print(json.dumps(launch(sys.argv[1])))
