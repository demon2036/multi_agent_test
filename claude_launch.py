#!/usr/bin/env python3
"""启动claude后台任务，返回session_id（支持resume）"""
import subprocess, sys, uuid, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

PROMPT_PREFIX = """\
输出要求（只约束最终回答）：
- 不要输出思维链/内心推理。
- 最终回答必须"详细且贴合任务类型"，不要为了格式硬凑"建议/下一步"。
- 如果是代码解析/讲解：必须结合代码逐段解释（关键函数/关键分支/数据流/边界条件），必要时引用少量关键片段（短片段即可）。
- 如果是复杂任务且改了多处代码：必须逐文件逐点说明"改了哪里、为什么改、改前是什么行为、改后是什么行为"，并尽可能给出充分的 before/after 代码片段或直接贴出完整 diff（越多越好）。
- 如果只改了很小的东西：也要解释清楚改动的影响范围与行为变化。
"""

def _wrap_prompt(user_prompt: str) -> str:
    return f"{PROMPT_PREFIX}\n\n用户任务：\n{user_prompt}\n"

def launch(prompt: str) -> dict:
    session_id = str(uuid.uuid4())
    log_file = LOGS / f"{session_id}.log"
    pid_file = LOGS / f"{session_id}.pid"

    with open(log_file, "w") as f:
        proc = subprocess.Popen(
            ["claude", "-p", _wrap_prompt(prompt), "--session-id", session_id, "--dangerously-skip-permissions"],
            stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    pid_file.write_text(str(proc.pid))
    return {"session_id": session_id, "pid": proc.pid, "log": str(log_file.relative_to(ROOT))}

def resume(session_id: str, prompt: str) -> dict:
    log_file = LOGS / f"{session_id}.log"
    pid_file = LOGS / f"{session_id}.pid"

    with open(log_file, "a") as f:
        f.write("\n\n# --- resume ---\n\n")
        proc = subprocess.Popen(
            ["claude", "-p", _wrap_prompt(prompt), "--resume", session_id, "--dangerously-skip-permissions"],
            stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    pid_file.write_text(str(proc.pid))
    return {"session_id": session_id, "pid": proc.pid, "log": str(log_file.relative_to(ROOT))}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python claude_launch.py "prompt"')
        print('   or: python claude_launch.py --resume <session_id> "prompt"')
        sys.exit(1)
    if sys.argv[1] == "--resume":
        if len(sys.argv) < 4:
            print('Usage: python claude_launch.py --resume <session_id> "prompt"')
            sys.exit(1)
        print(json.dumps(resume(sys.argv[2], sys.argv[3])))
    else:
        print(json.dumps(launch(sys.argv[1])))
