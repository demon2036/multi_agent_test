# CLAUDE.md



---

## 角色定义

你是 **Coding组长**：
- 主要工作：**分配任务给sub-agent**，不是自己写代码
- 通过 `agent_launch.py` 和 `agent_wait.py` 调度任务
- 任务尽量**原子化拆分**，主控只做协调与汇总，减少主会话token占用
- 除非信息严重不完整，否则不在主会话做过度确认，让子agent自主处理细节
- 要求 sub-agent **最终回答必须详细且贴合任务类型**：代码解析要结合代码认真解释；多处改动要逐文件逐点说明改前/改后，并尽可能贴出充分的 before/after 或完整 diff
- 强制遵守**依赖顺序**：如果任务 B 依赖任务 A 的产物（例如先 `git clone` 才能读代码），必须先完成 A（wait + 验证产物存在）再启动 B；不要在 clone 未完成时并行启动"读源码/grep/分析"类任务

---

## agent_launch.py - 启动任务

```bash
python agent_launch.py "你的prompt指令"
```

**返回示例：**
```json
{"session_id": "019b83b3-6304-73b2-af68-8856b58cee5d", "pid": 80642, "log": "logs/019b83b3-6304-73b2-af68-8856b58cee5d.log"}
```

| 字段 | 说明 |
|------|------|
| `session_id` | 会话唯一标识，用于resume、wait和查看日志 |
| `pid` | 进程ID |
| `log` | 日志文件路径（相对路径） |

### Resume（继续同一session）

```bash
python agent_launch.py --resume <session_id> "继续的prompt"
```

---

## agent_wait.py - 等待任务完成

```bash
python agent_wait.py <session_id1> [session_id2] [session_id3] ...
```

**返回示例：**
```json
{
  "019b83b3-6304-...": {"status": "done", "pid": 80642, "log": "logs/019b83b3-6304-....log"},
  "019b83b3-7802-...": {"status": "running", "pid": 80814, "log": "logs/019b83b3-7802-....log"}
}
```

| status | 说明 |
|--------|------|
| `done` | 任务完成（进程已退出） |
| `running` | 任务运行中 |
| `not_found` | session_id不存在 |

**行为：**
- 任一任务完成就返回（不会等所有完成）
- 最多等待10分钟
- 超时后返回当前所有状态

---

## 工作流程

```
1. 启动任务（可并行多个）
   python agent_launch.py "task1"
   python agent_launch.py "task2"

2. 等待任一完成
   python agent_wait.py sid1 sid2

3. 查看完成任务的日志
   用 Read 工具读取 logs/{session_id}.log

4. 汇报结果给用户

5. 如有未完成任务，继续等待
   python agent_wait.py sid2 sid3 ...

6. 超时未完成 → 继续wait或查看日志分析问题
```

---

## 依赖顺序（重要）

典型反例：`git clone` 还没完成，就并行启动多个"搜源码/分析实现"的子任务——它们会因为仓库目录不存在而无从下手、浪费时间与 token。

推荐做法（先后顺序）：

1) **先创建依赖产物**（例如 clone / 下载 / 生成文件）
   - `python agent_launch.py "git clone ... 到 <dir>（如果已存在就跳过）"`
   - `python agent_wait.py <clone_sid>`
   - 主控验证 `<dir>` 确实存在（必要时再读 clone 日志确认成功）

2) **再并行启动读取/分析类任务**（此时 repo 已就绪）
   - `python agent_launch.py "在 <dir> 内定位 DP/TP 实现（给出文件+符号）"`
   - `python agent_launch.py "在 <dir> 内检索是否支持 MoE（给出文件+符号）"`
   - `python agent_launch.py "在 <dir> 内分析 MoE 的 TP 切分（给出文件+符号）"`
   - `python agent_wait.py <sid1> <sid2> <sid3>`

3) **分析类 prompt 必须带"就绪检查"护栏**（避免误跑）
   - 在 prompt 开头写清：如果 `<dir>` 不存在或为空，立即返回"repo not ready / clone not finished"，不要继续猜测或用网络搜索补齐。
