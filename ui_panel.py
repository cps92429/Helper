#!/usr/bin/env python3
"""Streamlit 任務總管面板。"""

from __future__ import annotations

from code_helper import review_code
from rag_helper import answer_from_docs


def run() -> None:
    try:
        import streamlit as st
    except ImportError:
        raise SystemExit("未安裝 streamlit，請先執行：pip install streamlit")

    st.set_page_config(page_title="本地AI 任務總管", layout="wide")
    st.title("本地AI 任務總管")

    tab_rag, tab_code = st.tabs(["文件問答 (RAG)", "程式輔助"])

    with tab_rag:
        q = st.text_input("輸入問題")
        if st.button("查詢文件"):
            st.write(answer_from_docs(q))

    with tab_code:
        snippet = st.text_area("貼上程式碼", height=220)
        if st.button("分析程式碼"):
            st.write(review_code(snippet))


if __name__ == "__main__":
    run()
