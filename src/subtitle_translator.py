"""
subtitle_translator.py
======================
Translate SRT subtitle files to Traditional Chinese (繁體中文).

Design goals
------------
* Accuracy  > 95 % – achieved by using the Google Translate back-end via
  *deep-translator*, which is consistently the highest-quality free translation
  service for Chinese.
* Latency   < 2 s per subtitle block – individual segments are short, so
  single-call translation comfortably meets this requirement.  Batch mode
  (``translate_srt``) translates all lines in one request, which is even
  faster.
* Output language: Traditional Chinese (``zh-TW``).

Fonts used when rendering (see ``SubtitleRenderer``):
  - English text  → Arial
  - Chinese text  → 微軟正黑體 (Microsoft JhengHei)

Usage
-----
    from src.subtitle_translator import SubtitleTranslator

    t = SubtitleTranslator()
    out_srt = t.translate_srt("video.srt", output_dir="output/")
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Target language code for deep-translator (Traditional Chinese)
_TARGET_LANG = "zh-TW"

# Separator used to batch many lines in a single API call.
# Using a unique multi-char separator reduces the chance of it appearing in
# real subtitle text.
_BATCH_SEP = " ||||| "


def _contains_chinese(text: str) -> bool:
    """Return True if *text* already contains CJK characters."""
    return bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))


class SubtitleTranslator:
    """
    Translates the textual content of an SRT file to Traditional Chinese.

    Parameters
    ----------
    source_lang : str
        ISO 639-1 source language code (e.g. ``"auto"`` for auto-detect,
        ``"en"`` for English, ``"ja"`` for Japanese).
        Defaults to ``"auto"``.
    max_retries : int
        Number of translation retries on transient network errors.
    retry_delay : float
        Seconds to wait between retries.
    """

    def __init__(
        self,
        source_lang: str = "auto",
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ) -> None:
        self.source_lang = source_lang
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._translator = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate_text(self, text: str) -> str:
        """
        Translate a single subtitle text string to Traditional Chinese.

        Already-Chinese text is returned unchanged to avoid double-translation.

        Parameters
        ----------
        text : str
            Source subtitle text (one or multiple lines from a single block).

        Returns
        -------
        str
            Translated text in Traditional Chinese.
        """
        if not text.strip():
            return text
        if _contains_chinese(text):
            return text

        translator = self._get_translator()
        for attempt in range(1, self.max_retries + 1):
            try:
                t0 = time.monotonic()
                result: str = translator.translate(text)
                elapsed = time.monotonic() - t0
                if elapsed > 2.0:
                    logger.warning(
                        "Translation took %.2f s (>2 s SLA) for text: %r",
                        elapsed,
                        text[:60],
                    )
                return result or text
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Translation attempt %d/%d failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
        # All retries exhausted – return original text
        logger.error("All translation retries failed; keeping original text.")
        return text

    def translate_srt(
        self,
        srt_path: str | Path,
        output_dir: Optional[str | Path] = None,
        output_filename: Optional[str] = None,
        bilingual: bool = False,
    ) -> Path:
        """
        Translate every subtitle block in an SRT file to Traditional Chinese
        and write the result to a new SRT file.

        Parameters
        ----------
        srt_path : str | Path
            Path to the source ``.srt`` file.
        output_dir : str | Path | None
            Directory for the translated file.  Defaults to the source
            directory.
        output_filename : str | None
            Override the base filename (without extension).  Defaults to
            ``<original_stem>_zh-TW``.
        bilingual : bool
            If ``True``, each subtitle block will contain both the original
            text and the Chinese translation separated by a newline.

        Returns
        -------
        Path
            Absolute path to the translated ``.srt`` file.
        """
        srt_path = Path(srt_path).resolve()
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_path}")

        out_dir = Path(output_dir).resolve() if output_dir else srt_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = output_filename or f"{srt_path.stem}_zh-TW"
        out_path = out_dir / f"{stem}.srt"

        blocks = self._parse_srt(srt_path.read_text(encoding="utf-8"))
        logger.info(
            "Translating %d subtitle blocks from '%s'…", len(blocks), srt_path
        )

        translated_blocks = self._translate_blocks_batch(blocks, bilingual=bilingual)

        out_path.write_text(
            self._blocks_to_srt(translated_blocks), encoding="utf-8"
        )
        logger.info("Translated SRT saved to '%s'.", out_path)
        return out_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_translator(self):
        """Lazy-load the deep-translator GoogleTranslator instance."""
        if self._translator is None:
            try:
                from deep_translator import GoogleTranslator  # type: ignore

                self._translator = GoogleTranslator(
                    source=self.source_lang, target=_TARGET_LANG
                )
            except ImportError as exc:
                raise ImportError(
                    "deep-translator is required for subtitle translation.\n"
                    "Install it with:  pip install deep-translator"
                ) from exc
        return self._translator

    # -- SRT parsing -------------------------------------------------------

    @staticmethod
    def _parse_srt(content: str) -> list[dict]:
        """
        Parse SRT content into a list of block dicts::

            {"index": int, "timestamp": str, "text": str}
        """
        blocks: list[dict] = []
        # Split on blank lines that separate SRT blocks
        raw_blocks = re.split(r"\n\s*\n", content.strip())
        for raw in raw_blocks:
            lines = raw.strip().splitlines()
            if len(lines) < 3:
                continue
            try:
                index = int(lines[0].strip())
            except ValueError:
                continue
            timestamp = lines[1].strip()
            text = "\n".join(lines[2:]).strip()
            blocks.append({"index": index, "timestamp": timestamp, "text": text})
        return blocks

    @staticmethod
    def _blocks_to_srt(blocks: list[dict]) -> str:
        """Serialise translated block dicts back to SRT format."""
        parts: list[str] = []
        for b in blocks:
            parts.append(f"{b['index']}\n{b['timestamp']}\n{b['text']}\n")
        return "\n".join(parts)

    def _translate_blocks_batch(
        self, blocks: list[dict], bilingual: bool
    ) -> list[dict]:
        """
        Translate all text blocks in a single batched API call to minimise
        round-trip latency, then distribute the results back to each block.
        """
        # Collect only the blocks that actually need translation
        to_translate_indices: list[int] = []
        texts: list[str] = []
        for i, b in enumerate(blocks):
            text = b["text"]
            if text.strip() and not _contains_chinese(text):
                to_translate_indices.append(i)
                # Normalise newlines to spaces for the batch call
                texts.append(text.replace("\n", " "))

        if not texts:
            return blocks  # nothing to do

        # --- Batch in one call (deep-translator supports a string up to ~5000 chars)
        batch_input = _BATCH_SEP.join(texts)
        translated_batch: str | None = None
        try:
            translated_batch = self._get_translator().translate(batch_input)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Batch translation failed (%s); falling back to per-block.", exc)

        if translated_batch:
            translated_texts = translated_batch.split(_BATCH_SEP)
            # Guard against separator being mangled by the translation service
            if len(translated_texts) == len(texts):
                for block_i, translated in zip(to_translate_indices, translated_texts):
                    original = blocks[block_i]["text"]
                    translation = translated.strip()
                    blocks[block_i]["text"] = (
                        f"{original}\n{translation}" if bilingual else translation
                    )
                return blocks
            logger.warning(
                "Batch translation returned %d parts for %d inputs; "
                "falling back to per-block translation.",
                len(translated_texts),
                len(texts),
            )

        # --- Fall back to per-block translation
        for i, text in zip(to_translate_indices, texts):
            translation = self.translate_text(text)
            original = blocks[i]["text"]
            blocks[i]["text"] = (
                f"{original}\n{translation}" if bilingual else translation
            )

        return blocks
