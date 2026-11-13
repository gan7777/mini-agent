# -*- coding: utf-8 -*-
"""端到端冒烟测试：真实 LLM + 真实工具链路。

验证 6 项：
1. 基本对话 + 工具调用（todo add）
2. 带上下文的追问（接着上面记的待办问）
3. calculator 精确计算
4. search mock 链路
5. 两个 session 完全隔离

运行：python scripts/smoke_test.py
"""
import sys
import os
import time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # 保证 logs/sessions 输出落在项目根目录，无论从哪里启动

from agent.loop import build_agent

PASS, FAIL = "✅", "❌"
results = []


def check(name: str, cond: bool, detail: str = ""):
    results.append((name, cond, detail))
    print(f"{PASS if cond else FAIL} {name}" + (f"  -> {detail}" if detail else ""))


def main():
    # 每次运行用独立 session id：复用固定的 smoke-window-1 会让待办编号累加
    # （#1 -> #3），断言和"窗口2 看不到窗口1的待办"这一幕都会失真。
    run_id = time.strftime("%m%d-%H%M%S")
    tag1, tag2 = f"smoke-{run_id}-w1", f"smoke-{run_id}-w2"
    agent = build_agent(verbose=True)

    # ---------- 窗口 1 ----------
    s1 = agent.store.get(tag1)

    r1 = agent.run(s1, "帮我记一个待办：明天下午3点参加光辰智能面试")
    check("窗口1: todo 添加", "#1" in r1 and "面试" in r1, r1[:80])

    r2 = agent.run(s1, "我刚才让你记的待办是什么？")
    check("窗口1: 追问记得上下文", "面试" in r2, r2[:80])

    r3 = agent.run(s1, "帮我算一下 (128+72)*15/4 等于多少")
    check("窗口1: calculator 精确计算", "750" in r3, r3[:80])

    r4 = agent.run(s1, "帮我搜一下今天有什么科技新闻")
    # 断言断"工具链路走通"，不断"模型怎么措辞"——模型会把 mock 结果改写一遍，
    # 用最终答案匹配原文会 flaky（同样输入换个说法就红）
    tool_outputs = [m.get("content") or "" for m in s1.messages if m.get("role") == "tool"]
    served = any("的结果" in c for c in tool_outputs)
    check("窗口1: search mock 链路", served and bool(r4.strip()),
          f"tool_served={served} | {r4[:60]}")

    # ---------- 窗口 2（隔离性） ----------
    s2 = agent.store.get(tag2)
    r5 = agent.run(s2, "我现在有哪些待办？")
    check("窗口2: 看不到窗口1的待办", ("没有任何待办" in r5) or ("光辰" not in r5), r5[:80])

    # ---------- 持久化 ----------
    agent.store.save(s1)
    s1_reloaded = agent.store.get(tag1)
    check("持久化: 重启后 session 还在", len(s1_reloaded.messages) == len(s1.messages))

    print("\n========== 结果 ==========")
    ok = sum(1 for _, c, _ in results if c)
    print(f"{ok}/{len(results)} 通过")
    print(f"trace 日志: logs/trace.jsonl ({os.path.getsize('logs/trace.jsonl')} bytes)")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
