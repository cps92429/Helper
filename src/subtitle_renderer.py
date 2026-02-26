"""
subtitle_renderer.py
====================
Render TV-style subtitles onto video frames using Pillow.

Visual specification
--------------------
* Position    : bottom-centre (same as broadcast TV subtitles)
* Background  : semi-transparent black bar behind text
* English text: Arial font
* Chinese text: 微軟正黑體 (Microsoft JhengHei); falls back to a bundled
                CJK font when JhengHei is not installed (Linux / CI)
* Text colour : white with a 1-pixel black shadow for legibility
* Font size   : auto-scales to ~5 % of frame height (configurable)

Usage
-----
    from src.subtitle_renderer import SubtitleRenderer

    renderer = SubtitleRenderer()
    renderer.burn_subtitles("video.mp4", "video_zh-TW.srt", "output_burned.mp4")
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Font resolution ──────────────────────────────────────────────────────────

# Ordered list of candidate font paths for Microsoft JhengHei (Traditional
# Chinese).  The first existing path wins.
_JHENG_HEI_CANDIDATES: list[str] = [
    # Windows
    r"C:\Windows\Fonts\msjh.ttc",
    r"C:\Windows\Fonts\msjhbd.ttc",
    # macOS (via Office / manual install)
    "/Library/Fonts/Microsoft JhengHei.ttf",
    "/Library/Fonts/Microsoft JhengHei Bold.ttf",
    # Linux (user-installed)
    os.path.expanduser("~/.fonts/msjh.ttc"),
    os.path.expanduser("~/.local/share/fonts/msjh.ttc"),
    "/usr/share/fonts/truetype/msjh.ttc",
    # Noto CJK – wide availability on Linux as a reliable fallback
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
]

_ARIAL_CANDIDATES: list[str] = [
    # Windows
    r"C:\Windows\Fonts\arial.ttf",
    # macOS
    "/Library/Fonts/Arial.ttf",
    # Linux (via ttf-mscorefonts-installer)
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/usr/share/fonts/truetype/arial.ttf",
    # DejaVu Sans – very common Linux fallback, metrically similar
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]


def _find_font(candidates: list[str]) -> Optional[str]:
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _contains_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))


# ── SubtitleRenderer ─────────────────────────────────────────────────────────


class SubtitleRenderer:
    """
    Burns TV-style subtitles onto a video file.

    Parameters
    ----------
    font_size_ratio : float
        Font size expressed as a fraction of the frame height.
        Default is ``0.05`` (5 % of height).
    bg_opacity : int
        Background bar opacity, 0 (transparent) – 255 (opaque).
        Default is ``160`` (~63 % opaque black bar).
    padding : int
        Vertical and horizontal padding (in pixels) around the text block.
    bottom_margin : int
        Distance (pixels) from the bottom of the frame to the subtitle bar.
    """

    def __init__(
        self,
        font_size_ratio: float = 0.05,
        bg_opacity: int = 160,
        padding: int = 8,
        bottom_margin: int = 20,
    ) -> None:
        self.font_size_ratio = font_size_ratio
        self.bg_opacity = bg_opacity
        self.padding = padding
        self.bottom_margin = bottom_margin

        self._arial_path: Optional[str] = _find_font(_ARIAL_CANDIDATES)
        self._jheng_hei_path: Optional[str] = _find_font(_JHENG_HEI_CANDIDATES)

        if not self._arial_path:
            logger.warning(
                "Arial font not found; Pillow default font will be used for English."
            )
        if not self._jheng_hei_path:
            logger.warning(
                "Microsoft JhengHei / Noto CJK font not found; "
                "Pillow default font will be used for Chinese."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def burn_subtitles(
        self,
        video_path: str | Path,
        srt_path: str | Path,
        output_path: str | Path,
        ffmpeg_extra_args: Optional[list[str]] = None,
    ) -> Path:
        """
        Burn subtitles from *srt_path* into *video_path* and write the
        result to *output_path*.

        This method uses FFmpeg's ``subtitles`` filter for efficient,
        hardware-accelerated subtitle burning while honouring the specified
        fonts via ``force_style``.

        Parameters
        ----------
        video_path : str | Path
            Input video file.
        srt_path : str | Path
            ``.srt`` subtitle file (should already be in Traditional Chinese).
        output_path : str | Path
            Output video file path.
        ffmpeg_extra_args : list[str] | None
            Additional FFmpeg arguments inserted before the output path.

        Returns
        -------
        Path
            Resolved path to the output file.
        """
        video_path = Path(video_path).resolve()
        srt_path = Path(srt_path).resolve()
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        force_style = self._build_force_style()
        # Escape special characters in the SRT path for FFmpeg filter syntax
        safe_srt = str(srt_path).replace("\\", "/").replace(":", "\\:")

        filter_str = f"subtitles='{safe_srt}':force_style='{force_style}'"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", filter_str,
            "-c:a", "copy",
        ]
        if ffmpeg_extra_args:
            cmd.extend(ffmpeg_extra_args)
        cmd.append(str(output_path))

        logger.info("Burning subtitles: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg subtitle burning failed:\n{result.stderr}"
            )
        logger.info("Burned video saved to '%s'.", output_path)
        return output_path

    def render_frame(
        self,
        frame,  # PIL.Image.Image
        text: str,
    ):
        """
        Overlay subtitle *text* on a single PIL Image *frame* in TV style.

        This is used for frame-by-frame processing when FFmpeg is not
        available.

        Parameters
        ----------
        frame : PIL.Image.Image
            The video frame to annotate.
        text : str
            Subtitle text to render.

        Returns
        -------
        PIL.Image.Image
            A new image with the subtitle overlay applied.
        """
        from PIL import Image, ImageDraw, ImageFont  # type: ignore

        frame = frame.copy().convert("RGBA")
        width, height = frame.size
        font_size = max(16, int(height * self.font_size_ratio))

        font = self._load_font(text, font_size)
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

        # Measure text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Build semi-transparent overlay
        bar_w = text_w + self.padding * 2
        bar_h = text_h + self.padding * 2
        bar_x = (width - bar_w) // 2
        bar_y = height - bar_h - self.bottom_margin

        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        # Dark background bar
        overlay_draw.rectangle(
            [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
            fill=(0, 0, 0, self.bg_opacity),
        )

        # Shadow (1-px offset, black)
        text_x = bar_x + self.padding
        text_y = bar_y + self.padding
        overlay_draw.text((text_x + 1, text_y + 1), text, font=font, fill=(0, 0, 0, 200))
        # Main text (white)
        overlay_draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))

        composite = Image.alpha_composite(frame, overlay)
        return composite.convert("RGB")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_font(self, text: str, size: int):
        """Select the appropriate font based on text content."""
        from PIL import ImageFont  # type: ignore

        # Choose CJK font for Chinese text, Arial for everything else
        if _contains_chinese(text) and self._jheng_hei_path:
            font_path = self._jheng_hei_path
        elif not _contains_chinese(text) and self._arial_path:
            font_path = self._arial_path
        else:
            font_path = self._jheng_hei_path or self._arial_path

        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load font '%s': %s", font_path, exc)

        return ImageFont.load_default()

    def _build_force_style(self) -> str:
        """
        Build the ASS ``force_style`` string for the FFmpeg subtitles filter.

        Font selection follows the same logic as ``render_frame``:
        * Microsoft JhengHei for Chinese subtitles
        * Arial for non-Chinese subtitles
        (FFmpeg/libass will use the first matching system font; having both
        fonts installed gives the best result for bilingual subtitles.)
        """
        # Prefer JhengHei for CJK; Arial as secondary
        chinese_font = "Microsoft JhengHei"
        english_font = "Arial"
        font_name = f"{chinese_font},{english_font}"

        # Font size in ASS points (approximate for 480p-1080p)
        font_size = 24

        return (
            f"FontName={font_name},"
            f"FontSize={font_size},"
            "PrimaryColour=&H00FFFFFF,"   # white text
            "OutlineColour=&H00000000,"   # black outline
            "BackColour=&H80000000,"      # semi-transparent black background
            "Bold=0,"
            "Italic=0,"
            "Outline=1,"
            "Shadow=1,"
            "Alignment=2,"               # bottom-centre (same as SSA Alignment=2)
            "MarginV=20"                 # 20-px bottom margin
        )
