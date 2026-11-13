# -*- coding: utf-8 -*-
"""测试公共设施：MockLLM 模拟 LLM 行为，测试全流程不依赖真实 API key。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.llm import LLMClient  # noqa: E402


class MockLLM(LLMClient):
    """按脚本回放的假 LLM。

    script: 每次被调用时按顺序弹出一个返回项：
      - dict 带 tool_calls -> 模拟模型要调工具
      - dict 带 content    -> 模拟最终答案
    用完脚本后抛 AssertionError，防止测试静默通过。
    """

    def __init__(self, script):
        super().__init__(api_key="mock-key")
        self.script = list(script)
        self.calls = []  # 记录每次收到的 messages，便于断言

    def chat(self, messages, tools=None, temperature=0.7):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        if not self.script:
            raise AssertionError("MockLLM 脚本耗尽，但 loop 还在调用 LLM")
        return self.script.pop(0)


def tool_call_msg(name, args, call_id="call_1"):
    """构造一条模拟的 tool_calls assistant 消息。"""
    import json
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
        }],
    }


def text_msg(content):
    return {"role": "assistant", "content": content}
