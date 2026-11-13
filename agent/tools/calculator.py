# -*- coding: utf-8 -*-
"""calculator 工具：基于 ast 的安全四则运算求值（不用裸 eval，防注入）。"""
import ast
import operator

from .registry import Tool

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Mod: operator.mod, ast.Pow: operator.pow, ast.FloorDiv: operator.floordiv,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node) -> float:
    """只允许数字与四则运算节点，其余一律拒绝。"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"不支持的表达式元素: {type(node).__name__}")


def _calc_handler(args: dict, session) -> str:
    expr = args["expression"]
    try:
        result = _safe_eval(ast.parse(expr, mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        return f"错误：表达式无法计算 - {e}"
    # 整数结果去掉小数点尾巴
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"{expr} = {result}"


calculator_tool = Tool(
    name="calculator",
    description="精确计算数学表达式（支持 + - * / % ** 和括号）。任何需要算数的场合都应使用本工具，不要心算。",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式，如 (3+5)*12/2"}
        },
        "required": ["expression"],
    },
    handler=_calc_handler,
)
