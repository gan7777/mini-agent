# -*- coding: utf-8 -*-
from .registry import Tool, ToolRegistry
from .todo import todo_tool
from .calculator import calculator_tool
from .search import search_tool
from .weather import weather_tool

__all__ = ["Tool", "ToolRegistry", "todo_tool", "calculator_tool",
           "search_tool", "weather_tool"]


def build_default_registry() -> ToolRegistry:
    """组装默认工具集：todo（必做）+ calculator + search(mock) + weather(mock)。"""
    reg = ToolRegistry()
    reg.register(todo_tool)
    reg.register(calculator_tool)
    reg.register(search_tool)
    reg.register(weather_tool)
    return reg
