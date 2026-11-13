# -*- coding: utf-8 -*-
"""weather 工具：mock 实现（题目允许自定义工具，这里是第 4 个工具）。

返回值固定但结构真实，接真实天气 API 只需替换 handler。
"""
from .registry import Tool

_MOCK_WEATHER = {
    "杭州": "晴，18~26°C，东南风 2 级，空气质量良",
    "厦门": "多云，22~28°C，微风，空气质量优",
    "广州": "雷阵雨，24~30°C，南风 3 级，注意带伞",
}


def _weather_handler(args: dict, session) -> str:
    city = args["city"].strip()
    for name, info in _MOCK_WEATHER.items():
        if name in city:
            return f"{name}今天天气：{info}"
    return f"{city}今天天气：晴，20~27°C（mock 数据，未覆盖该城市时返回默认值）"


weather_tool = Tool(
    name="weather",
    description="查询指定城市今天的天气。用户问到天气、出门、穿衣建议时使用。",
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名，如 杭州"}
        },
        "required": ["city"],
    },
    handler=_weather_handler,
)
