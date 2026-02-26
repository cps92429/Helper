"""
video_processor.py
==================
High-level orchestrator that ties together subtitle generation, translation,
and rendering into a single pipeline.

Usage
-----
    from src.video_processor import VideoProcessor

    vp = VideoProcessor()

    # Full pipeline: generate + translate + burn
    output = vp.process(
        "my_video.mp4",
        output_dir="output/",
        source_language="en",
        bilingual=False,
    )

    # Or step-by-step:
    srt   = vp.extract_subtitles("my_video.mp4")
    zh_srt = vp.translate_subtitles(srt)
    burned = vp.burn_subtitles("my_video.mp4", zh_srt)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .subtitle_generator import SubtitleGenerator
from .subtitle_translator import SubtitleTranslator
from .subtitle_renderer import SubtitleRenderer

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Orchestrates the full subtitle generation → translation → rendering
    pipeline for a video file.

    Parameters
    ----------
    model_size : str
        Whisper model size (``"tiny"``, ``"base"``, ``"small"``,
        ``"medium"``, ``"large"``).  Default: ``"medium"``.
    device : str | None
        Torch device (``"cpu"``, ``"cuda"``).  Auto-detected when ``None``.
    """

    def __init__(
        self,
        model_size: str = "medium",
        device: Optional[str] = None,
    ) -> None:
        self._generator = SubtitleGenerator(model_size=model_size, device=device)
        self._translator = SubtitleTranslator()
        self._renderer = SubtitleRenderer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        video_path: str | Path,
        output_dir: Optional[str | Path] = None,
        source_language: Optional[str] = None,
        bilingual: bool = False,
        burn: bool = True,
    ) -> dict[str, Path]:
        """
        Run the complete pipeline on *video_path*.

        Steps:
        1. Generate SRT from audio (Whisper).
        2. Translate SRT to Traditional Chinese.
        3. Optionally burn translated subtitles into a new video.

        Parameters
        ----------
        video_path : str | Path
            Input video file.
        output_dir : str | Path | None
            Directory for all output files.  Defaults to the input directory.
        source_language : str | None
            Source language hint for Whisper (e.g. ``"en"``).
        bilingual : bool
            If ``True``, the translated SRT will contain both source text and
            Chinese translation.
        burn : bool
            If ``True``, burn the translated subtitles onto the video.

        Returns
        -------
        dict[str, Path]
            A dict with keys ``"original_srt"``, ``"translated_srt"``, and
            optionally ``"burned_video"``.
        """
        video_path = Path(video_path).resolve()
        out_dir = Path(output_dir).resolve() if output_dir else video_path.parent

        self._generator.language = source_language

        logger.info("Step 1/3 – Generating subtitles for '%s'…", video_path.name)
        original_srt = self._generator.generate(video_path, output_dir=out_dir)

        logger.info("Step 2/3 – Translating subtitles to Traditional Chinese…")
        translated_srt = self._translator.translate_srt(
            original_srt,
            output_dir=out_dir,
            bilingual=bilingual,
        )

        result: dict[str, Path] = {
            "original_srt": original_srt,
            "translated_srt": translated_srt,
        }

        if burn:
            logger.info("Step 3/3 – Burning subtitles onto video…")
            burned_path = out_dir / f"{video_path.stem}_subtitled{video_path.suffix}"
            self._renderer.burn_subtitles(
                video_path,
                translated_srt,
                burned_path,
            )
            result["burned_video"] = burned_path

        logger.info("Pipeline complete.  Outputs: %s", result)
        return result

    def extract_subtitles(
        self,
        video_path: str | Path,
        output_dir: Optional[str | Path] = None,
        source_language: Optional[str] = None,
    ) -> Path:
        """Generate SRT from *video_path* and return the SRT file path."""
        self._generator.language = source_language
        return self._generator.generate(video_path, output_dir=output_dir)

    def translate_subtitles(
        self,
        srt_path: str | Path,
        output_dir: Optional[str | Path] = None,
        bilingual: bool = False,
    ) -> Path:
        """Translate an existing SRT file to Traditional Chinese."""
        return self._translator.translate_srt(
            srt_path,
            output_dir=output_dir,
            bilingual=bilingual,
        )

    def burn_subtitles(
        self,
        video_path: str | Path,
        srt_path: str | Path,
        output_path: Optional[str | Path] = None,
    ) -> Path:
        """Burn *srt_path* subtitles onto *video_path*."""
        video_path = Path(video_path).resolve()
        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}_subtitled{video_path.suffix}"
        return self._renderer.burn_subtitles(video_path, srt_path, output_path)
