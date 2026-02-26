"""
app.py – Local Copilot AI GUI Application
==========================================
A tkinter-based desktop application that provides a user-friendly interface
for the video subtitle generation and translation pipeline.

Compatible with: Windows 10/11, Linux (with tkinter installed), macOS.

Features
--------
* Drag-and-drop (or Browse) video file selection
* Whisper model size selection
* Source language selection
* Bilingual subtitle toggle
* Real-time progress log
* Background processing (keeps GUI responsive)
* One-click "Open Output Folder" button

Run
---
    python gui/app.py
    # or from project root:
    python -m gui.app
"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

# Make sure the project root is on sys.path when running directly
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from src.agent import CopilotAgent

logger = logging.getLogger(__name__)

# ── Styling constants ────────────────────────────────────────────────────────

APP_TITLE = "Local Copilot AI – Video Subtitle System"
BG_COLOR = "#1e1e2e"          # dark background
FG_COLOR = "#cdd6f4"          # light text
ACCENT_COLOR = "#89b4fa"      # blue accent
BTN_BG = "#313244"
BTN_ACTIVE_BG = "#45475a"
FONT_MAIN = ("Arial", 11)
FONT_MONO = ("Consolas", 10)

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
LANGUAGES = {
    "Auto Detect": "auto",
    "English": "en",
    "Japanese": "ja",
    "Korean": "ko",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Chinese (Simplified)": "zh",
}


# ── Application class ────────────────────────────────────────────────────────


class CopilotApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("820x660")
        self.resizable(True, True)
        self.configure(bg=BG_COLOR)

        self._log_queue: queue.Queue[str] = queue.Queue()
        self._agent: CopilotAgent | None = None
        self._output_dir: Path | None = None

        self._build_ui()
        self._poll_log_queue()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        # ── Title bar ──
        title_lbl = tk.Label(
            self,
            text="🤖  Local Copilot AI  –  Video Subtitle System",
            font=("Arial", 15, "bold"),
            bg=BG_COLOR,
            fg=ACCENT_COLOR,
        )
        title_lbl.pack(fill="x", pady=(14, 4))

        # ── Input file selection ──
        file_frame = tk.LabelFrame(
            self, text="Video File", bg=BG_COLOR, fg=FG_COLOR,
            font=FONT_MAIN, bd=1, relief="groove",
        )
        file_frame.pack(fill="x", **pad)

        self._video_var = tk.StringVar()
        tk.Entry(
            file_frame, textvariable=self._video_var, bg=BTN_BG, fg=FG_COLOR,
            font=FONT_MAIN, insertbackground=FG_COLOR, width=60,
        ).pack(side="left", padx=8, pady=6, expand=True, fill="x")

        self._make_button(file_frame, "Browse…", self._browse_video).pack(
            side="left", padx=(0, 8), pady=6
        )

        # ── Options ──
        opt_frame = tk.LabelFrame(
            self, text="Options", bg=BG_COLOR, fg=FG_COLOR,
            font=FONT_MAIN, bd=1, relief="groove",
        )
        opt_frame.pack(fill="x", **pad)

        # Model size
        tk.Label(opt_frame, text="Whisper Model:", bg=BG_COLOR, fg=FG_COLOR,
                 font=FONT_MAIN).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self._model_var = tk.StringVar(value="medium")
        ttk.Combobox(
            opt_frame, textvariable=self._model_var, values=WHISPER_MODELS,
            state="readonly", width=10, font=FONT_MAIN,
        ).grid(row=0, column=1, sticky="w", padx=4, pady=6)

        # Source language
        tk.Label(opt_frame, text="Source Language:", bg=BG_COLOR, fg=FG_COLOR,
                 font=FONT_MAIN).grid(row=0, column=2, sticky="w", padx=(20, 4), pady=6)
        self._lang_var = tk.StringVar(value="Auto Detect")
        ttk.Combobox(
            opt_frame, textvariable=self._lang_var,
            values=list(LANGUAGES.keys()), state="readonly", width=18,
            font=FONT_MAIN,
        ).grid(row=0, column=3, sticky="w", padx=4, pady=6)

        # Bilingual toggle
        self._bilingual_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            opt_frame, text="Bilingual subtitles (original + Chinese)",
            variable=self._bilingual_var, bg=BG_COLOR, fg=FG_COLOR,
            selectcolor=BTN_BG, activebackground=BG_COLOR,
            activeforeground=FG_COLOR, font=FONT_MAIN,
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=8, pady=(2, 6))

        # Output directory
        tk.Label(opt_frame, text="Output Dir:", bg=BG_COLOR, fg=FG_COLOR,
                 font=FONT_MAIN).grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self._outdir_var = tk.StringVar(value="(same as video)")
        tk.Entry(
            opt_frame, textvariable=self._outdir_var, bg=BTN_BG, fg=FG_COLOR,
            font=FONT_MAIN, insertbackground=FG_COLOR, width=40,
        ).grid(row=2, column=1, columnspan=2, sticky="ew", padx=4, pady=6)
        self._make_button(opt_frame, "Browse…", self._browse_output_dir).grid(
            row=2, column=3, sticky="w", padx=4, pady=6
        )

        # ── Action buttons ──
        btn_frame = tk.Frame(self, bg=BG_COLOR)
        btn_frame.pack(fill="x", padx=12, pady=8)

        self._process_btn = self._make_button(
            btn_frame, "▶  Process Video (Full Pipeline)", self._start_process,
            width=34, font=("Arial", 12, "bold"), fg=ACCENT_COLOR,
        )
        self._process_btn.pack(side="left", padx=(0, 8))

        self._make_button(btn_frame, "Generate Only", self._start_generate_only).pack(
            side="left", padx=4
        )
        self._make_button(btn_frame, "Translate Only", self._start_translate_only).pack(
            side="left", padx=4
        )
        self._open_btn = self._make_button(
            btn_frame, "📂  Open Output", self._open_output_folder,
        )
        self._open_btn.pack(side="right", padx=4)
        self._open_btn["state"] = "disabled"

        # ── Progress bar ──
        self._progress = ttk.Progressbar(self, mode="indeterminate", length=400)
        self._progress.pack(fill="x", padx=12, pady=2)

        # ── Log area ──
        log_frame = tk.LabelFrame(
            self, text="Log", bg=BG_COLOR, fg=FG_COLOR,
            font=FONT_MAIN, bd=1, relief="groove",
        )
        log_frame.pack(fill="both", expand=True, **pad)
        self._log_text = scrolledtext.ScrolledText(
            log_frame, bg="#181825", fg="#a6e3a1", font=FONT_MONO,
            state="disabled", wrap="word", height=14,
        )
        self._log_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _make_button(self, parent, text, command, **kw) -> tk.Button:
        defaults = dict(
            bg=BTN_BG, fg=FG_COLOR, activebackground=BTN_ACTIVE_BG,
            activeforeground=FG_COLOR, relief="flat", cursor="hand2",
            font=FONT_MAIN, padx=10, pady=4,
        )
        defaults.update(kw)
        return tk.Button(parent, text=text, command=command, **defaults)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _browse_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.ts"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._video_var.set(path)

    def _browse_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self._outdir_var.set(path)

    def _start_process(self) -> None:
        self._run_in_background(action="process_video")

    def _start_generate_only(self) -> None:
        self._run_in_background(action="generate_subtitles")

    def _start_translate_only(self) -> None:
        video = self._video_var.get().strip()
        # For translate-only, expect an SRT next to the video
        if not video:
            messagebox.showerror("Error", "Please select a video file first.")
            return
        srt = Path(video).with_suffix(".srt")
        if not srt.exists():
            messagebox.showerror(
                "Error",
                f"SRT not found at '{srt}'.\n"
                "Run 'Generate Only' first, or select the correct SRT.",
            )
            return
        self._run_in_background(action="translate_subtitles", srt_path=str(srt))

    def _open_output_folder(self) -> None:
        folder = self._output_dir or Path(self._video_var.get()).parent
        if sys.platform == "win32":
            os.startfile(str(folder))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    # ------------------------------------------------------------------
    # Background processing
    # ------------------------------------------------------------------

    def _run_in_background(self, action: str, **extra) -> None:
        video = self._video_var.get().strip()
        if not video and action != "translate_subtitles":
            messagebox.showerror("Error", "Please select a video file first.")
            return

        outdir_str = self._outdir_var.get().strip()
        outdir: str | None = (
            None if outdir_str == "(same as video)" else outdir_str
        )

        task: dict = {
            "action": action,
            "output_dir": outdir,
            "bilingual": self._bilingual_var.get(),
            "source_language": LANGUAGES[self._lang_var.get()],
        }
        if video:
            task["video_path"] = video
        task.update(extra)

        # Disable controls and start spinner
        self._set_controls_state("disabled")
        self._progress.start(12)
        self._log_queue.put(f"[▶] Starting action: {action}\n")

        model_size = self._model_var.get()
        thread = threading.Thread(
            target=self._worker, args=(task, model_size), daemon=True
        )
        thread.start()

    def _worker(self, task: dict, model_size: str) -> None:
        """Background worker thread."""
        def progress_cb(msg: str) -> None:
            self._log_queue.put(msg + "\n")

        try:
            agent = CopilotAgent(model_size=model_size, on_progress=progress_cb)
            result = agent.run_task(task)
            if result.get("status") == "ok":
                # Extract output directory from result
                for key in ("burned_video", "translated_srt", "srt_path"):
                    if key in result:
                        self._output_dir = Path(result[key]).parent
                        break
                self._log_queue.put(
                    f"[✔] Done.  Output: {result}\n"
                )
            else:
                self._log_queue.put(f"[✖] Error: {result.get('message')}\n")
        except Exception as exc:  # noqa: BLE001
            self._log_queue.put(f"[✖] Exception: {exc}\n")
        finally:
            self._log_queue.put("__DONE__")

    def _poll_log_queue(self) -> None:
        """Drain the log queue and update the text widget."""
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg == "__DONE__":
                    self._progress.stop()
                    self._set_controls_state("normal")
                    self._open_btn["state"] = "normal"
                else:
                    self._append_log(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _append_log(self, text: str) -> None:
        self._log_text["state"] = "normal"
        self._log_text.insert("end", text)
        self._log_text.see("end")
        self._log_text["state"] = "disabled"

    def _set_controls_state(self, state: str) -> None:
        for widget in self.winfo_children():
            try:
                widget["state"] = state
            except tk.TclError:
                pass


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    app = CopilotApp()
    app.mainloop()


if __name__ == "__main__":
    main()
