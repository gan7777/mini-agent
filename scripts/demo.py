# -*- coding: utf-8 -*-
"""一键演示脚本：把笔试题的每个要求"演"一遍。

运行：python scripts/demo.py
（会真实调用 LLM，请确保已配置 LLM_API_KEY 或 DASHSCOPE_API_KEY）

演示顺序严格对应题目要求：
  1. 一次输入触发多个工具（天气 + 待办）
  2. 追问记得上下文
  3. 窗口隔离：窗口 2 看不到窗口 1 的待办
  4. 各窗口独立记忆
  5. 重启进程后接续对话（持久化）
  6. context 压缩（低阈值触发，直观看到摘要）
  7. 工具异常不崩溃
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from agent.loop import build_agent  # noqa: E402


def banner(step: str, title: str):
    print("\n" + "=" * 66)
    print(f"  {step}  {title}")
    print("=" * 66)


def ask(agent, session, text: str):
    print(f"\n👤 用户: {text}")
    reply = agent.run(session, text)
    print(f"🤖 Agent: {reply}")


def reset_demo_sessions():
    """清掉上次演示残留的 session，保证每次演示都是干净开局。"""
    from pathlib import Path
    for p in Path("sessions").glob("demo-*.json"):
        p.unlink()


def main():
    print("Mini Agent 演示 —— 从零实现的最小可用 Agent（无 agent 框架）")
    reset_demo_sessions()

    agent = build_agent(verbose=True)

    banner("[1/7]", "窗口1：一次输入触发两个工具（查天气 + 记待办）")
    w1 = agent.store.get("demo-window-1")
    ask(agent, w1, "杭州今天天气怎么样？顺便帮我记个待办：明天下午3点参加光辰智能面试")

    banner("[2/7]", "窗口1：追问（上下文里既有对话也有工具结果）")
    ask(agent, w1, "那我明天有什么安排？出门要带伞吗？")

    banner("[3/7]", "窗口2：完全独立的 session，看不到窗口1的任何内容")
    w2 = agent.store.get("demo-window-2")
    ask(agent, w2, "我现在有哪些待办？")

    banner("[4/7]", "窗口2：各自记录，互不干扰")
    ask(agent, w2, "帮我记个待办：周五前把周报发给组长")
    ask(agent, w2, "列一下我的待办")
    ask(agent, w1, "也列一下我的待办")

    banner("[5/7]", "模拟进程重启：重新构造 Agent，从磁盘恢复 session 继续聊")
    agent2 = build_agent(verbose=True)
    w1_restored = agent2.store.get("demo-window-1")
    print(f"（从 sessions/demo-window-1.json 恢复了 {len(w1_restored.messages)} 条消息）")
    ask(agent2, w1_restored, "刚才那条待办再确认一下，别忘了")

    banner("[6/7]", "工具异常不崩溃：3 除以 0")
    ask(agent2, w1_restored, "帮我算一下 3 除以 0 等于多少")

    banner("[7/7]", "Context 压缩：把阈值调到 120 token，多聊几轮就能看到摘要介入")
    os.environ["AGENT_CONTEXT_MAX_TOKENS"] = "120"
    agent3 = build_agent(verbose=True)
    w3 = agent3.store.get("demo-compress")
    for q in ["我叫甘荣丰，在准备光辰智能的 Agent 岗位笔试",
              "我的项目是一个 RAG 客服机器人，用了 Chroma 和 qwen-max",
              "帮我记个待办：今晚把 README 的 memory 部分写完",
              "我刚才说我的项目用了什么向量库？"]:
        ask(agent3, w3, q)

    print("\n---- 压缩后的 messages 结构（可以看到摘要消息位置）----")
    for i, m in enumerate(w3.messages):
        content = str(m.get("content") or "")[:70].replace("\n", " ")
        print(f"  {i}. [{m['role']}] {content}")
        if i > 6:
            print("  ...")
            break

    print("\n---- logs/trace.jsonl 最近 3 条 ----")
    with open(os.path.join("logs", "trace.jsonl"), encoding="utf-8") as f:
        for line in f.readlines()[-3:]:
            print("  " + line.strip()[:160])

    print("\n演示结束。以上全部行为均可在 logs/trace.jsonl 中复查。")


if __name__ == "__main__":
    main()
