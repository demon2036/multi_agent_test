#!/usr/bin/env python3
"""统一启动器：通过 AGENT_TYPE 环境变量选择 codex 或 claude"""
import subprocess, sys, os, uuid, re, time, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

_SID_RE = re.compile(r"session id: ([a-f0-9-]+)")

# Worker prompt 文件路径，可通过环境变量覆盖
WORKER_PROMPT_FILE = os.environ.get("WORKER_PROMPT_FILE", "prompts/WORKER.md")

PROMPT_PREFIX = """\
输出要求（只约束最终回答）：
- 不要输出思维链/内心推理。
- 最终回答必须"详细且贴合任务类型"，不要为了格式硬凑"建议/下一步"。
- 如果是代码解析/讲解：必须结合代码逐段解释（关键函数/关键分支/数据流/边界条件），必要时引用少量关键片段（短片段即可）。
- 如果是复杂任务且改了多处代码：必须逐文件逐点说明"改了哪里、为什么改、改前是什么行为、改后是什么行为"，并尽可能给出充分的 before/after 代码片段或直接贴出完整 diff（越多越好）。
- 如果只改了很小的东西：也要解释清楚改动的影响范围与行为变化。
"""

AGENTS = {
    "codex": {
        "launch_cmd": lambda sid, prompt: ["codex", "-a", "never", "exec", "-s", "danger-full-access", "--skip-git-repo-check", prompt],
        "resume_cmd": lambda sid, prompt: ["codex", "-a", "never", "exec", "--skip-git-repo-check", "-s", "danger-full-access", "resume", sid, prompt],
        "sid_from_output": True,
    },
    "claude": {
        "launch_cmd": lambda sid, prompt: ["claude", "-p", prompt, "--session-id", sid, "--dangerously-skip-permissions"],
        "resume_cmd": lambda sid, prompt: ["claude", "-p", prompt, "--resume", sid, "--dangerously-skip-permissions"],
        "sid_from_output": False,
    },
}

def _get_agent():
    name = os.environ.get("AGENT_TYPE", "claude").lower()
    if name not in AGENTS:
        raise ValueError(f"Unknown AGENT_TYPE: {name}, must be one of {list(AGENTS.keys())}")
    return AGENTS[name]

def _wrap_prompt(user_prompt: str) -> str:
    worker_instruction = ""
    worker_file = ROOT / WORKER_PROMPT_FILE
    if worker_file.exists():
        worker_instruction = f"【重要】执行任务前，请先阅读 {WORKER_PROMPT_FILE} 文件了解执行规范。\n"
        worker_instruction += "如果 sop/ 目录下有与当前任务相关的 SOP 文件，请先阅读并遵循。\n\n"
    return f"{worker_instruction}{PROMPT_PREFIX}\n\n用户任务：\n{user_prompt}\n"

def launch(prompt: str) -> dict:
    agent = _get_agent()
    wrapped = _wrap_prompt(prompt)

    if agent["sid_from_output"]:
        # Codex: 从输出解析 session_id
        tmp_log = LOGS / f"tmp_{int(time.time()*1000)}.log"
        with open(tmp_log, "w") as f:
            proc = subprocess.Popen(
                agent["launch_cmd"](None, wrapped),
                stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
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
    else:
        # Claude: 预生成 UUID
        session_id = str(uuid.uuid4())
        log_file = LOGS / f"{session_id}.log"
        pid_file = LOGS / f"{session_id}.pid"
        with open(log_file, "w") as f:
            proc = subprocess.Popen(
                agent["launch_cmd"](session_id, wrapped),
                stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True,
            )

    pid_file.write_text(str(proc.pid))
    return {"session_id": session_id, "pid": proc.pid, "log": str(log_file.relative_to(ROOT))}

def resume(session_id: str, prompt: str) -> dict:
    agent = _get_agent()
    log_file = LOGS / f"{session_id}.log"
    pid_file = LOGS / f"{session_id}.pid"

    with open(log_file, "a") as f:
        f.write("\n\n# --- resume ---\n\n")
        proc = subprocess.Popen(
            agent["resume_cmd"](session_id, _wrap_prompt(prompt)),
            stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    pid_file.write_text(str(proc.pid))
    return {"session_id": session_id, "pid": proc.pid, "log": str(log_file.relative_to(ROOT))}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python agent_launch.py "prompt"')
        print('   or: python agent_launch.py --resume <session_id> "prompt"')
        print(f'Set AGENT_TYPE env var to switch backend (current: {os.environ.get("AGENT_TYPE", "codex")})')
        sys.exit(1)
    if sys.argv[1] == "--resume":
        if len(sys.argv) < 4:
            print('Usage: python agent_launch.py --resume <session_id> "prompt"')
            sys.exit(1)
        print(json.dumps(resume(sys.argv[2], sys.argv[3])))
    else:
        print(json.dumps(launch(sys.argv[1])))
