#!/usr/bin/env python3
"""文件問答模組（簡易版）。"""

from __future__ import annotations

from pathlib import Path

DOCS_DIR = Path("docs")


def answer_from_docs(query: str) -> str:
    query = query.strip()
    if not query:
        return "請提供問題，例如：--query \"這份文件的重點是什麼？\""

    if not DOCS_DIR.exists():
        return "找不到 docs/ 目錄，請先建立並放入文件。"

    files = sorted([p for p in DOCS_DIR.iterdir() if p.is_file()])
    if not files:
        return "docs/ 目前沒有文件，請放入 PDF 或文字檔後再試。"

    file_names = ", ".join(p.name for p in files[:8])
    more = " ..." if len(files) > 8 else ""
    return (
        f"[RAG 模擬回應] 你問：{query}\n"
        f"目前可用文件：{file_names}{more}\n"
        "提示：可再接向量資料庫與 PDF 解析器以獲得真正檢索問答能力。"
    )
