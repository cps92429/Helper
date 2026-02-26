"""
tests/test_subtitle_renderer.py
================================
Unit tests for SubtitleRenderer.

Pillow is used for the frame-rendering path; FFmpeg is mocked for the
burn_subtitles path so tests don't require a real video or FFmpeg binary.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.subtitle_renderer import SubtitleRenderer, _contains_chinese


# ── helpers ─────────────────────────────────────────────────────────────────


class TestContainsChinese:
    def test_false_for_english(self):
        assert not _contains_chinese("Hello world")

    def test_true_for_chinese(self):
        assert _contains_chinese("繁體中文字幕")


# ── _build_force_style ───────────────────────────────────────────────────────


class TestBuildForceStyle:
    def test_contains_font_names(self):
        r = SubtitleRenderer()
        style = r._build_force_style()
        assert "Microsoft JhengHei" in style
        assert "Arial" in style

    def test_contains_alignment(self):
        r = SubtitleRenderer()
        style = r._build_force_style()
        assert "Alignment=2" in style

    def test_contains_margin(self):
        r = SubtitleRenderer()
        style = r._build_force_style()
        assert "MarginV=20" in style

    def test_white_primary_colour(self):
        r = SubtitleRenderer()
        style = r._build_force_style()
        assert "FFFFFF" in style


# ── render_frame ─────────────────────────────────────────────────────────────


class TestRenderFrame:
    @pytest.fixture
    def pil_frame(self):
        """Create a small test image."""
        try:
            from PIL import Image
            return Image.new("RGB", (640, 360), color=(30, 30, 30))
        except ImportError:
            pytest.skip("Pillow not installed")

    def test_render_returns_rgb_image(self, pil_frame):
        from PIL import Image
        r = SubtitleRenderer()
        result = r.render_frame(pil_frame, "Hello World")
        assert result.mode == "RGB"
        assert result.size == pil_frame.size

    def test_render_chinese_text(self, pil_frame):
        from PIL import Image
        r = SubtitleRenderer()
        result = r.render_frame(pil_frame, "繁體中文字幕")
        assert result.mode == "RGB"

    def test_render_empty_text(self, pil_frame):
        """Should not raise even with empty text."""
        r = SubtitleRenderer()
        result = r.render_frame(pil_frame, "")
        assert result is not None


# ── burn_subtitles (FFmpeg mocked) ────────────────────────────────────────────


class TestBurnSubtitles:
    def test_calls_ffmpeg(self, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00")
        srt = tmp_path / "video.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        out = tmp_path / "output.mp4"

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            r = SubtitleRenderer()
            result = r.burn_subtitles(video, srt, out)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-vf" in cmd
        assert result == out

    def test_raises_on_ffmpeg_failure(self, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"\x00")
        srt = tmp_path / "video.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        out = tmp_path / "output.mp4"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error: codec not found"

        with patch("subprocess.run", return_value=mock_result):
            r = SubtitleRenderer()
            with pytest.raises(RuntimeError, match="FFmpeg subtitle burning failed"):
                r.burn_subtitles(video, srt, out)
