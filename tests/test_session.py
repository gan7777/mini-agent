# -*- coding: utf-8 -*-
"""Session 隔离与持久化测试。"""
from agent.session import Session, SessionStore
from agent.tools import todo_tool


def test_sessions_are_isolated(tmp_path):
    store = SessionStore(base_dir=str(tmp_path / "s"))
    w1 = store.get("window-1")
    w2 = store.get("window-2")

    # 窗口1 记待办，窗口2 不可见
    todo_tool.handler({"action": "add", "content": "窗口1的秘密待办"}, w1)
    todo_tool.handler({"action": "add", "content": "窗口2的待办"}, w2)

    assert len(w1.todos["items"]) == 1
    assert w1.todos["items"][0]["content"] == "窗口1的秘密待办"
    assert w2.todos["items"][0]["content"] == "窗口2的待办"
    # messages 也隔离（各自只有 system）
    assert len(w1.messages) == 1 and len(w2.messages) == 1


def test_persistence_across_restart(tmp_path):
    """模拟重启：新 store 实例从磁盘恢复同一个 session，可续聊。"""
    base = str(tmp_path / "s")

    store1 = SessionStore(base_dir=base)
    s1 = store1.get("window-1")
    s1.append({"role": "user", "content": "昨天聊到哪了之前的问题"})
    s1.append({"role": "assistant", "content": "我们聊了天气"})
    todo_tool.handler({"action": "add", "content": "买牛奶"}, s1)
    store1.save(s1)

    store2 = SessionStore(base_dir=base)  # 相当于重启后的新进程
    s2 = store2.get("window-1")

    assert s2.session_id == "window-1"
    assert len(s2.user_messages()) == 1
    assert s2.messages[-1]["content"] == "我们聊了天气"
    assert s2.todos["items"] == [{"id": 1, "content": "买牛奶", "done": False}]
    # 恢复后的 session 继续追加，与重启前文件内容连贯
    s2.append({"role": "user", "content": "继续刚才的话题"})
    assert s2.user_messages()[-1]["content"] == "继续刚才的话题"


def test_session_id_sanitized(tmp_path):
    """session_id 含非法字符时不产生路径逃逸。"""
    store = SessionStore(base_dir=str(tmp_path / "s"))
    s = store.get("../../evil")
    store.save(s)
    import os
    files = os.listdir(str(tmp_path / "s"))
    assert files == ["______evil.json"]  # 全部被净化为下划线


def test_atomic_save(tmp_path):
    store = SessionStore(base_dir=str(tmp_path / "s"))
    s = store.get("w")
    store.save(s)
    import os, json
    path = str(tmp_path / "s" / "w.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["session_id"] == "w"
    assert not os.path.exists(path + ".tmp")  # 临时文件已原子替换
