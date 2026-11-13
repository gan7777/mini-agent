# -*- coding: utf-8 -*-
"""todo 工具（题目必做项）。

一个工具带 action 参数实现 add/list/complete 三个动作，
todo 状态存在 session 上（session.todos），随 session 持久化，天然按窗口隔离。
"""
from .registry import Tool


def _todo_handler(args: dict, session) -> str:
    action = args["action"]
    todos = session.todos  # 直接挂在 session 上，随 session.json 落盘

    if action == "add":
        content = args["content"].strip()
        if not content:
            return "错误：待办内容不能为空"
        todo_id = todos["next_id"]
        todos["next_id"] += 1
        todos["items"].append({"id": todo_id, "content": content, "done": False})
        return f"已添加待办 #{todo_id}: {content}（当前共 {len(todos['items'])} 条待办）"

    if action == "list":
        if not todos["items"]:
            return "当前没有任何待办"
        lines = []
        for t in todos["items"]:
            mark = "x" if t["done"] else " "
            lines.append(f"[{mark}] #{t['id']} {t['content']}")
        return "当前待办列表：\n" + "\n".join(lines)

    if action == "complete":
        tid = args["todo_id"]
        for t in todos["items"]:
            if t["id"] == tid:
                if t["done"]:
                    return f"待办 #{tid} 已经是完成状态"
                t["done"] = True
                return f"已完成待办 #{tid}: {t['content']}"
        return f"错误：找不到待办 #{tid}，可用 list 先查看"

    return f"错误：未知 action {action}，只支持 add/list/complete"


todo_tool = Tool(
    name="todo",
    description="管理用户的待办事项。支持添加(add)、查看(list)、完成(complete)。",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "complete"],
                "description": "操作类型：add 添加、list 查看全部、complete 标记完成",
            },
            "content": {
                "type": "string",
                "description": "action=add 时必填，待办内容",
            },
            "todo_id": {
                "type": "integer",
                "description": "action=complete 时必填，待办编号",
            },
        },
        "required": ["action"],
    },
    handler=_todo_handler,
)
