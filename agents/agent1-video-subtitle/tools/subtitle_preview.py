import argparse
import tkinter as tk
from tkinter import ttk

import srt


def load_subtitles(path: str):
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    return list(srt.parse(text))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subtitles", required=True, help="Path to .srt")
    args = parser.parse_args()

    subs = load_subtitles(args.subtitles)

    root = tk.Tk()
    root.title("字幕預覽 (SRT)")
    root.geometry("980x680")

    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(fill="both", expand=True)

    cols = ("start", "end", "text")
    tree = ttk.Treeview(main_frame, columns=cols, show="headings")
    tree.heading("start", text="開始")
    tree.heading("end", text="結束")
    tree.heading("text", text="字幕")
    tree.column("start", width=140, anchor="w")
    tree.column("end", width=140, anchor="w")
    tree.column("text", width=640, anchor="w")

    vsb = ttk.Scrollbar(main_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")

    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(0, weight=1)

    for item in subs:
        tree.insert(
            "",
            "end",
            values=(
                str(item.start),
                str(item.end),
                item.content.replace("\n", " / "),
            ),
        )

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

