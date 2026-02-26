"""
subtitle_generator.py
=====================
Whisper-based automatic speech recognition that produces SRT subtitle files
from a video or audio source.

Requirements
------------
- openai-whisper
- ffmpeg (system binary)
- torch / torchaudio

Usage
-----
    from src.subtitle_generator import SubtitleGenerator

    gen = SubtitleGenerator(model_size="medium")
    srt_path = gen.generate("my_video.mp4", output_dir="output/")
"""

from __future__ import annotations

import os
import logging
import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """
    Generates SRT subtitle files from a video / audio file using OpenAI Whisper.

    Parameters
    ----------
    model_size : str
        Whisper model size.  Choices: ``tiny``, ``base``, ``small``,
        ``medium``, ``large``.  ``medium`` gives a good balance between
        speed and accuracy on most machines.
    device : str
        Torch device string, e.g. ``"cuda"`` or ``"cpu"``.
        ``None`` (default) auto-detects CUDA; falls back to CPU.
    language : str | None
        Source language hint (e.g. ``"zh"`` for Chinese, ``"en"`` for
        English).  ``None`` lets Whisper auto-detect.
    """

    # Default to "medium" for good accuracy while still being usable on CPU
    DEFAULT_MODEL = "medium"

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL,
        device: Optional[str] = None,
        language: Optional[str] = None,
    ) -> None:
        self.model_size = model_size
        self.language = language
        self._device = device
        self._model = None  # lazy-loaded on first use

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        video_path: str | Path,
        output_dir: Optional[str | Path] = None,
        output_filename: Optional[str] = None,
    ) -> Path:
        """
        Transcribe *video_path* and save the result as an SRT file.

        Parameters
        ----------
        video_path : str | Path
            Path to the input video / audio file.
        output_dir : str | Path | None
            Directory where the ``.srt`` file will be saved.  Defaults to
            the same directory as the input file.
        output_filename : str | None
            Override the base name of the output file (without extension).
            Defaults to the stem of the input file.

        Returns
        -------
        Path
            Absolute path of the generated ``.srt`` file.
        """
        video_path = Path(video_path).resolve()
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        out_dir = Path(output_dir).resolve() if output_dir else video_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = output_filename or video_path.stem
        srt_path = out_dir / f"{stem}.srt"

        logger.info("Loading Whisper model '%s'…", self.model_size)
        model = self._load_model()

        logger.info("Transcribing '%s'…", video_path)
        result = model.transcribe(
            str(video_path),
            language=self.language,
            verbose=False,
            word_timestamps=False,
        )

        segments = result.get("segments", [])
        logger.info("Transcription complete – %d segments found.", len(segments))

        srt_content = self._segments_to_srt(segments)
        srt_path.write_text(srt_content, encoding="utf-8")
        logger.info("SRT saved to '%s'.", srt_path)
        return srt_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self):
        """Lazy-load the Whisper model (imports whisper only when needed)."""
        if self._model is None:
            try:
                import whisper  # type: ignore
                import torch  # type: ignore

                device = self._device
                if device is None:
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info("Using device: %s", device)
                self._model = whisper.load_model(self.model_size, device=device)
            except ImportError as exc:
                raise ImportError(
                    "openai-whisper is required for subtitle generation.\n"
                    "Install it with:  pip install openai-whisper"
                ) from exc
        return self._model

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Convert a float number of seconds to SRT timestamp format."""
        td = datetime.timedelta(seconds=seconds)
        total_ms = int(td.total_seconds() * 1000)
        hours, remainder = divmod(total_ms, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, millis = divmod(remainder, 1_000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @classmethod
    def _segments_to_srt(cls, segments: list[dict]) -> str:
        """Convert Whisper transcript segments to SRT format string."""
        lines: list[str] = []
        for idx, seg in enumerate(segments, start=1):
            start = cls._format_timestamp(seg["start"])
            end = cls._format_timestamp(seg["end"])
            text = seg["text"].strip()
            lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
        return "\n".join(lines)
