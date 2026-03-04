#!/usr/bin/env python3
"""主任務入口：整合 RAG、程式輔助與本地模型工具。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from code_helper import review_code
from rag_helper import answer_from_docs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地 AI 任務入口")
    parser.add_argument(
        "--task",
        choices=("rag", "code", "local"),
        required=True,
        help="要執行的任務類型",
    )
    parser.add_argument("--query", default="", help="RAG 問題")
    parser.add_argument("--code", default="", help="要分析的程式碼片段")
    parser.add_argument("--prompt", default="", help="local_ai.py 使用的提示文字")
    return parser.parse_args()


def run_local_model(prompt: str) -> int:
    if not prompt.strip():
        print("請提供 --prompt")
        return 1

    cmd = [sys.executable, "local_ai.py", "--prompt", prompt]
    print(f"執行本地模型：{' '.join(cmd)}")
    return subprocess.call(cmd)


def main() -> None:
    args = parse_args()

    if args.task == "rag":
        print(answer_from_docs(args.query))
        return

    if args.task == "code":
        print(review_code(args.code))
        return

    if args.task == "local":
        raise SystemExit(run_local_model(args.prompt))


if __name__ == "__main__":
    main()
