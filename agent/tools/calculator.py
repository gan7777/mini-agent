# -*- coding: utf-8 -*-
"""calculator 工具：基于 ast 的安全四则运算求值（不用裸 eval，防注入）。"""
import ast
import math
import operator

from .registry import Tool

# ast 白名单挡住了代码注入，但挡不住「合法的天文数字」：
# 9**9**9 是纯算术表达式，能通过白名单，却会让进程算到天荒地老（实测卡死）。
# 所以对幂运算单独加上限，并限制表达式长度，防止一次工具调用把进程拖死。
MAX_POW_EXPONENT = 100
MAX_EXPR_LENGTH = 200

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
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if type(node.op) is ast.Pow:
            # 幂是唯一会出现「输入极短、计算量爆炸」的算子，单独设闸
            if abs(right) > MAX_POW_EXPONENT:
                raise ValueError(f"指数过大（上限 {MAX_POW_EXPONENT}），拒绝计算")
            if abs(left) > 1e6 and right > 1:
                raise ValueError("底数过大，拒绝计算")
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"不支持的表达式元素: {type(node).__name__}")


def _calc_handler(args: dict, session) -> str:
    expr = args["expression"]
    if len(expr) > MAX_EXPR_LENGTH:
        return f"错误：表达式过长（上限 {MAX_EXPR_LENGTH} 字符）"
    try:
        result = _safe_eval(ast.parse(expr, mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        return f"错误：表达式无法计算 - {e}"
    if isinstance(result, float) and not math.isfinite(result):
        return "错误：计算结果溢出（超出浮点范围）"
    # 整数结果去掉小数点尾巴
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"{expr} = {result}"


calculator_tool = Tool(
    name="calculator",
    description="精确计算数学表达式（支持 + - * / % ** 和括号，指数不超过 100）。任何需要算数的场合都应使用本工具，不要心算。",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "数学表达式，如 (3+5)*12/2"}
        },
        "required": ["expression"],
    },
    handler=_calc_handler,
)
