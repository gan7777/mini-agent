# -*- coding: utf-8 -*-
"""search 工具：mock 实现。

题目允许 search mock。这里返回预置的伪搜索结果（内容写得像真的，否则模型会
判定"结果不可用"并告诉用户搜索没开，演示效果反而失真），但走的是完整的真实工具
链路（注册 -> schema -> LLM 决策 -> 执行 -> 结果回填）。
后续接真实搜索 API 只需要替换 handler，其他一行不动。
"""
import time

from .registry import Tool

# 命中关键词就返回更贴合的结果，让"搜索"看起来真的在查东西
_MOCK_RESULTS = {
    "科技": [
        {"title": "多模态大模型推理成本一年下降约 60%",
         "snippet": "多家厂商在新一代模型中引入稀疏激活与投机解码，单位 token 推理成本较去年同期下降约六成，长上下文场景受益最明显。"},
        {"title": "端侧小模型开始承接高频 Agent 工具调用",
         "snippet": "3B 级别模型在意图分类与工具选择任务上接近大模型表现，部分厂商已把简单工具路由下沉到端侧，首 token 延迟压到 200ms 内。"},
    ],
    "agent": [
        {"title": "Agent 工程的重心从 prompt 转向 harness",
         "snippet": "业内讨论集中在 loop 设计、工具错误回喂、上下文压缩与可观测性四件事，框架本身的价值被重新评估。"},
        {"title": "function calling 与宽原语路线的分歧",
         "snippet": "OpenAI-compatible 阵营依赖强 schema 约束，Claude Code 式实现给模型 Bash/文件编辑等宽工具，二者扩展成本与可控性差异明显。"},
    ],
    "天气": [
        {"title": "广州未来三天以雷阵雨为主",
         "snippet": "受季风槽影响，广州未来三天多雷阵雨，气温 24~30°C，局地伴有短时强降水，出行建议带伞。"},
    ],
}

_FALLBACK = [
    {"title": "相关讨论集中在工程落地而非模型能力",
     "snippet": "围绕该话题的公开讨论多聚焦于部署成本、延迟与可观测性等工程问题，而非模型效果本身。"},
    {"title": "实践者更关注可回滚的小步迭代",
     "snippet": "多位从业者在复盘中提到：先把链路跑通并加满日志，再谈优化，比一开始追求架构完备更有效。"},
]


def _search_handler(args: dict, session) -> str:
    query = args["query"]
    # 模拟网络延迟后返回预置结果；真实实现里这里替换为 httpx 调搜索 API
    time.sleep(0.1)
    results = _FALLBACK
    for key, val in _MOCK_RESULTS.items():
        if key in query.lower():
            results = val
            break
    lines = [f'{i+1}. {r["title"]} — {r["snippet"]}' for i, r in enumerate(results)]
    return f'搜索 "{query}" 的结果：\n' + "\n".join(lines)


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
