# -*- coding: utf-8 -*-
"""LLM 客户端封装（OpenAI-compatible chat/completions）。

- 不依赖任何 SDK/agent 框架，直接用 httpx 调 HTTP 接口，请求体就是最朴素的
  chat.completions 格式（DeepSeek / Qwen / GLM 等均兼容）
- API key 只从环境变量读取（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL），代码里零密钥
- 带超时 + 有限重试 + 明确的错误信息
"""
import os
import time
from typing import List, Optional

import httpx

DEFAULT_BASE_URL = "https://api.deepseek.com"  # 任何 OpenAI-compatible 端点均可
DEFAULT_MODEL = "deepseek-chat"
# 通义千问的 OpenAI 兼容端点（设了 DASHSCOPE_API_KEY 时的默认值）
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_DEFAULT_MODEL = "qwen-plus"


def load_dotenv(path: str = ".env") -> None:
    """极简 .env 加载（不引入 python-dotenv 依赖）。

    只补全环境里还没有的变量，已存在的系统环境变量优先级更高。
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


class LLMError(Exception):
    """LLM 调用失败（重试后仍失败）。"""


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, timeout: float = 60.0, max_retries: int = 2):
        # 全部从环境变量读，仓库里永远不出现真实 key
        # 优先级：LLM_API_KEY > DASHSCOPE_API_KEY（通义，自动切兼容端点）
        self.api_key = (api_key or os.environ.get("LLM_API_KEY")
                        or os.environ.get("DASHSCOPE_API_KEY", ""))
        using_dashscope = not (api_key or os.environ.get("LLM_API_KEY")) and bool(
            os.environ.get("DASHSCOPE_API_KEY"))
        if using_dashscope:
            default_url, default_model = DASHSCOPE_BASE_URL, DASHSCOPE_DEFAULT_MODEL
        else:
            default_url, default_model = DEFAULT_BASE_URL, DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", default_url)).rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL", default_model)
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: List[dict], tools: Optional[List[dict]] = None,
             temperature: float = 0.7) -> dict:
        """调用 chat/completions，返回原始 assistant message dict。

        messages: OpenAI 格式消息列表（system/user/assistant/tool）
        tools:    function calling 的 tool schema 列表，None 表示不启用
        """
        if not self.api_key:
            raise LLMError(
                "LLM_API_KEY 未配置。请复制 .env.example 为 .env 并填入 key，"
                "或在环境变量中设置后重试。"
            )
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"  # 由模型基于 schema 自主决策是否调用工具

        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        url = f"{self.base_url}/chat/completions"

        last_err: Exception = LLMError("unknown")
        for attempt in range(1, self.max_retries + 2):
            try:
                # 直接发请求，不自动跟随重定向，避免把 Authorization 带到别处
                with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                    resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]
                # 4xx 是请求本身的问题，重试无意义，直接报错
                if 400 <= resp.status_code < 500:
                    raise LLMError(f"LLM 请求被拒绝 HTTP {resp.status_code}: {resp.text[:300]}")
                last_err = LLMError(f"LLM 服务异常 HTTP {resp.status_code}: {resp.text[:300]}")
            except LLMError:
                raise
            except (httpx.TimeoutException, httpx.HTTPError) as e:
                last_err = LLMError(f"LLM 网络错误: {type(e).__name__}: {e}")
            if attempt <= self.max_retries:
                time.sleep(1.5 * attempt)  # 简单线性退避
        raise last_err
