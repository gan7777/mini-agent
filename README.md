# Mini Agent —— 从零实现的最小可用 Agent

GitHub: https://github.com/gan7777/mini-agent

不依赖任何 agent 框架（langgraph / openhands 等），Agent Runtime 全部手写：
agent loop、工具注册（JSON Schema 驱动 function calling）、多 session 管理、
context 压缩、工具调用 trace。

## 运行方式

```bash
# 1. 安装依赖（仅 httpx，无任何 agent 框架）
pip install -r requirements.txt

# 2. 配置 API key（代码里零密钥，全部走环境变量）
cp .env.example .env
# 编辑 .env 填入你的 LLM_API_KEY（任何 OpenAI-compatible 服务均可）

# 3. 启动（Windows: python main.py，需要先 set 环境变量或使用 .env 加载）
python main.py --session-id window-1
```

多窗口演示（对应笔试题 session 管理要求）：

```bash
python main.py --session-id window-1   # 窗口1：查天气、记待办
python main.py --session-id window-2   # 窗口2：写周报、记待办（与窗口1完全隔离）
```

同名 `--session-id` 随时重进续聊：session 落盘在 `sessions/` 目录，
重启进程后对话历史、待办状态原样恢复。

运行测试（不依赖真实 API key，LLM 用 mock 替身）：

```bash
pytest tests/ -q
```

## 在 PyCharm 里跑起来（3 步）

1. **打开项目**：`File → Open`，选中 `mini-agent` 文件夹（注意选到含 `main.py` 的这一层，
   不要选它的父目录），PyCharm 会自动识别为 Python 项目。
2. **配解释器**：`File → Settings → Project → Python Interpreter → Add Interpreter → Add Local Interpreter`，
   选一个 Python 3.9+ 的解释器；然后在 PyCharm 底部 `Terminal` 里执行
   `pip install -r requirements.txt`（只有 httpx 一个运行依赖 + pytest）。
3. **跑起来**：
   - 想聊天：右键 `main.py → Run 'main'`，控制台里直接输入对话。
   - 想带会话：`Run → Edit Configurations → Parameters` 填 `--session-id window-1`，
     再复制一份配置改成 `window-2`，就能开两个窗口演示隔离。
   - 想跑测试：右键 `tests` 目录 → `Run 'pytest in tests'`，应看到 24 passed。
   - 想跑端到端演示：右键 `scripts/smoke_test.py → Run`，会自动验证 todo/追问/计算/搜索/隔离/持久化。

**关于 API key**（代码零密钥，两种方式任选）：

- 方式一（推荐）：系统环境变量里设置 `LLM_API_KEY`（任何 OpenAI-compatible 服务的 key），
  PyCharm 启动时会自动继承。
- 方式二：把 `.env.example` 复制成 `.env`，填入 `LLM_API_KEY=...` 后重开 PyCharm/重跑
  （`.env` 已在 `.gitignore` 中，不会被提交）。
- 若系统里已有 `DASHSCOPE_API_KEY`（通义千问），无需任何配置，程序会自动切换到
  dashscope 兼容端点和 `qwen-plus` 模型。

> 常见坑：`ModuleNotFoundError: No module named 'agent'` —— 说明打开的是父目录而不是
> `mini-agent` 本身，或运行配置里的 Working directory 不是项目根目录，改回项目根即可。

## 系统设计

```
┌──────────┐   user input   ┌─────────────────────────────────────┐
│ main.py  │ ─────────────▶ │ Agent.run(session, input)  [loop.py]│
└──────────┘                │  ┌───────────────────────────────┐  │
                            │  │ while iter < MAX_ITERATIONS:  │  │
┌──────────┐   messages     │  │  LLM.chat(messages, tools)    │  │
│Session   │──────────────▶ │  │   │                           │  │
│Store     │  (含持久化)    │  │   ├─ 无 tool_calls → 最终答案  │  │
└──────────┘                │  │   └─ 有 tool_calls → 执行工具  │  │
                            │  │        结果 role=tool 回填 ──┐ │  │
┌──────────┐  tool schemas  │  └────────────────────────┼────┘  │
│Tool      │──────────────▶ │      继续循环 ◀────────────┘      │
│Registry  │                └─────────────────────────────────────┘
└──────────┘                        │
┌──────────┐  超阈值压缩    ┌───────▼──────────┐   每轮一行   ┌──────────┐
│Context   │──────────────▶│ TraceLogger      │────────────▶│ logs/    │
│Manager   │               └──────────────────┘   jsonl     │trace.jsonl│
└──────────┘                                                └──────────┘
```

