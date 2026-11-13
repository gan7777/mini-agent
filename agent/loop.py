# -*- coding: utf-8 -*-
"""Agent 核心循环 + 工具调用 trace。

Loop 步骤（对应笔试题要求）：
  Step one   接收用户输入（追加到 session.messages）
  Step two   调 LLM，模型基于工具 schema 自主决策：直接回复 or 发起 tool_calls
  Step three 有 tool_calls 则执行工具，结果以 role=tool 消息回填
  Step four  根据情况继续 loop（再调 LLM）或把最终答案返回给用户

安全阀：MAX_ITERATIONS 防止模型无限调用工具死循环。
输出解析：一轮 LLM 回复按三类处理——思考过程（reasoning，只进 trace）、
          工具调用（tool_calls，执行后回填 role=tool）、最终答案（content，返回用户）。
异常处理：工具错误 → 作为 tool result 喂回 LLM；LLM 错误 → 友好文案返回用户。
Trace：每一轮写 logs/trace.jsonl + 控制台摘要。
"""
import getpass
import json
import os
import time
from typing import List, Optional

from .context import ContextManager, estimate_messages_tokens
from .llm import LLMClient, LLMError
from .session import Session, SessionStore
from .tools import ToolRegistry

MAX_ITERATIONS = 10  # 单次任务最多工具调用轮数，防止死循环


class TraceLogger:
    """结构化 trace：每轮 loop 记一行 jsonl，方便面试官直接查看执行日志。"""

    def __init__(self, log_dir: str = "logs"):
        os.makedirs(log_dir, exist_ok=True)
        self.path = os.path.join(log_dir, "trace.jsonl")

    def log(self, session_id: str, event: dict) -> None:
        record = {"ts": time.strftime("%H:%M:%S"), "session": session_id, **event}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class Agent:
    def __init__(self, llm: LLMClient, registry: ToolRegistry, store: SessionStore,
                 context_manager: Optional[ContextManager] = None,
                 trace: Optional[TraceLogger] = None, verbose: bool = True):
        self.llm = llm
        self.registry = registry
        self.store = store
        self.ctx = context_manager or ContextManager(llm)
        self.trace = trace or TraceLogger()
        self.verbose = verbose

    # ------------------------------------------------------------------ #
    def run(self, session: Session, user_input: str) -> str:
        """处理一轮用户输入，返回最终文本回复（内部可能经过多轮工具调用）。"""
        session.append({"role": "user", "content": user_input})

        for iteration in range(1, MAX_ITERATIONS + 1):
            # context 压缩检查：发起 LLM 调用前确保没超阈值
            before_len = len(session.messages)
            session.messages = self.ctx.maybe_compress(session.messages)
            if len(session.messages) < before_len:
                # 压缩发生时要留痕：演示/排查时一眼能看到"它在何时压缩"
                if self.verbose:
                    print(f"  🗜 [context] 触发压缩：{before_len} 条 → "
                          f"{len(session.messages)} 条（旧对话已摘要）")
                self.trace.log(session.session_id, {
                    "iter": iteration, "event": "context_compressed",
                    "before_msgs": before_len, "after_msgs": len(session.messages),
                    "tokens_est": estimate_messages_tokens(session.messages),
                })

            try:
                assistant_msg = self.llm.chat(
                    session.messages, tools=self.registry.to_openai_schemas()
                )
            except LLMError as e:
                # LLM 层异常：不能把堆栈抛给用户，给出可操作的文案
                self.trace.log(session.session_id, {"iter": iteration,
                               "event": "llm_error", "error": str(e)})
                return f"抱歉，模型调用出现问题：{e}"

            tool_calls = assistant_msg.get("tool_calls") or []

            # 解析 LLM 输出：思考过程 / 工具调用 / 最终答案，三类都要能被区分出来。
            # reasoning 字段各家长得不完全一样（DeepSeek 用 reasoning_content，
            # 部分兼容实现用 reasoning），统一取一次。
            thinking = assistant_msg.get("reasoning_content") or assistant_msg.get("reasoning") or ""
            if thinking:
                if self.verbose:
                    first_line = thinking.strip().splitlines()[0] if thinking.strip() else ""
                    print(f"  💭 [thinking] {first_line[:80]}")
                # 思考过程只进 trace，不回填 context：一是部分模型不接受回传
                # reasoning 字段（会 400），二是思考文本通常比答案还长，回填会加速 context 爆炸
                self.trace.log(session.session_id, {
                    "iter": iteration, "event": "llm_thinking",
                    "thinking": thinking[:300],
                })

            if not tool_calls:
                # Step four：模型给出最终答案，loop 结束
                content = assistant_msg.get("content") or ""
                session.append({"role": "assistant", "content": content})
                self.trace.log(session.session_id, {
                    "iter": iteration, "event": "final_answer",
                    "answer": content[:100],
                    "tokens_est": estimate_messages_tokens(session.messages),
                })
                self.store.save(session)
                return content

            # Step three：执行工具
            # assistant 的 tool_calls 消息必须先进 history，且必须去掉 reasoning 字段——
            # 下一轮请求原样带回去，不少 OpenAI-compatible 服务会直接 400
            session.append({k: v for k, v in assistant_msg.items()
                            if k not in ("reasoning_content", "reasoning")})
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                t0 = time.time()
                result = self.registry.execute(name, args, session)
                cost_ms = int((time.time() - t0) * 1000)

                if self.verbose:
                    print(f"  ⚙ [{iteration}] {name}({json.dumps(args, ensure_ascii=False)}) -> {result[:60]}...")
                self.trace.log(session.session_id, {
                    "iter": iteration, "event": "tool_call", "tool": name,
                    "args": args, "result": result[:200], "cost_ms": cost_ms,
                })
                session.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result,
                })

        # 达到最大轮次：强制截断，明确告知（而不是静默失败）
        self.trace.log(session.session_id, {"event": "max_iterations_reached",
                       "max": MAX_ITERATIONS})
        return (f"（本次任务已连续执行 {MAX_ITERATIONS} 轮工具调用仍未完成，"
                f"为安全起见已停止。你可以换个说法让我继续。）")


def build_agent(verbose: bool = True) -> Agent:
    """组装默认 Agent（真实 LLM）。"""
    llm = LLMClient()
    from .tools import build_default_registry
    registry = build_default_registry()
    store = SessionStore()
    # 压缩阈值可通过环境变量调小，方便现场演示压缩行为
    max_tokens = int(os.environ.get("AGENT_CONTEXT_MAX_TOKENS", "3000"))
    ctx = ContextManager(llm, max_tokens=max_tokens)
    return Agent(llm=llm, registry=registry, store=store,
                 context_manager=ctx, verbose=verbose)


def repl(agent: Agent, session_id: Optional[str] = None) -> None:
    """交互式命令行：一个 session_id 就是一个独立窗口。"""
    session_id = session_id or f"window-{getpass.getuser()}"
    session = agent.store.get(session_id)
    print(f"Mini Agent 已启动 | session={session_id} | 输入 exit 退出")
    if len(session.user_messages()) > 0:
        print(f"（检测到历史记录 {len(session.user_messages())} 条，继续上次的对话）")
    while True:
        try:
            user_input = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            break
        reply = agent.run(session, user_input)
        print(f"\nAgent> {reply}")
    agent.store.save(session)
    print("已保存 session，下次用相同 --session-id 可继续对话。")
