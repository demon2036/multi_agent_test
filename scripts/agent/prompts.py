#!/usr/bin/env python3
"""Prompt templates and wrapping logic for agent tasks."""

PROMPT_PREFIX = """\
输出要求（只约束最终回答）：
- 不要输出思维链/内心推理。
- 最终回答必须"详细且贴合任务类型"，不要为了格式硬凑"建议/下一步"。
- 如果是代码解析/讲解：必须结合代码逐段解释（关键函数/关键分支/数据流/边界条件），必要时引用少量关键片段（短片段即可）。
- 如果是复杂任务且改了多处代码：必须逐文件逐点说明"改了哪里、为什么改、改前是什么行为、改后是什么行为"，并尽可能给出充分的 before/after 代码片段或直接贴出完整 diff（越多越好）。
- 如果只改了很小的东西：也要解释清楚改动的影响范围与行为变化。
"""


def wrap_prompt(user_prompt: str, output_name: str = None, sop_name: str = None) -> str:
    """
    Wrap user prompt with standard instructions.

    Args:
        user_prompt: The raw task prompt from user
        output_name: If set, instruct worker to write answer to answers/{output_name}.md
        sop_name: If set, instruct worker to write SOP to sop/{sop_name}.md

    Returns:
        Wrapped prompt string with all instructions prepended
    """
    worker_instruction = ""
    # SOP 提示（WORKER.md 提示已移除，因为 agent 会自动读取 CLAUDE.md）
    worker_instruction += "如果 sop/ 目录下有与当前任务相关的 SOP 文件，请先阅读并遵循。\n\n"

    output_instruction = ""
    if output_name:
        output_instruction = f"""
【输出要求 - 必须遵守】
任务完成后，必须将回答写入 `answers/{output_name}.md`

回答必须详细完整：
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
