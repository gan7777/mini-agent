# -*- coding: utf-8 -*-
"""Session 管理。

- Session = session_id + messages + todos + 元信息
- SessionStore 负责创建/读取/持久化：每个 session 一个 json 文件落在 sessions/ 目录，
  重启进程后用户可以随时接着原窗口继续聊（题目隐含的持久化要求）
- 不同 session_id 的 messages / todos 完全隔离
"""
import json
import os
import threading
import time
from typing import Dict, List, Optional

SYSTEM_PROMPT = (
    "你是一个能使用工具的智能助手。回答简洁准确。\n"
    "需要算数时用 calculator 工具；需要实时信息时用 search 工具；"
    "用户提到待办/任务安排时用 todo 工具。\n"
    "工具结果仅供你参考，最终要用自然语言回复用户。"
)


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        # todo 工具的状态挂在 session 上，天然按窗口隔离 + 随 session 落盘
        self.todos: dict = {"next_id": 1, "items": []}
        self.created_at = time.time()
        self.updated_at = self.created_at

    def append(self, msg: dict) -> None:
        self.messages.append(msg)
        self.updated_at = time.time()

    def user_messages(self) -> List[dict]:
        return [m for m in self.messages if m["role"] == "user"]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "todos": self.todos,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        s = cls.__new__(cls)
        s.session_id = d["session_id"]
        s.messages = d["messages"]
        s.todos = d.get("todos", {"next_id": 1, "items": []})
        s.created_at = d.get("created_at", time.time())
        s.updated_at = d.get("updated_at", s.created_at)
        return s


class SessionStore:
    def __init__(self, base_dir: str = "sessions"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self._cache: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def _path(self, session_id: str) -> str:
        # session_id 做一层文件名净化，防路径注入
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return os.path.join(self.base_dir, f"{safe}.json")

    def get(self, session_id: str) -> Session:
        """取出 session；磁盘上有就恢复（续聊），没有就新建。"""
        with self._lock:
            if session_id in self._cache:
                return self._cache[session_id]
            path = self._path(session_id)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    session = Session.from_dict(json.load(f))
            else:
                session = Session(session_id)
            self._cache[session_id] = session
            return session

    def save(self, session: Session) -> None:
        """每轮对话后落盘。写临时文件再原子替换，避免写一半损坏。"""
        with self._lock:
            path = self._path(session.session_id)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)

    def list_sessions(self) -> List[str]:
        if not os.path.isdir(self.base_dir):
            return []
        return sorted(
            f[:-5] for f in os.listdir(self.base_dir) if f.endswith(".json")
        )
