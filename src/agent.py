"""
agent.py
========
Multi-function Copilot Agent that can:

* Process video files (subtitle generation + translation + burning)
* Watch a directory for new video files and process them automatically
* Answer natural-language queries about its own capabilities
* Expose a simple JSON-RPC style interface for VS Code and Windows-app
  integrations

Usage
-----
    from src.agent import CopilotAgent

    agent = CopilotAgent()

    # Single-file task
    result = agent.run_task({
        "action": "process_video",
        "video_path": "lecture.mp4",
        "output_dir": "output/",
        "source_language": "en",
        "bilingual": False,
    })

    # Watch a folder
    agent.watch_directory("videos/", output_dir="output/")
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .video_processor import VideoProcessor

logger = logging.getLogger(__name__)

# Supported video extensions that the agent will process automatically
_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts"}


class CopilotAgent:
    """
    Multi-function Copilot Agent for video subtitle automation.

    Parameters
    ----------
    model_size : str
        Whisper model size.  Default: ``"medium"``.
    device : str | None
        Torch device.  ``None`` = auto-detect.
    on_progress : Callable[[str], None] | None
        Optional callback invoked with progress messages.  Useful for
        updating a GUI progress bar or VS Code status-bar item.
    """

    SUPPORTED_ACTIONS = {
        "process_video",
        "generate_subtitles",
        "translate_subtitles",
        "burn_subtitles",
        "watch_directory",
        "stop_watch",
        "list_capabilities",
    }

    def __init__(
        self,
        model_size: str = "medium",
        device: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._processor = VideoProcessor(model_size=model_size, device=device)
        self._on_progress = on_progress or (lambda msg: logger.info(msg))
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_watch_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Dispatch a task dict and return a result dict.

        The task dict must contain an ``"action"`` key.  All other keys
        are action-specific parameters.

        Returns
        -------
        dict
            A result dict with a ``"status"`` key (``"ok"`` or ``"error"``)
            and action-specific output keys.
        """
        action = task.get("action", "")
        if action not in self.SUPPORTED_ACTIONS:
            return {
                "status": "error",
                "message": (
                    f"Unknown action '{action}'.  "
                    f"Supported: {sorted(self.SUPPORTED_ACTIONS)}"
                ),
            }

        try:
            if action == "process_video":
                return self._action_process_video(task)
            if action == "generate_subtitles":
                return self._action_generate_subtitles(task)
            if action == "translate_subtitles":
                return self._action_translate_subtitles(task)
            if action == "burn_subtitles":
                return self._action_burn_subtitles(task)
            if action == "watch_directory":
                return self._action_watch_directory(task)
            if action == "stop_watch":
                return self._action_stop_watch()
            if action == "list_capabilities":
                return self._action_list_capabilities()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Task '%s' failed.", action)
            return {"status": "error", "message": str(exc)}

        return {"status": "error", "message": "Unhandled action."}

    def run_task_json(self, task_json: str) -> str:
        """
        Convenience wrapper: accept a JSON string, return a JSON string.
        Useful for VS Code extension IPC and Windows named-pipe integration.
        """
        try:
            task = json.loads(task_json)
        except json.JSONDecodeError as exc:
            return json.dumps({"status": "error", "message": f"Invalid JSON: {exc}"})
        result = self.run_task(task)
        return json.dumps(result, default=str)

    def watch_directory(
        self,
        directory: str | Path,
        output_dir: Optional[str | Path] = None,
        source_language: Optional[str] = None,
        bilingual: bool = False,
        poll_interval: float = 5.0,
    ) -> None:
        """
        Start a background thread that watches *directory* for new video
        files and automatically processes them.

        Parameters
        ----------
        directory : str | Path
            Directory to monitor.
        output_dir : str | Path | None
            Output directory for processed files.
        source_language : str | None
            Whisper language hint.
        bilingual : bool
            Whether to include original text alongside Chinese translation.
        poll_interval : float
            Seconds between directory polls.
        """
        directory = Path(directory).resolve()
        self._stop_watch_event.clear()
        self._watch_thread = threading.Thread(
            target=self._watch_loop,
            args=(directory, output_dir, source_language, bilingual, poll_interval),
            daemon=True,
        )
        self._watch_thread.start()
        self._on_progress(f"Watching '{directory}' for new video files…")

    def stop_watching(self) -> None:
        """Stop the background directory-watch thread."""
        self._stop_watch_event.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=10)
        self._on_progress("Directory watch stopped.")

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _action_process_video(self, task: dict) -> dict:
        video_path = task.get("video_path")
        if not video_path:
            return {"status": "error", "message": "'video_path' is required."}
        self._on_progress(f"Processing video: {video_path}")
        result = self._processor.process(
            video_path,
            output_dir=task.get("output_dir"),
            source_language=task.get("source_language"),
            bilingual=bool(task.get("bilingual", False)),
            burn=bool(task.get("burn", True)),
        )
        return {"status": "ok", **{k: str(v) for k, v in result.items()}}

    def _action_generate_subtitles(self, task: dict) -> dict:
        video_path = task.get("video_path")
        if not video_path:
            return {"status": "error", "message": "'video_path' is required."}
        self._on_progress(f"Generating subtitles for: {video_path}")
        srt_path = self._processor.extract_subtitles(
            video_path,
            output_dir=task.get("output_dir"),
            source_language=task.get("source_language"),
        )
        return {"status": "ok", "srt_path": str(srt_path)}

    def _action_translate_subtitles(self, task: dict) -> dict:
        srt_path = task.get("srt_path")
        if not srt_path:
            return {"status": "error", "message": "'srt_path' is required."}
        self._on_progress(f"Translating subtitles: {srt_path}")
        out_path = self._processor.translate_subtitles(
            srt_path,
            output_dir=task.get("output_dir"),
            bilingual=bool(task.get("bilingual", False)),
        )
        return {"status": "ok", "translated_srt": str(out_path)}

    def _action_burn_subtitles(self, task: dict) -> dict:
        video_path = task.get("video_path")
        srt_path = task.get("srt_path")
        if not video_path or not srt_path:
            return {
                "status": "error",
                "message": "Both 'video_path' and 'srt_path' are required.",
            }
        self._on_progress(f"Burning subtitles onto: {video_path}")
        out = self._processor.burn_subtitles(
            video_path, srt_path, task.get("output_path")
        )
        return {"status": "ok", "burned_video": str(out)}

    def _action_watch_directory(self, task: dict) -> dict:
        directory = task.get("directory")
        if not directory:
            return {"status": "error", "message": "'directory' is required."}
        self.watch_directory(
            directory,
            output_dir=task.get("output_dir"),
            source_language=task.get("source_language"),
            bilingual=bool(task.get("bilingual", False)),
            poll_interval=float(task.get("poll_interval", 5.0)),
        )
        return {"status": "ok", "message": f"Watching '{directory}'."}

    def _action_stop_watch(self) -> dict:
        self.stop_watching()
        return {"status": "ok", "message": "Watch stopped."}

    @classmethod
    def _action_list_capabilities(cls) -> dict:
        return {
            "status": "ok",
            "capabilities": {
                "process_video": (
                    "Full pipeline: generate subtitles → translate to "
                    "Traditional Chinese → burn onto video."
                ),
                "generate_subtitles": (
                    "Transcribe video audio to SRT using OpenAI Whisper."
                ),
                "translate_subtitles": (
                    "Translate an existing SRT file to Traditional Chinese "
                    "(繁體中文) using Google Translate via deep-translator."
                ),
                "burn_subtitles": (
                    "Burn an SRT subtitle file onto a video using FFmpeg. "
                    "TV-style layout with Arial (English) / "
                    "微軟正黑體 (Chinese) fonts."
                ),
                "watch_directory": (
                    "Watch a directory for new video files and process them "
                    "automatically in the background."
                ),
                "stop_watch": "Stop the directory-watch background thread.",
                "list_capabilities": "Return this capabilities listing.",
            },
        }

    # ------------------------------------------------------------------
    # Directory watcher (polling-based, no extra dependencies)
    # ------------------------------------------------------------------

    def _watch_loop(
        self,
        directory: Path,
        output_dir: Optional[str | Path],
        source_language: Optional[str],
        bilingual: bool,
        poll_interval: float,
    ) -> None:
        """Background polling loop."""
        processed: set[Path] = set()
        while not self._stop_watch_event.is_set():
            try:
                for entry in directory.iterdir():
                    if (
                        entry.is_file()
                        and entry.suffix.lower() in _VIDEO_EXTENSIONS
                        and entry not in processed
                    ):
                        processed.add(entry)
                        self._on_progress(f"New video detected: {entry.name}")
                        try:
                            self._processor.process(
                                entry,
                                output_dir=output_dir,
                                source_language=source_language,
                                bilingual=bilingual,
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.error(
                                "Failed to process '%s': %s", entry.name, exc
                            )
            except Exception as exc:  # noqa: BLE001
                logger.error("Watch loop error: %s", exc)
            time.sleep(poll_interval)
