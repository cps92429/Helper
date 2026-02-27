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
    primary_colour: str = "&H00FFFFFF"  # BGR + alpha in ASS
    outline_colour: str = "&H00000000"
    back_colour: str = "&H64000000"
    bold: int = 0
    italic: int = 0
    outline: int = 2
    shadow: int = 1
    alignment: int = 2  # bottom-center
    margin_l: int = 80
    margin_r: int = 80
    margin_v: int = 60
    play_res_x: int = 1920
    play_res_y: int = 1080


def load_style(style_json: Optional[str], alignment: int) -> AssStyle:
    style = AssStyle(alignment=alignment)
    if not style_json:
        return style
    with open(style_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    for k, v in data.items():
        if hasattr(style, k):
            setattr(style, k, v)
    style.alignment = alignment
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


def srt_to_ass(srt_text: str, style: AssStyle) -> str:
    subs = list(srt.parse(srt_text))

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
            "Style: Default,{font},{size},{pri},&H000000FF,{outl},{back},{bold},{italic},0,0,100,100,0,0,1,"
            "{outline},{shadow},{align},{ml},{mr},{mv},1".format(
                font=style.fontname,
                size=style.fontsize,
                pri=style.primary_colour,
                outl=style.outline_colour,
                back=style.back_colour,
                bold=style.bold,
                italic=style.italic,
                outline=style.outline,
                shadow=style.shadow,
                align=style.alignment,
                ml=style.margin_l,
                mr=style.margin_r,
                mv=style.margin_v,
            ),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )

    events = []
    for item in subs:
        text = item.content.replace("\n", "\\N")
        events.append(
            "Dialogue: 0,{start},{end},Default,,0,0,0,,{text}".format(
                start=_fmt_time(item.start),
                end=_fmt_time(item.end),
                text=text,
            )
        )

    return header + "\n" + "\n".join(events) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input .srt path")
    parser.add_argument("--output", required=True, help="Output .ass path")
    parser.add_argument("--style-json", default="", help="Path to style.json (optional)")
    parser.add_argument("--alignment", type=int, default=2, help="ASS alignment (default 2=bottom-center)")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8-sig") as f:
        srt_text = f.read()

    style = load_style(args.style_json or None, alignment=int(args.alignment))
    ass_text = srt_to_ass(srt_text, style)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(ass_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
