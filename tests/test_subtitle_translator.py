"""
tests/test_subtitle_translator.py
==================================
Unit tests for SubtitleTranslator.

The deep-translator dependency is mocked so these tests run offline.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.subtitle_translator import SubtitleTranslator, _contains_chinese


# ── helpers ────────────────────────────────────────────────────────────────


class TestContainsChinese:
    def test_empty(self):
        assert not _contains_chinese("")

    def test_english_only(self):
        assert not _contains_chinese("Hello world")

    def test_simplified_chinese(self):
        assert _contains_chinese("你好")

    def test_traditional_chinese(self):
        assert _contains_chinese("繁體中文")

    def test_mixed(self):
        assert _contains_chinese("Hello 世界")


# ── _parse_srt / _blocks_to_srt ─────────────────────────────────────────────


SRT_CONTENT = """\
1
00:00:00,000 --> 00:00:02,000
Hello world

2
00:00:02,500 --> 00:00:05,000
This is a test
"""


class TestSrtParsing:
    def test_parse_basic(self):
        translator = SubtitleTranslator()
        blocks = translator._parse_srt(SRT_CONTENT)
        assert len(blocks) == 2
        assert blocks[0]["index"] == 1
        assert blocks[0]["timestamp"] == "00:00:00,000 --> 00:00:02,000"
        assert blocks[0]["text"] == "Hello world"

    def test_roundtrip(self):
        translator = SubtitleTranslator()
        blocks = translator._parse_srt(SRT_CONTENT)
        serialised = translator._blocks_to_srt(blocks)
        re_parsed = translator._parse_srt(serialised)
        assert len(re_parsed) == len(blocks)
        for orig, reparsed in zip(blocks, re_parsed):
            assert orig["text"] == reparsed["text"]

    def test_parse_empty(self):
        translator = SubtitleTranslator()
        assert translator._parse_srt("") == []


# ── translate_text ─────────────────────────────────────────────────────────


class TestTranslateText:
    def _make_translator(self, return_value: str) -> SubtitleTranslator:
        mock_gt = MagicMock()
        mock_gt.translate.return_value = return_value

        fake_module = MagicMock()
        fake_module.GoogleTranslator.return_value = mock_gt

        t = SubtitleTranslator()
        t._translator = mock_gt
        return t

    def test_translate_english(self):
        t = self._make_translator("哈囉世界")
        result = t.translate_text("Hello world")
        assert result == "哈囉世界"

    def test_already_chinese_skipped(self):
        t = self._make_translator("should not be called")
        result = t.translate_text("你好世界")
        assert result == "你好世界"
        t._translator.translate.assert_not_called()

    def test_empty_string(self):
        t = self._make_translator("")
        result = t.translate_text("")
        assert result == ""

    def test_retry_on_failure(self):
        mock_gt = MagicMock()
        mock_gt.translate.side_effect = [Exception("network error"), "成功"]

        t = SubtitleTranslator(retry_delay=0)
        t._translator = mock_gt
        result = t.translate_text("Hello")
        assert result == "成功"
        assert mock_gt.translate.call_count == 2

    def test_all_retries_exhausted_returns_original(self):
        mock_gt = MagicMock()
        mock_gt.translate.side_effect = Exception("always fails")

        t = SubtitleTranslator(max_retries=2, retry_delay=0)
        t._translator = mock_gt
        result = t.translate_text("Hello")
        assert result == "Hello"


# ── translate_srt ──────────────────────────────────────────────────────────


class TestTranslateSrt:
    def _patched_translator(self, return_value: str) -> SubtitleTranslator:
        mock_gt = MagicMock()
        mock_gt.translate.return_value = return_value
        t = SubtitleTranslator()
        t._translator = mock_gt
        return t

    def test_translate_srt_file(self, tmp_path):
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(SRT_CONTENT, encoding="utf-8")

        t = self._patched_translator("哈囉世界 ||||| 這是測試")
        out = t.translate_srt(srt_file, output_dir=tmp_path)

        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "-->" in content

    def test_translate_srt_raises_on_missing_file(self, tmp_path):
        t = SubtitleTranslator()
        with pytest.raises(FileNotFoundError):
            t.translate_srt(tmp_path / "nonexistent.srt")

    def test_bilingual_output(self, tmp_path):
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(SRT_CONTENT, encoding="utf-8")

        mock_gt = MagicMock()
        # Return two translations separated by the batch separator
        mock_gt.translate.return_value = "你好世界 ||||| 這是一個測試"
        t = SubtitleTranslator()
        t._translator = mock_gt

        out = t.translate_srt(srt_file, output_dir=tmp_path, bilingual=True)
        content = out.read_text(encoding="utf-8")
        # Original English should still appear (bilingual mode)
        assert "Hello world" in content or "This is a test" in content
