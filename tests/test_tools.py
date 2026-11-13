# -*- coding: utf-8 -*-
"""工具系统测试：注册、schema 生成、执行、参数校验、todo 状态流转。"""
import pytest

from agent.session import Session
from agent.tools import Tool, ToolRegistry, todo_tool, calculator_tool, search_tool


def test_registry_register_and_schema():
    reg = ToolRegistry()
    tool = Tool(name="dummy", description="d", parameters={"type": "object", "properties": {}},
                handler=lambda a, s: "ok")
    reg.register(tool)
    schemas = reg.to_openai_schemas()
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "dummy"


def test_registry_duplicate_rejected():
    reg = ToolRegistry()
    tool = Tool(name="x", description="d", parameters={}, handler=lambda a, s: "ok")
    reg.register(tool)
    with pytest.raises(ValueError):
        reg.register(tool)


def test_calculator_safe_eval():
    session = Session("c1")
    assert "(3+5)*2 = 16" in calculator_tool.handler({"expression": "(3+5)*2"}, session)
    assert "2**2 = 4" in calculator_tool.handler({"expression": "2**2"}, session)


def test_calculator_rejects_injection():
    session = Session("c2")
    out = calculator_tool.handler({"expression": "__import__('os').system('echo hi')"}, session)
    assert "无法计算" in out  # 不执行任意代码


def test_calculator_zero_division():
    session = Session("c3")
    assert "无法计算" in calculator_tool.handler({"expression": "1/0"}, session)


def test_calculator_rejects_pow_bomb():
    """ast 白名单挡不住「合法但算不完」的表达式，必须有规模上限。"""
    session = Session("c4")
    # 9**9**9 是合法算术，但会让进程卡死；上限生效后应立即返回错误
    assert "无法计算" in calculator_tool.handler({"expression": "9**9**9"}, session)
    # 正常量级的幂仍要能用
    assert "2**10 = 1024" in calculator_tool.handler({"expression": "2**10"}, session)


def test_calculator_rejects_overlong_expression():
    session = Session("c5")
    out = calculator_tool.handler({"expression": "1+" * 200 + "1"}, session)
    assert "表达式过长" in out


def test_todo_flow():
    session = Session("t1")
    assert "已添加待办 #1" in todo_tool.handler({"action": "add", "content": "写周报"}, session)
    assert "已添加待办 #2" in todo_tool.handler({"action": "add", "content": "交房租"}, session)
    listed = todo_tool.handler({"action": "list"}, session)
    assert "#1 写周报" in listed and "#2 交房租" in listed
    assert "已完成待办 #1" in todo_tool.handler({"action": "complete", "todo_id": 1}, session)
    # 重复完成要幂等提示
    assert "已经是完成状态" in todo_tool.handler({"action": "complete", "todo_id": 1}, session)
    # 不存在的 id
    assert "找不到待办" in todo_tool.handler({"action": "complete", "todo_id": 99}, session)


def test_todo_invalid_action():
    session = Session("t2")
    assert "未知 action" in todo_tool.handler({"action": "delete_all"}, session)


def test_search_mock_returns_results():
    session = Session("s1")
    out = search_tool.handler({"query": "今天天气"}, session)
    assert "的结果" in out and "今天天气" in out


def test_registry_executes_and_validates():
    reg = ToolRegistry()
    reg.register(calculator_tool)
    session = Session("r1")
    # 正常
    assert "= 8" in reg.execute("calculator", {"expression": "3+5"}, session)
    # 类型错误
    assert "参数校验失败" in reg.execute("calculator", {"expression": 123}, session)
    # 不存在的工具
    assert "不存在" in reg.execute("nope", {}, session)