模块职责：

| 模块 | 职责 | 关键决策 |
|---|---|---|
| `agent/loop.py` | Agent 核心循环 | 终止条件=无 tool_calls 或达 `MAX_ITERATIONS`（防死循环）；工具结果以 `role=tool` 回填后继续 loop |
| `agent/llm.py` | LLM 客户端 | 手写 httpx 调 OpenAI-compatible 接口（不用 SDK）；超时+2次重试；4xx 不重试直接报错 |
| `agent/tools/registry.py` | 工具注册机制 | Tool = name/description/JSON Schema/handler；参数校验失败**不 crash**，错误信息作为 tool result 喂回 LLM 让它自行纠正 |
| `agent/tools/todo.py` | 必做工具 | 单工具带 action 参数（add/list/complete）；状态挂 session 上，天然按窗口隔离+落盘 |
| `agent/tools/calculator.py` | 计算工具 | ast 安全求值，拒绝任意代码注入（不用裸 eval） |
| `agent/tools/search.py` | 搜索工具 | mock 实现，但走完整真实工具链路；换真实 API 只需改 handler |
| `agent/session.py` | Session 管理 | 每 session 一个 json，原子写入（tmp+replace）；session_id 净化防路径逃逸 |
| `agent/context.py` | Context 管理 | 估算 token 超阈值→旧消息 LLM 摘要替换（system 永远保留，最近 N 条原样）；摘要失败降级为截断式摘要，不阻断对话 |
| `agent/loop.py TraceLogger` | 工具调用 trace | 每轮 loop 写一行 jsonl：时间/session/轮次/工具/入参/结果/耗时 |

## Memory 的召回时机与放置方式（重点设计说明）

本项目的 memory 分三层，各自的**写入时机**和**召回时机**不同：

**1. 短期记忆 = session.messages（对话内）**

- 写入：每轮 loop 自动追加（user 输入、assistant 回复、tool 结果）
- 召回：无需召回，每次 LLM 调用全量随行——这是追问能 work 的原因：
  - 纯对话追问：上一轮的 user/assistant 消息就在 history 里
  - 带工具的追问：工具的调用参数与结果也以 tool 消息保留在 history 里
- 放置方式：完整保留在 context 中，直到触发压缩

**2. 压缩记忆 = summary 消息（超长对话）**

- 写入时机：发起 LLM 调用前检查，估算 token 超过阈值才触发（`context.maybe_compress`）
- 召回方式：压缩产物作为一条带 `[历史对话摘要]` 标记的 user 消息，**放在 context 头部**
  （system 之后、最近消息之前）——位置靠前保证注意力权重高，且 system prompt 永不被动
- 放置方式：`system → summary → 最近 keep_recent 条原样消息`。最近的细节不摘要
  （保证追问连贯），更早的噪声被摘要掉

**3. 跨 session 长期记忆（设计预留，README 说明方向）**

- 当前实现范围：题目要求的基础版是 session 内记忆，跨 session 长期记忆未实现完整闭环，
  但存储位与召回时机已预留设计：
- 写入时机：任务结束时抽取"值得记住的事实"（用户偏好、长期待办），写入
  per-user 的长期存储（向量库或结构化 KV）
- 召回时机：**新用户输入进来后、拼 context 之前**——用当前输入做检索
  （embedding 相似度或规则匹配），把命中的记忆片段注入 system prompt 尾部，
  而不是塞满整个 context
- 为什么不用全文塞入：长期记忆会无限增长，检索式召回（召回 top-k 相关片段）
  才能同时保证"记得住"和"context 不爆炸"

## 使用的 AI 辅助与问题解决记录

见 [docs/ai-log.md](docs/ai-log.md)。

## 项目结构

```
mini-agent/
├── agent/
│   ├── loop.py          # Agent 核心循环 + TraceLogger
│   ├── llm.py           # OpenAI-compatible LLM 客户端（手写 httpx）
│   ├── session.py       # Session/SessionStore（持久化、隔离）
│   ├── context.py       # Context 压缩
│   └── tools/
│       ├── registry.py  # 工具注册机制（Schema 驱动）
│       ├── todo.py      # 待办（必做）
│       ├── calculator.py# ast 安全计算
│       └── search.py    # mock 搜索
├── tests/               # 24 个测试，MockLLM 驱动，零 API key 依赖
├── docs/ai-log.md       # AI 使用记录
├── main.py              # CLI 入口
└── logs/trace.jsonl     # 运行时自动生成的工具调用 trace
```
