# -*- coding: utf-8 -*-
"""Context 有效性管理。

策略（题目要求"基础压缩"即可）：
1. 轮次限制：单次任务的 agent loop 由 MAX_ITERATIONS 控制（见 loop.py）
2. 长度限制：messages 估算 token 超过阈值时触发压缩
3. 压缩方式：保留 system prompt 不动；把最早的若干轮对话用 LLM 总结成一条
   带标记的 summary 消息替换，最近 KEEP_RECENT 条原样保留（保证追问连贯）

哪些信息该进 context（README 有详细论述）：
   进：用户输入、assistant 最终回复、工具调用摘要
   精简：工具原始返回的大段内容在压缩时一并被总结掉
"""
import re
from typing import List, Optional

SUMMARY_MARKER = "[历史对话摘要]"


def estimate_tokens(text: str) -> int:
    """粗估 token：中文按字算，英文按 ~4 字符一个 token。
    够用于触发压缩判断，精确计数不是本模块职责。"""
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    return cjk + (len(text) - cjk) // 4


def estimate_messages_tokens(messages: List[dict]) -> int:
    total = 0
    for m in messages:
        total += estimate_tokens(str(m.get("content") or ""))
        for tc in m.get("tool_calls") or []:
            total += estimate_tokens(str(tc.get("function", {}).get("arguments", "")))
    return total


class ContextManager:
    def __init__(self, llm_client, max_tokens: int = 3000, keep_recent: int = 6):
        """
        llm_client:  用于生成摘要（测试时可注入 mock）
        max_tokens:  压缩触发阈值（估算值）
        keep_recent: 压缩时保留最近多少条消息不参与摘要
        """
        self.llm = llm_client
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent

    def maybe_compress(self, messages: List[dict]) -> List[dict]:
        """超阈值则压缩 messages 并原样返回新列表（不修改调用方引用）。"""
        if estimate_messages_tokens(messages) <= self.max_tokens:
            return messages
        return self.compress(messages)

    def compress(self, messages: List[dict]) -> List[dict]:
        system = [m for m in messages if m["role"] == "system"]
        rest = [m for m in messages if m["role"] != "system"]

        if len(rest) <= self.keep_recent:
            return messages  # 没什么可压的

        old = rest[:-self.keep_recent]
        recent = rest[-self.keep_recent:]

        summary_text = self._summarize(old)
        summary_msg = {"role": "user", "content": f"{SUMMARY_MARKER}\n{summary_text}"}

        return system + [summary_msg] + recent

    def _summarize(self, old_messages: List[dict]) -> str:
        """用 LLM 把旧对话压成摘要；LLM 失败时降级为截断式摘要（不阻断对话）。"""
        transcript = "\n".join(
            f"[{m['role']}] {str(m.get('content') or '')[:200]}"
            + (f" (调用工具 {', '.join(tc['function']['name'] for tc in m.get('tool_calls') or [])})"
               if m.get("tool_calls") else "")
            for m in old_messages
        )
        prompt = (
            "请把以下对话历史压缩成一段简洁摘要，保留：用户的目标、已完成的动作、"
            "关键结论（如已记录的待办）。不超过 200 字，直接输出摘要正文。\n\n" + transcript
        )
        try:
            reply = self.llm.chat(
                [{"role": "user", "content": prompt}], tools=None, temperature=0.2
            )
            text = (reply.get("content") or "").strip()
            if text:
                return text
        except Exception:  # noqa: BLE001 —— 摘要失败不影响主流程
            pass
        # 降级：粗暴拼接角色+首行（content 为 None/空的消息只记角色和工具名）
        lines = []
        for m in old_messages:
            first_line = str(m.get("content") or "").strip().splitlines()
            first_line = first_line[0][:80] if first_line else "(无文本内容)"
            tool_names = [tc["function"]["name"] for tc in m.get("tool_calls") or []]
            if tool_names:
                first_line += f"（调用工具: {', '.join(tool_names)}）"
            lines.append(f"{m['role']}: {first_line}")
        return "；".join(lines)[:500]
