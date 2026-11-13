# -*- coding: utf-8 -*-
"""Mini Agent —— 从零实现的最小可用 Agent（Agent Runtime 自研，无任何 agent 框架）。"""
from .llm import LLMClient, LLMError
from .session import Session, SessionStore, SYSTEM_PROMPT
from .loop import Agent, MAX_ITERATIONS
from .context import ContextManager

__version__ = "0.1.0"
