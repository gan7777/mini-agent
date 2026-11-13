# -*- coding: utf-8 -*-
"""CLI 入口。

用法：
    python main.py                       # 默认 session（window-default）
    python main.py --session-id window-1 # 指定窗口，独立上下文，可随时续聊
"""
import argparse
import sys

from agent.loop import build_agent, repl


def main():
    parser = argparse.ArgumentParser(description="Mini Agent - 最小可用 Agent")
    parser.add_argument("--session-id", default="window-default",
                        help="会话 ID，不同 ID 相互隔离，同名可续聊")
    parser.add_argument("--quiet", action="store_true", help="不打印工具调用过程")
    args = parser.parse_args()

    try:
        agent = build_agent(verbose=not args.quiet)
    except Exception as e:  # noqa: BLE001
        print(f"启动失败: {e}", file=sys.stderr)
        sys.exit(1)

    repl(agent, session_id=args.session_id)


if __name__ == "__main__":
    main()
