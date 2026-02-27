import argparse
from dataclasses import dataclass
from datetime import timedelta
from typing import List, Tuple

import srt


def _cps(text: str, duration_s: float) -> float:
    t = "".join(text.split())
    if duration_s <= 0.001:
        return 999.0
    return len(t) / duration_s


def _is_cjk(text: str) -> bool:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return True
    return False


def _smart_line_break(text: str, max_len: int = 22) -> str:
    text = " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split()).strip()
    if len(text) <= max_len:
        return text

    if _is_cjk(text):
        a = text[:max_len].strip()
        b = text[max_len : max_len * 2].strip()
        return (a + "\n" + b).strip()

    parts: List[str] = []
    s = text
    while len(s) > max_len and len(parts) < 2:
        cut = s.rfind(" ", 0, max_len)
        if cut == -1:
            cut = max_len
        parts.append(s[:cut].strip())
        s = s[cut:].strip()
    if s and len(parts) < 2:
        parts.append(s)
    return "\n".join(parts[:2]).strip()


def _pick_split(text: str) -> int:
    s = text.strip()
    if not s:
        return 0
    mid = len(s) // 2
    punct = "。！？；：，,.-—…"
    # Look for punctuation near mid.
    for radius in range(0, 18):
        for pos in (mid - radius, mid + radius):
            if 1 <= pos < len(s) - 1 and s[pos] in punct:
                return pos + 1
    # Fallback: nearest space.
    for radius in range(0, 18):
        for pos in (mid - radius, mid + radius):
            if 1 <= pos < len(s) - 1 and s[pos].isspace():
                return pos + 1
    return mid


def _proportional_split_times(start: timedelta, end: timedelta, a_len: int, b_len: int) -> Tuple[timedelta, timedelta]:
    total = max(1, a_len + b_len)
    duration = (end - start).total_seconds()
    a_s = max(0.3, duration * (a_len / total))
    a_end = start + timedelta(seconds=a_s)
    return a_end, end


def _semantic_merge(subs: List[srt.Subtitle]) -> List[srt.Subtitle]:
    # Borrowed idea from auto_subtitle_pro4.py: merge adjacent cues into semantic chunks.
    merged: List[srt.Subtitle] = []
    buf: srt.Subtitle | None = None

    def flush() -> None:
        nonlocal buf
        if buf is not None:
            merged.append(buf)
        buf = None

    for sub in subs:
        if buf is None:
            buf = sub
            continue

        gap = (sub.start - buf.end).total_seconds()
        total_dur = (sub.end - buf.start).total_seconds()
        combined_text = (buf.content.rstrip() + " " + sub.content.lstrip()).strip()

        # Merge if short enough and near-contiguous.
        if gap <= 0.25 and total_dur <= 6.0 and len("".join(combined_text.split())) <= 40:
            buf = srt.Subtitle(index=buf.index, start=buf.start, end=sub.end, content=combined_text)
            continue

        flush()
        buf = sub

    flush()
    return merged


def smart_segment(subs: List[srt.Subtitle]) -> List[srt.Subtitle]:
    # Heuristic targets (good readability):
    # - Avoid too-short cues
    # - Keep cps reasonable
    # - Prefer splitting on punctuation, merging tiny adjacent cues
    # Step 1: semantic merge to reduce choppiness.
    out: List[srt.Subtitle] = _semantic_merge(subs)

    def can_merge(prev: srt.Subtitle, cur: srt.Subtitle) -> bool:
        gap = (cur.start - prev.end).total_seconds()
        if gap > 0.15:
            return False
        merged_text = (prev.content.rstrip() + " " + cur.content.lstrip()).strip()
        merged_dur = (cur.end - prev.start).total_seconds()
        if merged_dur < 0.8:
            return False
        if len(merged_text) > 90:
            return False
        if _cps(merged_text, merged_dur) > 20:
            return False
        return True

    for sub in subs:
        if out and can_merge(out[-1], sub):
            prev = out.pop()
            out.append(
                srt.Subtitle(
                    index=prev.index,
                    start=prev.start,
                    end=sub.end,
                    content=(prev.content.rstrip() + "\n" + sub.content.lstrip()).strip(),
                )
            )
            continue

        out.append(sub)

    # Step 2: split long / high-cps cues
    final: List[srt.Subtitle] = []
    for sub in out:
        dur = (sub.end - sub.start).total_seconds()
        text = sub.content.strip()
        if not text:
            continue

        too_fast = _cps(text, dur) > 20
        too_long = len("".join(text.split())) > 80
        if not (too_fast or too_long):
            final.append(srt.Subtitle(index=sub.index, start=sub.start, end=sub.end, content=_smart_line_break(text)))
            continue

        split_at = _pick_split(text)
        a = text[:split_at].strip()
        b = text[split_at:].strip()
        if not a or not b:
            final.append(sub)
            continue

        a_end, end = _proportional_split_times(sub.start, sub.end, len(a), len(b))
        final.append(srt.Subtitle(index=sub.index, start=sub.start, end=a_end, content=_smart_line_break(a)))
        final.append(srt.Subtitle(index=sub.index + 1, start=a_end, end=end, content=_smart_line_break(b)))

    # Reindex
    for i, sub in enumerate(final, start=1):
        sub.index = i
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input .srt")
    parser.add_argument("--output", required=True, help="Output .srt")
    parser.add_argument("--max-len", type=int, default=22, help="Max chars per line (approx)")
    args = parser.parse_args()

    text = open(args.input, "r", encoding="utf-8-sig").read()
    subs = list(srt.parse(text))
    # max-len currently affects line-breaking only; keep signature stable for callers.
    global _smart_line_break
    original = _smart_line_break
    _smart_line_break = lambda t, max_len=args.max_len: original(t, max_len=max_len)  # type: ignore
    out = smart_segment(subs)
    open(args.output, "w", encoding="utf-8").write(srt.compose(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
