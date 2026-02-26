"""
tests/test_subtitle_generator.py
=================================
Unit tests for SubtitleGenerator.

These tests mock the openai-whisper dependency so they run without a GPU
or the large whisper package installed.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.subtitle_generator import SubtitleGenerator


# ── _format_timestamp ──────────────────────────────────────────────────────


class TestFormatTimestamp:
    def test_zero(self):
        assert SubtitleGenerator._format_timestamp(0.0) == "00:00:00,000"

    def test_one_second(self):
        assert SubtitleGenerator._format_timestamp(1.0) == "00:00:01,000"

    def test_one_minute(self):
        assert SubtitleGenerator._format_timestamp(60.0) == "00:01:00,000"

    def test_one_hour(self):
        assert SubtitleGenerator._format_timestamp(3600.0) == "01:00:00,000"

    def test_fractional_seconds(self):
        assert SubtitleGenerator._format_timestamp(1.5) == "00:00:01,500"

    def test_complex(self):
        # 1h 2m 3.456s
        seconds = 3600 + 120 + 3.456
        assert SubtitleGenerator._format_timestamp(seconds) == "01:02:03,456"


# ── _segments_to_srt ──────────────────────────────────────────────────────


class TestSegmentsToSrt:
    def test_empty(self):
        result = SubtitleGenerator._segments_to_srt([])
        assert result == ""

    def test_single_segment(self):
        segments = [{"start": 0.0, "end": 2.5, "text": " Hello world"}]
        result = SubtitleGenerator._segments_to_srt(segments)
        assert result == "1\n00:00:00,000 --> 00:00:02,500\nHello world\n"

    def test_multiple_segments(self):
        segments = [
            {"start": 0.0, "end": 1.0, "text": " First"},
            {"start": 1.5, "end": 3.0, "text": " Second"},
        ]
        result = SubtitleGenerator._segments_to_srt(segments)
        lines = result.split("\n\n")
        assert len(lines) == 2
        assert lines[0].startswith("1\n")
        assert lines[1].startswith("2\n")


# ── generate (mocked whisper) ─────────────────────────────────────────────


class TestGenerate:
    def _make_fake_whisper_module(self, segments):
        """Return a fake whisper module."""
        fake_model = MagicMock()
        fake_model.transcribe.return_value = {"segments": segments}

        fake_whisper = MagicMock()
        fake_whisper.load_model.return_value = fake_model
        return fake_whisper

    def test_generate_creates_srt(self, tmp_path):
        # Create a dummy video file
        video = tmp_path / "test.mp4"
        video.write_bytes(b"\x00" * 16)

        segments = [
            {"start": 0.0, "end": 2.0, "text": " Hello"},
            {"start": 2.5, "end": 5.0, "text": " World"},
        ]
        fake_whisper = self._make_fake_whisper_module(segments)

        with patch.dict("sys.modules", {"whisper": fake_whisper, "torch": MagicMock()}):
            gen = SubtitleGenerator(model_size="tiny")
            # Pre-load the fake model
            gen._model = fake_whisper.load_model("tiny")
            srt_path = gen.generate(video, output_dir=tmp_path)

        assert srt_path.exists()
        content = srt_path.read_text(encoding="utf-8")
        assert "Hello" in content
        assert "World" in content
        assert "-->" in content

    def test_generate_raises_on_missing_file(self, tmp_path):
        gen = SubtitleGenerator()
        with pytest.raises(FileNotFoundError):
            gen.generate(tmp_path / "nonexistent.mp4")

    def test_generate_custom_output_filename(self, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"\x00")

        segments = [{"start": 0.0, "end": 1.0, "text": " Test"}]
        fake_whisper = self._make_fake_whisper_module(segments)

        with patch.dict("sys.modules", {"whisper": fake_whisper, "torch": MagicMock()}):
            gen = SubtitleGenerator(model_size="tiny")
            gen._model = fake_whisper.load_model("tiny")
            srt_path = gen.generate(
                video,
                output_dir=tmp_path,
                output_filename="custom_name",
            )

        assert srt_path.name == "custom_name.srt"
