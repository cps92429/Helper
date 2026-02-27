import sys
import time
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def _agent_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _repo_root(agent_dir: Path) -> Path:
    return agent_dir.parents[1]


def _format_srt_ts(seconds: float) -> str:
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds) % 60
    m = int(seconds) // 60 % 60
    h = int(seconds) // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


class RealtimeStudio(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Agent1 即時聽打（Realtime）")
        self.geometry("980x640")

        self._agent_dir = _agent_dir()
        self._repo_root = _repo_root(self._agent_dir)
        if str(self._agent_dir) not in sys.path:
            sys.path.insert(0, str(self._agent_dir))

        from studio.services.realtime import RealtimeTranscriber, list_input_devices  # noqa: E402

        self._RealtimeTranscriber = RealtimeTranscriber
        self._list_input_devices = list_input_devices

        self._rt = None
        self._start_wall: Optional[float] = None

        self._build_ui()
        self.after(120, self._poll_segments)

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="模型").grid(row=0, column=0, sticky="w")
        self.model_var = tk.StringVar(value="base")
        ttk.Combobox(top, textvariable=self.model_var, values=["tiny", "base", "small", "medium"], width=10, state="readonly").grid(
            row=0, column=1, sticky="w", padx=(6, 18)
        )

        ttk.Label(top, text="語言").grid(row=0, column=2, sticky="w")
        self.lang_var = tk.StringVar(value="auto")
        ttk.Combobox(top, textvariable=self.lang_var, values=["auto", "zh", "en", "ja", "ko"], width=8, state="readonly").grid(
            row=0, column=3, sticky="w", padx=(6, 18)
        )

        ttk.Label(top, text="Chunk(秒)").grid(row=0, column=4, sticky="w")
        self.chunk_var = tk.StringVar(value="2.0")
        ttk.Entry(top, textvariable=self.chunk_var, width=8).grid(row=0, column=5, sticky="w", padx=(6, 18))

        ttk.Label(top, text="裝置").grid(row=0, column=6, sticky="w")
        self.dev_var = tk.StringVar(value="(預設)")
        self.dev_combo = ttk.Combobox(top, textvariable=self.dev_var, width=40, state="readonly")
        self.dev_combo.grid(row=0, column=7, sticky="w", padx=(6, 18))
        self._refresh_devices()

        btns = ttk.Frame(top)
        btns.grid(row=0, column=8, sticky="e")

        self.start_btn = ttk.Button(btns, text="開始", command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn = ttk.Button(btns, text="停止", command=self._stop, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=4)
        self.save_srt_btn = ttk.Button(btns, text="另存 SRT", command=self._save_srt)
        self.save_srt_btn.pack(side=tk.LEFT, padx=4)
        self.save_txt_btn = ttk.Button(btns, text="另存 TXT", command=self._save_txt)
        self.save_txt_btn.pack(side=tk.LEFT, padx=4)

        self.status = tk.StringVar(value="就緒")
        status_row = ttk.Frame(self, padding=(10, 0, 10, 6))
        status_row.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(status_row, textvariable=self.status).pack(side=tk.LEFT)
        self.busy = ttk.Progressbar(status_row, mode="indeterminate", length=160)
        self.busy.pack(side=tk.RIGHT)

        mid = ttk.Frame(self, padding=(10, 0, 10, 10))
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.text = tk.Text(mid, wrap="word", font=("Segoe UI", 11))
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(mid, command=self.text.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=sb.set)

    def _refresh_devices(self) -> None:
        items = ["(預設)"]
        self._device_map = {"(預設)": None}
        for idx, name in self._list_input_devices():
            label = f"{idx}: {name}"
            items.append(label)
            self._device_map[label] = idx
        self.dev_combo["values"] = items
        if self.dev_var.get() not in items:
            self.dev_var.set("(預設)")

    def _start(self) -> None:
        if self._rt and self._rt.is_running():
            return
        try:
            chunk = float(self.chunk_var.get().strip())
            if chunk <= 0.5:
                raise ValueError("chunk too small")
        except Exception:
            messagebox.showerror("參數錯誤", "Chunk(秒) 需要是 >= 0.5 的數字。")
            return

        dev = self._device_map.get(self.dev_var.get(), None)
        try:
            self._rt = self._RealtimeTranscriber(
                model_size=self.model_var.get(),
                language=self.lang_var.get(),
                chunk_seconds=chunk,
                device=dev,
            )
            self._rt.start()
            self._start_wall = time.time()
        except Exception as e:
            messagebox.showerror("啟動失敗", str(e))
            self._rt = None
            return

        self.status.set("聽打中...（可先說幾句話測試）")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.busy.start(12)

    def _stop(self) -> None:
        if self._rt:
            self._rt.stop()
        self.status.set("已停止")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        try:
            self.busy.stop()
        except Exception:
            pass

    def _poll_segments(self) -> None:
        try:
            if self._rt:
                while True:
                    seg = self._rt.get_segment_nowait()
                    if seg is None:
                        break
                    self._append_segment(seg.start, seg.end, seg.text)
        finally:
            self.after(120, self._poll_segments)

    def _append_segment(self, start: float, end: float, text: str) -> None:
        line = f"[{_format_srt_ts(start)} - {_format_srt_ts(end)}] {text}\n"
        self.text.insert("end", line)
        self.text.see("end")

    def _save_srt(self) -> None:
        if not self._rt or not self._rt.segments:
            messagebox.showinfo("無內容", "目前沒有可輸出的段落。")
            return

        initial = str(self._repo_root / "Output" / "realtime.srt")
        path = filedialog.asksaveasfilename(
            title="另存 SRT",
            defaultextension=".srt",
            filetypes=[("SRT", "*.srt")],
            initialfile=Path(initial).name,
            initialdir=str(Path(initial).parent),
        )
        if not path:
            return

        lines = []
        for i, seg in enumerate(self._rt.segments, start=1):
            lines.append(str(i))
            lines.append(f"{_format_srt_ts(seg.start)} --> {_format_srt_ts(seg.end)}")
            lines.append(seg.text)
            lines.append("")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        messagebox.showinfo("完成", f"已輸出：{path}")

    def _save_txt(self) -> None:
        if not self._rt or not self._rt.segments:
            messagebox.showinfo("無內容", "目前沒有可輸出的段落。")
            return

        initial = str(self._repo_root / "Output" / "realtime.txt")
        path = filedialog.asksaveasfilename(
            title="另存 TXT",
            defaultextension=".txt",
            filetypes=[("Text", "*.txt")],
            initialfile=Path(initial).name,
            initialdir=str(Path(initial).parent),
        )
        if not path:
            return

        text = "\n".join(seg.text for seg in self._rt.segments if seg.text.strip())
        Path(path).write_text(text + "\n", encoding="utf-8")
        messagebox.showinfo("完成", f"已輸出：{path}")


def main() -> int:
    app = RealtimeStudio()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
