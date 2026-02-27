import argparse
import json
import os
from dataclasses import dataclass
from typing import Optional

import srt


@dataclass
class AssStyle:
    fontname: str = "Microsoft JhengHei"
    fontsize: int = 48
    primary_colour: str = "&H00FFFFFF"
    outline_colour: str = "&H00000000"
    back_colour: str = "&H64000000"
    bold: int = 0
    italic: int = 0
    outline: int = 2
    shadow: int = 1
    margin_l: int = 80
    margin_r: int = 80
    margin_v_bottom: int = 60
    margin_v_top: int = 60
    play_res_x: int = 1920
    play_res_y: int = 1080


def load_style(style_json: Optional[str]) -> AssStyle:
    style = AssStyle()
    if not style_json:
        return style
    with open(style_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    for k, v in data.items():
        if hasattr(style, k):
            setattr(style, k, v)
    return style


def _fmt_time(td) -> str:
    total_ms = int(td.total_seconds() * 1000)
    cs = (total_ms % 1000) // 10
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def bilingual_srt_to_ass(en_srt_text: str, zh_srt_text: str, style: AssStyle) -> str:
    en_subs = sorted(list(srt.parse(en_srt_text)), key=lambda x: x.start)
    zh_subs = sorted(list(srt.parse(zh_srt_text)), key=lambda x: x.start)
    n = min(len(en_subs), len(zh_subs))

    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {style.play_res_x}",
            f"PlayResY: {style.play_res_y}",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
            # Top style (alignment 8)
            "Style: Top,{font},{size},{pri},&H000000FF,{outl},{back},{bold},{italic},0,0,100,100,0,0,1,"
            "{outline},{shadow},8,{ml},{mr},{mv},1".format(
                font=style.fontname,
                size=style.fontsize,
                pri=style.primary_colour,
                outl=style.outline_colour,
                back=style.back_colour,
                bold=style.bold,
                italic=style.italic,
                outline=style.outline,
                shadow=style.shadow,
                ml=style.margin_l,
                mr=style.margin_r,
                mv=style.margin_v_top,
            ),
            # Bottom style (alignment 2)
            "Style: Bottom,{font},{size},{pri},&H000000FF,{outl},{back},{bold},{italic},0,0,100,100,0,0,1,"
            "{outline},{shadow},2,{ml},{mr},{mv},1".format(
                font=style.fontname,
                size=style.fontsize,
                pri=style.primary_colour,
                outl=style.outline_colour,
                back=style.back_colour,
                bold=style.bold,
                italic=style.italic,
                outline=style.outline,
                shadow=style.shadow,
                ml=style.margin_l,
                mr=style.margin_r,
                mv=style.margin_v_bottom,
            ),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )

    events = []
    for i in range(n):
        en = en_subs[i]
        zh = zh_subs[i]
        start = _fmt_time(min(en.start, zh.start))
        end = _fmt_time(max(en.end, zh.end))

        en_text = en.content.replace("\n", "\\N")
        zh_text = zh.content.replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start},{end},Top,,0,0,0,,{en_text}")
        events.append(f"Dialogue: 0,{start},{end},Bottom,,0,0,0,,{zh_text}")

    return header + "\n" + "\n".join(events) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--en-srt", required=True, help="English (or original) SRT path")
    parser.add_argument("--zh-srt", required=True, help="Traditional Chinese SRT path")
    parser.add_argument("--output", required=True, help="Output ASS path")
    parser.add_argument("--style-json", default="", help="Path to style.json (optional)")
    args = parser.parse_args()

    with open(args.en_srt, "r", encoding="utf-8-sig") as f:
        en_text = f.read()
    with open(args.zh_srt, "r", encoding="utf-8-sig") as f:
        zh_text = f.read()

    style = load_style(args.style_json or None)
    ass_text = bilingual_srt_to_ass(en_text, zh_text, style)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(ass_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

