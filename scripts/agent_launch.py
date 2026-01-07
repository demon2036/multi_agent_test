#!/usr/bin/env python3
"""统一启动器：通过 AGENT_TYPE 环境变量选择 codex 或 claude"""
import subprocess, sys, os, uuid, re, time, json, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # 项目根目录
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

_SID_RE = re.compile(r"session id: ([a-f0-9-]+)")

# Worker prompt 文件路径，可通过环境变量覆盖
WORKER_PROMPT_FILE = os.environ.get("WORKER_PROMPT_FILE", "prompts/WORKER.md")

# Worker 工作目录，可通过环境变量覆盖
WORKDIR = ROOT / os.environ.get("WORKER_WORKDIR", "workdir")
WORKDIR.mkdir(exist_ok=True)

# 确保 answers 和 sop 目录存在
ANSWERS_DIR = WORKDIR / "answers"
ANSWERS_DIR.mkdir(exist_ok=True)
SOP_DIR = WORKDIR / "sop"
SOP_DIR.mkdir(exist_ok=True)

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
    name = os.environ.get("AGENT_TYPE", "codex").lower()
    if name not in AGENTS:
        raise ValueError(f"Unknown AGENT_TYPE: {name}, must be one of {list(AGENTS.keys())}")
    return AGENTS[name]

def _wrap_prompt(user_prompt: str, output_name: str = None, sop_name: str = None) -> str:
    worker_instruction = ""
    worker_file = ROOT / WORKER_PROMPT_FILE
    if worker_file.exists():
        worker_instruction = f"【重要】执行任务前，请先阅读 {WORKER_PROMPT_FILE} 文件了解执行规范。\n"
        worker_instruction += "如果 sop/ 目录下有与当前任务相关的 SOP 文件，请先阅读并遵循。\n\n"

    output_instruction = ""
    if output_name:
        output_instruction = f"""
【输出要求 - 必须遵守】
任务完成后，必须将回答写入 `answers/{output_name}.md`

回���必须详细完整：
- 代码分析类：逐段解释关键逻辑、数据流、边界条件，引用关键代码片段
- 代码改动类：逐文件逐点说明改了哪里、为什么改、改前/改后行为，贴出 diff
- 搜索定位类：列出所有匹配位置，附带简要说明

绝对不允许敷衍了事或只给结论不给过程！

"""

    sop_instruction = ""
    if sop_name:
        sop_instruction = f"""
【SOP 输出要求】
将 SOP 写入 `sop/{sop_name}.md`，格式：

# [SOP 标题]

## 适用场景
[什么情况下使用这个 SOP]

## 步骤
1. ...
2. ...

## 注意事项
- ...

"""
    return f"{worker_instruction}{output_instruction}{sop_instruction}{PROMPT_PREFIX}\n\n用户任务：\n{user_prompt}\n"

def launch(prompt: str, output_name: str = None, sop_name: str = None) -> dict:
    agent = _get_agent()
    wrapped = _wrap_prompt(prompt, output_name, sop_name)

    if agent["sid_from_output"]:
        # Codex: 从输出解析 session_id
        tmp_log = LOGS / f"tmp_{int(time.time()*1000)}.log"
        with open(tmp_log, "w") as f:
            proc = subprocess.Popen(
                agent["launch_cmd"](None, wrapped),
                stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True,
                cwd=WORKDIR,
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
                cwd=WORKDIR,
            )

    pid_file.write_text(str(proc.pid))
    result = {"session_id": session_id, "pid": proc.pid, "log": str(log_file.relative_to(ROOT))}
    if output_name:
        result["answer"] = f"workdir/answers/{output_name}.md"
    if sop_name:
        result["sop"] = f"workdir/sop/{sop_name}.md"
    return result

def resume(session_id: str, prompt: str, output_name: str = None, sop_name: str = None) -> dict:
    agent = _get_agent()
    log_file = LOGS / f"{session_id}.log"
    pid_file = LOGS / f"{session_id}.pid"

    with open(log_file, "a") as f:
        f.write("\n\n# --- resume ---\n\n")
        proc = subprocess.Popen(
            agent["resume_cmd"](session_id, _wrap_prompt(prompt, output_name, sop_name)),
            stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True,
            cwd=WORKDIR,
        )

    pid_file.write_text(str(proc.pid))
    result = {"session_id": session_id, "pid": proc.pid, "log": str(log_file.relative_to(ROOT))}
    if output_name:
        result["answer"] = f"workdir/answers/{output_name}.md"
    if sop_name:
        result["sop"] = f"workdir/sop/{sop_name}.md"
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动或恢复 Worker Agent")
    parser.add_argument("--output", "-o", help="输出文件名（不含.md后缀），Worker 会将回答写入 answers/{output}.md")
    parser.add_argument("--sop", "-s", help="SOP 文件名（不含.md后缀），Worker 会将 SOP 写入 sop/{sop}.md")
    parser.add_argument("--resume", "-r", metavar="SESSION_ID", help="恢复指定 session")
    parser.add_argument("prompt", nargs="?", help="任务 prompt")

    args = parser.parse_args()

    if not args.prompt:
        parser.print_help()
        print(f'\nSet AGENT_TYPE env var to switch backend (current: {os.environ.get("AGENT_TYPE", "codex")})')
        sys.exit(1)

    if args.resume:
        print(json.dumps(resume(args.resume, args.prompt, args.output, args.sop)))
    else:
        print(json.dumps(launch(args.prompt, args.output, args.sop)))
