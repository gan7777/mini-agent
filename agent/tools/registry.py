# -*- coding: utf-8 -*-
"""工具注册机制。

设计要点：
- 每个工具 = Tool dataclass（name / description / parameters JSON Schema / handler）
- registry 统一维护，to_openai_schema() 生成 OpenAI-compatible function calling 的 tools 参数
- handler 统一签名 handler(args: dict, session: Session) -> str
  - session 传入是为了让工具能按 session 隔离存取状态（如 todo）
- 返回值一律是 str：工具的执行结果（包括错误信息）都会作为 tool result 喂回给 LLM，
  绝不在工具层直接抛异常给用户——错误处理交给 Agent 循环和 LLM 自行决策。
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Any, Optional


@dataclass
class Tool:
    name: str
    description: str
    # JSON Schema，描述参数。LLM 基于 schema 自主决策怎么调用。
    parameters: dict
    handler: Callable[[dict, Any], str]

    def to_openai_schema(self) -> dict:
        """转换成 OpenAI-compatible function calling 的 tool 定义。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """工具注册表。用装饰器或 register() 注册，全项目共享一个实例。"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具重复注册: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def to_openai_schemas(self) -> List[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, args: dict, session: Any) -> str:
        """执行工具，任何异常都转成错误字符串返回（给 LLM 看，让它自行纠正）。"""
        tool = self._tools.get(name)
        if tool is None:
            return f"错误：工具 {name} 不存在。可用工具: {', '.join(self._tools)}"
        # 参数校验：schema 校验失败不 crash，把错误喂回给 LLM 让它重试
        err = self._validate_args(tool, args)
        if err:
            return f"错误：参数校验失败 - {err}。请根据 schema 修正后重试。"
        try:
            return tool.handler(args, session)
        except Exception as e:  # noqa: BLE001 —— 工具层兜底，异常转为可读信息
            return f"错误：工具 {name} 执行失败 - {type(e).__name__}: {e}"

    @staticmethod
    def _validate_args(tool: Tool, args: Any) -> Optional[str]:
        """轻量参数校验，避免引入 jsonschema 依赖也能保证基本健壮性。"""
        if not isinstance(args, dict):
            return "参数必须是 JSON object"
        schema = tool.parameters or {}
        required = schema.get("required", [])
        for r in required:
            if r not in args:
                return f"缺少必填参数: {r}"
        props = schema.get("properties", {})
        type_map = {"string": str, "number": (int, float), "integer": int,
                    "boolean": bool, "array": list, "object": dict}
        for k, v in args.items():
            if k not in props:
                continue  # 额外参数宽松处理
            t = props[k].get("type")
            if t in type_map and not isinstance(v, type_map[t]):
                # bool 是 int 的子类，排除掉
                if t == "integer" and isinstance(v, bool):
                    return f"参数 {k} 应为 integer"
                if not (t in ("number", "integer") and isinstance(v, bool)):
                    return f"参数 {k} 应为 {t}, 实际为 {type(v).__name__}"
        return None
