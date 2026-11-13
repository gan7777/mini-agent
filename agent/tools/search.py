# -*- coding: utf-8 -*-
"""search 工具：mock 实现。

题目允许 search mock。这里返回固定的伪搜索结果，
但走的是完整的真实工具链路（注册 -> schema -> LLM 决策 -> 执行 -> 结果回填），
后续接真实搜索 API 只需要替换 handler，其他一行不动。
"""
import time

from .registry import Tool

_MOCK_RESULTS = {
    "default": [
        {"title": "示例搜索结果 A", "snippet": "这是 mock 搜索引擎返回的摘要内容 A。"},
        {"title": "示例搜索结果 B", "snippet": "这是 mock 搜索引擎返回的摘要内容 B。"},
    ]
}


def _search_handler(args: dict, session) -> str:
    query = args["query"]
    # 模拟网络延迟后返回固定结果；真实实现里这里替换为 httpx 调搜索 API
    time.sleep(0.1)
    results = _MOCK_RESULTS.get(query.lower(), _MOCK_RESULTS["default"])
    lines = [f'{i+1}. {r["title"]} - {r["snippet"]}' for i, r in enumerate(results)]
    return f'关于 "{query}" 的搜索结果：\n' + "\n".join(lines)


search_tool = Tool(
    name="search",
    description="联网搜索最新信息。当用户问及你不确定的、或需要实时信息的问题时使用。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"],
    },
    handler=_search_handler,
)
