#!/usr/bin/env python3
"""程式輔助模組（簡易靜態建議）。"""

from __future__ import annotations


def review_code(code: str) -> str:
    text = code.strip()
    if not text:
        return "請透過 --code 提供要分析的程式碼片段。"

    suggestions: list[str] = []
    if "print(" in text:
        suggestions.append("可考慮將部分 print 改為 logging，便於正式環境追蹤。")
    if "except Exception" in text:
        suggestions.append("建議縮小例外範圍，避免吞掉非預期錯誤。")
    if "TODO" in text.upper():
        suggestions.append("偵測到 TODO，建議建立 issue 追蹤。")

    if not suggestions:
        suggestions.append("程式碼可讀性不錯，建議補上型別註記與單元測試。")

    return "[Code Helper 建議]\n- " + "\n- ".join(suggestions)
