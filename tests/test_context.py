# -*- coding: utf-8 -*-
"""Context 压缩测试。"""
from agent.context import (ContextManager, SUMMARY_MARKER,
                           estimate_messages_tokens, estimate_tokens)
from conftest import MockLLM, text_msg


def test_estimate_tokens():
    assert estimate_tokens("你好世界") == 4          # 中文按字
    assert estimate_tokens("abcdefgh") == 2          # 英文按 4 字符


def test_no_compress_below_threshold():
    llm = MockLLM([])
    cm = ContextManager(llm, max_tokens=10000)
    msgs = [{"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"}]
    out = cm.maybe_compress(msgs)
    assert out == msgs
    assert llm.calls == []  # 没触发摘要


def test_compress_keeps_system_and_recent(tmp_path):
    """超阈值：system 保留，旧消息压成 summary，最近 4 条原样保留。"""
    llm = MockLLM([text_msg("用户之前问了天气和待办，助手已回复并记录。")])
    cm = ContextManager(llm, max_tokens=50, keep_recent=4)

    msgs = [{"role": "system", "content": "你是助手"}]
    for i in range(20):
        msgs.append({"role": "user", "content": f"第{i}个问题，内容比较长一些一些" * 3})
        msgs.append({"role": "assistant", "content": f"第{i}个回答，也写长一点点" * 3})

    out = cm.compress(msgs)

    assert out[0]["role"] == "system"                       # system 永远保留
    assert out[1]["role"] == "user"
    assert SUMMARY_MARKER in out[1]["content"]              # 摘要带标记
    assert "已回复" in out[1]["content"]                    # 用了 LLM 的摘要结果
    assert out[-4:] == msgs[-4:]                            # 最近消息原样保留
    assert estimate_messages_tokens(out) < estimate_messages_tokens(msgs)
    # 摘要调用的输入里应包含旧对话内容
    summarized = llm.calls[0]["messages"][0]["content"]
    assert "第0个问题" in summarized


def test_compress_llm_failure_fallback(tmp_path):
    """摘要 LLM 挂了：降级为截断式摘要，不阻断对话。"""
    class BoomLLM(MockLLM):
        def chat(self, messages, tools=None, temperature=0.7):
            raise RuntimeError("llm down")

    cm = ContextManager(BoomLLM([]), max_tokens=50, keep_recent=4)
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(10):
        msgs.append({"role": "user", "content": f"问题{i}"})
        msgs.append({"role": "assistant", "content": f"回答{i}"})
    out = cm.compress(msgs)
    assert SUMMARY_MARKER in out[1]["content"]
    assert "user" in out[1]["content"]  # 降级摘要里有角色信息


def test_compress_preserves_tool_summary_info():
    """旧消息里的 tool_calls 在降级摘要中体现工具名（LLM 摘要时也会透传 transcript）。"""
    cm = ContextManager(MockLLM([]), max_tokens=50, keep_recent=2)
    msgs = [{"role": "system", "content": "sys"},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "1", "function": {"name": "todo", "arguments": "{}"}}]},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"}]
    out = cm.compress(msgs)
    assert "todo" in out[1]["content"]  # 降级摘要标明了调用过的工具
