import sys
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import srt

# Make `studio.*` importable when running this file directly.
AGENT_DIR = Path(__file__).resolve().parents[1]  # agents/agent1-video-subtitle
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from studio.config import load_agent1_config, resolve_repo_root_from_file  # noqa: E402
from studio.services.jobs import Job, JobOptions  # noqa: E402
from studio.services.runner import run_job  # noqa: E402


@dataclass
class UiJob:
    job: Job
    status: str = "pending"  # pending/running/done/error
    message: str = ""
    output_srt: Optional[Path] = None
    output_ass: Optional[Path] = None
    output_zh_tw_srt: Optional[Path] = None


class SubtitleStudio(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("字幕工作室 (Agent1)")
        self.geometry("1080x760")

        self.repo_root = resolve_repo_root_from_file(Path(__file__))
        self.cfg = load_agent1_config(self.repo_root)
        self.venv_python = self.repo_root / ".venv" / "Scripts" / "python.exe"

        self.events: "queue.Queue[dict]" = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.cancel_flag = threading.Event()

        self.jobs: List[UiJob] = []

        self._build_ui()
        self.after(100, self._poll_events)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        top = ttk.Frame(root)
        top.pack(fill="x")

        self.output_dir_var = tk.StringVar(value=str(self.repo_root / self.cfg.default_output_dir_name))
        ttk.Label(top, text="輸出資料夾").pack(side="left")
        ttk.Entry(top, textvariable=self.output_dir_var, width=80).pack(side="left", padx=8)
        ttk.Button(top, text="選擇...", command=self._pick_output_dir).pack(side="left")

        opts = ttk.Labelframe(root, text="處理選項", padding=10)
        opts.pack(fill="x", pady=10)

        self.opt_transcribe = tk.BooleanVar(value=True)
        self.opt_smart = tk.BooleanVar(value=True)
        self.opt_translate = tk.BooleanVar(value=True)
        self.opt_ass = tk.BooleanVar(value=True)
        self.opt_bilingual = tk.BooleanVar(value=False)
        self.opt_burn = tk.BooleanVar(value=False)

        ttk.Checkbutton(opts, text="生成字幕 (轉錄)", variable=self.opt_transcribe).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="智慧斷句", variable=self.opt_smart).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="專業翻譯 (繁體中文)", variable=self.opt_translate).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="輸出 ASS (字幕設計)", variable=self.opt_ass).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="雙語上下 (ASS)", variable=self.opt_bilingual).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="一鍵燒錄進影片", variable=self.opt_burn).pack(side="left", padx=8)

        style_row = ttk.Frame(root)
        style_row.pack(fill="x")
        ttk.Label(style_row, text="字幕樣式").pack(side="left")
        self.style_path_var = tk.StringVar(value=str(self.repo_root / "agents" / "agent1-video-subtitle" / "style.json"))
        ttk.Entry(style_row, textvariable=self.style_path_var, width=80).pack(side="left", padx=8)
        ttk.Button(style_row, text="選擇...", command=self._pick_style_json).pack(side="left")

        actions = ttk.Frame(root)
        actions.pack(fill="x")

        ttk.Button(actions, text="新增檔案...", command=self._add_files).pack(side="left")
        ttk.Button(actions, text="新增資料夾...", command=self._add_folder).pack(side="left", padx=8)
        ttk.Button(actions, text="清空清單", command=self._clear_jobs).pack(side="left", padx=8)
        ttk.Button(actions, text="開始批次", command=self._start).pack(side="left", padx=8)
        ttk.Button(actions, text="取消", command=self._cancel).pack(side="left", padx=8)

        mid = ttk.Panedwindow(root, orient="horizontal")
        mid.pack(fill="both", expand=True, pady=10)

        left = ttk.Frame(mid, padding=0)
        right = ttk.Frame(mid, padding=0)
        mid.add(left, weight=1)
        mid.add(right, weight=2)

        self.tree = ttk.Treeview(left, columns=("status", "path"), show="headings", selectmode="browse")
        self.tree.heading("status", text="狀態")
        self.tree.heading("path", text="輸入檔案")
        self.tree.column("status", width=120, anchor="w")
        self.tree.column("path", width=420, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._refresh_preview())

        prog = ttk.Frame(root)
        prog.pack(fill="x")

        self.progress_var = tk.IntVar(value=0)
        self.progress = ttk.Progressbar(prog, orient="horizontal", mode="determinate", maximum=100, variable=self.progress_var)
        self.progress.pack(fill="x", expand=True, side="left")
        self.progress_label = ttk.Label(prog, text="待命")
        self.progress_label.pack(side="left", padx=10)

        preview = ttk.Labelframe(right, text="字幕預覽 (SRT)", padding=10)
        preview.pack(fill="both", expand=True)

        self.preview_tree = ttk.Treeview(preview, columns=("start", "end", "text"), show="headings")
        self.preview_tree.heading("start", text="開始")
        self.preview_tree.heading("end", text="結束")
        self.preview_tree.heading("text", text="字幕")
        self.preview_tree.column("start", width=140, anchor="w")
        self.preview_tree.column("end", width=140, anchor="w")
        self.preview_tree.column("text", width=640, anchor="w")
        vsb = ttk.Scrollbar(preview, orient="vertical", command=self.preview_tree.yview)
        self.preview_tree.configure(yscrollcommand=vsb.set)
        self.preview_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

    def _pick_output_dir(self) -> None:
        p = filedialog.askdirectory(title="選擇輸出資料夾")
        if p:
            self.output_dir_var.set(p)

    def _pick_style_json(self) -> None:
        p = filedialog.askopenfilename(
            title="選擇字幕樣式 JSON",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
        )
        if p:
            self.style_path_var.set(p)

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="新增檔案（影片/音檔 或 SRT）",
            filetypes=[
                ("Media/SRT", "*.mp4 *.mkv *.mov *.avi *.mp3 *.wav *.flac *.m4a *.aac *.srt"),
                ("All", "*.*"),
            ],
        )
        if not paths:
            return

        for p in paths:
            path = Path(p)
            bilingual = self.opt_bilingual.get()
            burn = self.opt_burn.get()
            convert_ass = self.opt_ass.get() or bilingual or burn
            translate = self.opt_translate.get() or bilingual
            opts = JobOptions(
                transcribe=self.opt_transcribe.get() and path.suffix.lower() != ".srt",
                smart_segment=self.opt_smart.get(),
                pro_translate_zh_tw=translate,
                convert_ass=convert_ass,
                bilingual_ass=bilingual,
                burn_in=burn,
            )
            self.jobs.append(UiJob(job=Job(input_path=path, options=opts)))

        self._render_jobs()

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="新增資料夾（批次）")
        if not folder:
            return
        base = Path(folder)
        exts = {".mp4", ".mkv", ".mov", ".avi", ".mp3", ".wav", ".flac", ".m4a", ".aac", ".srt"}
        files = sorted([p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in exts])
        if not files:
            messagebox.showinfo("沒有檔案", "此資料夾找不到支援的媒體或 SRT。")
            return

        for path in files:
            bilingual = self.opt_bilingual.get()
            burn = self.opt_burn.get()
            convert_ass = self.opt_ass.get() or bilingual or burn
            translate = self.opt_translate.get() or bilingual
            opts = JobOptions(
                transcribe=self.opt_transcribe.get() and path.suffix.lower() != ".srt",
                smart_segment=self.opt_smart.get(),
                pro_translate_zh_tw=translate,
                convert_ass=convert_ass,
                bilingual_ass=bilingual,
                burn_in=burn,
            )
            self.jobs.append(UiJob(job=Job(input_path=path, options=opts)))

        self._render_jobs()

    def _clear_jobs(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("忙碌中", "處理中無法清空，請先取消。")
            return
        self.jobs = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

    def _render_jobs(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, uj in enumerate(self.jobs):
            self.tree.insert("", "end", iid=str(i), values=(uj.status, str(uj.job.input_path)))

    def _start(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if not self.jobs:
            messagebox.showinfo("沒有工作", "請先新增檔案。")
            return
        if not self.venv_python.exists():
            messagebox.showerror("缺少 venv", "找不到 .venv，請先執行：.\\setup.ps1 -Target Agent1")
            return

        out_dir = Path(self.output_dir_var.get()).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        style_path = Path(self.style_path_var.get()).expanduser()
        if not style_path.exists():
            messagebox.showerror("樣式檔不存在", f"找不到樣式檔：{style_path}")
            return

        self.cancel_flag.clear()
        self.progress_var.set(0)
        self.progress_label.config(text="開始...")

        self.worker_thread = threading.Thread(target=self._run_batch, args=(out_dir,), daemon=True)
        self.worker_thread.start()

    def _cancel(self) -> None:
        self.cancel_flag.set()
        self.progress_label.config(text="取消中（會在下一步停止）...")

    def _emit_progress(self, value: int, message: str) -> None:
        self.events.put({"type": "progress", "value": int(value), "message": str(message)})

    def _run_batch(self, out_dir: Path) -> None:
        style_path = Path(self.style_path_var.get()).expanduser()
        for idx, uj in enumerate(self.jobs):
            if self.cancel_flag.is_set():
                self.events.put({"type": "status", "index": idx, "status": "canceled", "message": "已取消"})
                break

            self.events.put({"type": "status", "index": idx, "status": "running", "message": "處理中"})
            try:
                result = run_job(
                    job=uj.job,
                    repo_root=self.repo_root,
                    cfg=self.cfg,
                    venv_python=self.venv_python,
                    output_dir=out_dir,
                    style_json=style_path,
                    progress_cb=self._emit_progress,
                )
                self.events.put(
                    {
                        "type": "done",
                        "index": idx,
                        "srt": str(result.srt_path) if result.srt_path else "",
                        "zh_tw_srt": str(result.zh_tw_srt_path) if result.zh_tw_srt_path else "",
                        "ass": str(result.ass_path) if result.ass_path else "",
                    }
                )
            except Exception as e:
                self.events.put({"type": "error", "index": idx, "message": str(e)})

        self.events.put({"type": "batch_done"})

    def _poll_events(self) -> None:
        try:
            while True:
                ev = self.events.get_nowait()
                et = ev.get("type")
                if et == "progress":
                    self.progress_var.set(int(ev.get("value", 0)))
                    self.progress_label.config(text=str(ev.get("message", "")))
                elif et == "status":
                    i = int(ev["index"])
                    self.jobs[i].status = str(ev.get("status", "running"))
                    self.jobs[i].message = str(ev.get("message", ""))
                    self._render_jobs()
                elif et == "done":
                    i = int(ev["index"])
                    self.jobs[i].status = "done"
                    self.jobs[i].output_srt = Path(ev["srt"]) if ev.get("srt") else None
                    self.jobs[i].output_zh_tw_srt = Path(ev["zh_tw_srt"]) if ev.get("zh_tw_srt") else None
                    self.jobs[i].output_ass = Path(ev["ass"]) if ev.get("ass") else None
                    self._render_jobs()
                    # Auto-preview translated SRT if available, else original.
                    self.tree.selection_set(str(i))
                    self._refresh_preview()
                elif et == "error":
                    i = int(ev["index"])
                    self.jobs[i].status = "error"
                    self.jobs[i].message = str(ev.get("message", ""))
                    self._render_jobs()
                    messagebox.showerror("處理失敗", self.jobs[i].message)
                elif et == "batch_done":
                    self.progress_label.config(text="批次完成")
        except queue.Empty:
            pass
        finally:
            self.after(120, self._poll_events)

    def _refresh_preview(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        uj = self.jobs[idx]

        srt_path = uj.output_zh_tw_srt or uj.output_srt
        if not srt_path or not srt_path.exists():
            return

        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)

        try:
            text = srt_path.read_text(encoding="utf-8-sig")
            subs = list(srt.parse(text))
            for sub in subs[:1000]:
                self.preview_tree.insert(
                    "",
                    "end",
                    values=(str(sub.start), str(sub.end), sub.content.replace("\n", " / ")),
                )
        except Exception as e:
            messagebox.showerror("預覽失敗", str(e))


def main() -> int:
    app = SubtitleStudio()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
