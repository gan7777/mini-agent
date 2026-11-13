# -*- coding: utf-8 -*-
"""Trace 日志测试。"""
import json
import os

from agent.loop import TraceLogger


def test_trace_writes_jsonl(tmp_path):
    tl = TraceLogger(log_dir=str(tmp_path))
    tl.log("w1", {"iter": 1, "event": "tool_call", "tool": "todo", "cost_ms": 3})
    tl.log("w1", {"iter": 2, "event": "final_answer", "answer": "done"})

    path = str(tmp_path / "trace.jsonl")
    with open(path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    assert len(records) == 2
    assert records[0]["session"] == "w1"
    assert records[0]["tool"] == "todo"
    assert records[1]["event"] == "final_answer"
    assert "ts" in records[0]  # 带时间戳
