import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import srt


@dataclass
class TranslateItem:
    id: int
    text: str


def _wrap_zh_tw(text: str, max_line_chars: int = 18, max_lines: int = 2) -> str:
    # Subtitle-friendly wrapping:
    # - Prefer existing line breaks when they are already short enough.
    # - Otherwise reflow into up to two lines by character count.
    s = " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())
    if not s:
        return ""

    if "\n" in text:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines and all(len(ln) <= max_line_chars for ln in lines) and len(lines) <= max_lines:
            return "\n".join(lines)

    # Simple greedy wrap.
    out_lines: List[str] = []
    i = 0
    while i < len(s) and len(out_lines) < max_lines:
        remaining_lines = max_lines - len(out_lines)
        remaining_chars = len(s) - i
        if remaining_lines == 1:
            out_lines.append(s[i:].strip())
            break

        # Try to break around punctuation close to the limit.
        take = min(max_line_chars, remaining_chars)
        chunk = s[i : i + take]
        break_pos = -1
        for j in range(len(chunk) - 1, max(0, len(chunk) - 8), -1):
            if chunk[j] in "，。！？；：、)" or chunk[j] == " ":
                break_pos = j + 1
                break
        if break_pos <= 0:
            break_pos = take

        out_lines.append(s[i : i + break_pos].strip())
        i += break_pos

    return "\n".join(out_lines).strip()

def _opencc_convert(text: str, config: str) -> str:
    try:
        from opencc import OpenCC  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "缺少 OpenCC 套件，無法進行繁體中文強制轉換。\n"
            "請先執行：.\\setup.ps1 -Target Agent1\n"
            f"原始錯誤：{e}"
        )

    cc = OpenCC(config)
    return cc.convert(text)


def _extract_json_array(text: str) -> List[dict]:
    # Copilot may occasionally add extra newlines; extract the first JSON array.
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model output does not contain a JSON array.")
    return json.loads(text[start : end + 1])


def _run_copilot_prompt(prompt: str, model: str) -> str:
    # Use GitHub Copilot CLI via `gh copilot -- ...` to avoid handling tokens directly.
    # `-s` makes it suitable for scripting (only the model response).
    cmd = [
        "gh",
        "copilot",
        "--",
        "-p",
        prompt,
        "-s",
        "--log-level",
        "error",
        "--no-custom-instructions",
        "--model",
        model,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "Authentication failed" in stderr or "copilot login" in stderr:
            raise RuntimeError(
                "Copilot CLI 驗證失敗。\n\n"
                "請先完成一次 Copilot CLI 登入（只需做一次）：\n"
                "  1) 在 PowerShell 執行：gh copilot -- login\n"
                "  2) 依提示用瀏覽器完成 OAuth device flow\n\n"
                "或改用環境變數提供 Token（需具備 Fine-grained PAT 的 Copilot Requests 權限）：\n"
                "  - COPILOT_GITHUB_TOKEN\n"
                "  - GH_TOKEN\n"
                "  - GITHUB_TOKEN\n\n"
                f"原始錯誤：{stderr}"
            )
        raise RuntimeError(f"Copilot CLI failed (exit={proc.returncode}): {stderr}")
    return proc.stdout.strip()


def _build_prompt(items: List[TranslateItem]) -> str:
    payload = [{"id": it.id, "text": it.text} for it in items]
    return (
        "你是專業的影片字幕譯者。請把下列 JSON 陣列中的 text 翻譯成「繁體中文（台灣用語）」，"
        "語氣自然、像人工翻譯、用詞精準，避免直翻或機翻感。\n"
        "要求：\n"
        "1) 只輸出 JSON 陣列，不要 Markdown，不要解釋。\n"
        "2) 保留每個項目的 id，不要改動 id。\n"
        "3) 請輸出格式：[{\"id\":1,\"translation\":\"...\"}, ...]\n"
        "4) 不要使用簡體字；必要時用台灣常用詞（例如：影片/字幕/軟體）。\n"
        "5) 保留專有名詞、縮寫、數字、單位、URL。\n"
        "6) 字幕可讀性：每個 translation 最多兩行，以 \\n 換行；盡量精簡但不丟意思。\n"
        "7) 若原文含有換行，請合理保留或重新分行。\n"
        "8) 不要新增額外內容（例如：註解、括號說明）。\n\n"
        "輸入：\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n"
    )


def translate_items(
    items: List[TranslateItem],
    model: str,
    batch_chars: int,
    max_line_chars: int,
    opencc_config: str,
) -> Dict[int, str]:
    translations: Dict[int, str] = {}
    batch: List[TranslateItem] = []
    batch_len = 0

    def flush():
        nonlocal batch, batch_len
        if not batch:
            return
        out = _run_copilot_prompt(_build_prompt(batch), model=model)
        arr = _extract_json_array(out)
        id_to_tr: Dict[int, str] = {}
        for obj in arr:
            if "id" not in obj or "translation" not in obj:
                continue
            try:
                id_to_tr[int(obj["id"])] = str(obj["translation"])
            except Exception:
                continue
        for it in batch:
            tr = id_to_tr.get(it.id, "")
            tr = _opencc_convert(tr, opencc_config) if opencc_config else tr
            translations[it.id] = _wrap_zh_tw(tr, max_line_chars=max_line_chars, max_lines=2)
        batch = []
        batch_len = 0

    for it in items:
        tlen = len(it.text)
        if batch and (batch_len + tlen > batch_chars):
            flush()
        batch.append(it)
        batch_len += tlen

    flush()
    return translations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input .srt path")
    parser.add_argument("--output", required=True, help="Output .srt path (zh-TW)")
    parser.add_argument("--model", default="gpt-4.1", help="Copilot CLI model (default: gpt-4.1)")
    parser.add_argument("--batch-chars", type=int, default=2500, help="Approx chars per request")
    parser.add_argument("--max-line-chars", type=int, default=18, help="Wrap translation line length")
    parser.add_argument(
        "--opencc",
        default="s2twp",
        help="OpenCC config for zh conversion (default: s2twp). Use empty string to disable.",
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8-sig") as f:
        srt_text = f.read()

    subs = list(srt.parse(srt_text))
    items: List[TranslateItem] = []
    for idx, sub in enumerate(subs, start=1):
        items.append(TranslateItem(id=idx, text=sub.content))

    id_to_translation = translate_items(
        items,
        model=args.model,
        batch_chars=args.batch_chars,
        max_line_chars=args.max_line_chars,
        opencc_config=str(args.opencc or ""),
    )

    out_subs: List[srt.Subtitle] = []
    for idx, sub in enumerate(subs, start=1):
        tr = id_to_translation.get(idx, sub.content)
        out_subs.append(
            srt.Subtitle(index=sub.index, start=sub.start, end=sub.end, content=tr)
        )

    out_text = srt.compose(out_subs)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(out_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
