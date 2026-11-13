# -*- coding: utf-8 -*-
"""Agent Loop 测试：用 MockLLM 驱动，覆盖 loop 终止、工具回填、截断、LLM 异常。"""
from agent.loop import Agent, MAX_ITERATIONS
from agent.context import ContextManager
from agent.session import SessionStore
from agent.tools import build_default_registry
from conftest import MockLLM, tool_call_msg, text_msg


def make_agent(script, tmp_path):
    llm = MockLLM(script)
    store = SessionStore(base_dir=str(tmp_path / "sessions"))
    agent = Agent(llm=llm, registry=build_default_registry(), store=store,
                  context_manager=ContextManager(llm), verbose=False)
    return agent, llm


def test_tool_call_then_final_answer(tmp_path):
    """模型先调 calculator 再给最终答案：验证 loop 走通 + 工具结果回填。"""
    agent, llm = make_agent(
        [tool_call_msg("calculator", {"expression": "(3+5)*2"}),
         text_msg("计算结果是 16。")],
        tmp_path,
    )
    session = agent.store.get("t1")
    reply = agent.run(session, "帮我算下 (3+5)*2")

    assert reply == "计算结果是 16。"
    # messages 里应有：user, assistant(tool_calls), tool(result), assistant(final)
    roles = [m["role"] for m in session.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    tool_msg = session.messages[3]
    assert "(3+5)*2 = 16" in tool_msg["content"]
    # 第二次调用 LLM 时，工具结果已在 context 中
    second_call = llm.calls[1]["messages"]
    assert any(m["role"] == "tool" and "16" in m["content"] for m in second_call)


def test_max_iterations_truncation(tmp_path):
    """模型无限要求调工具：达到 MAX_ITERATIONS 后强制截断且不再调用 LLM。"""
    agent, llm = make_agent(
        [tool_call_msg("search", {"query": "x"}, call_id=f"c{i}")
         for i in range(MAX_ITERATIONS + 3)],
        tmp_path,
    )
    session = agent.store.get("t2")
    reply = agent.run(session, "一直搜下去")

    assert "停止" in reply and str(MAX_ITERATIONS) in reply
    assert len(llm.calls) == MAX_ITERATIONS  # 恰好调用 MAX_ITERATIONS 次


def test_llm_error_returns_friendly_message(tmp_path):
    """LLM 层抛异常：loop 不崩溃，返回友好错误文案。"""
    from agent.llm import LLMError

    class BoomLLM(MockLLM):
        def chat(self, messages, tools=None, temperature=0.7):
            raise LLMError("连接超时")

    agent = Agent(llm=BoomLLM([]), registry=build_default_registry(),
                  store=SessionStore(base_dir=str(tmp_path / "s")), verbose=False)
    session = agent.store.get("t3")
    reply = agent.run(session, "hi")
    assert "模型调用出现问题" in reply and "连接超时" in reply


def test_unknown_tool_error_fed_back_to_llm(tmp_path):
    """模型调了不存在的工具：错误作为 tool result 喂回，loop 继续。"""
    agent, llm = make_agent(
        [tool_call_msg("not_exist", {}),
         text_msg("好的，那个工具不可用。")],
        tmp_path,
    )
    session = agent.store.get("t4")
    reply = agent.run(session, "test")
    tool_msg = [m for m in session.messages if m["role"] == "tool"][0]
    assert "工具 not_exist 不存在" in tool_msg["content"]
    assert reply == "好的，那个工具不可用。"


def test_invalid_args_fed_back_not_crash(tmp_path):
    """参数缺必填项：校验错误作为 tool result 返回给 LLM 而不是异常。"""
    agent, _ = make_agent(
        [tool_call_msg("calculator", {"wrong_param": "x"}),  # 缺必填 expression
         text_msg("收到。")],
        tmp_path,
    )
    session = agent.store.get("t5")
    agent.run(session, "算个数")
    tool_msg = [m for m in session.messages if m["role"] == "tool"][0]
    assert "参数校验失败" in tool_msg["content"]
