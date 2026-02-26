"""
tests/test_agent.py
====================
Unit tests for CopilotAgent.

VideoProcessor is mocked so these tests run without Whisper or FFmpeg.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import CopilotAgent


def _make_agent() -> CopilotAgent:
    """Return an agent whose internal VideoProcessor is mocked."""
    agent = CopilotAgent.__new__(CopilotAgent)
    agent._processor = MagicMock()
    agent._on_progress = lambda msg: None
    agent._watch_thread = None
    agent._stop_watch_event = MagicMock()
    return agent


# ── list_capabilities ────────────────────────────────────────────────────────


class TestListCapabilities:
    def test_returns_all_actions(self):
        agent = _make_agent()
        result = agent.run_task({"action": "list_capabilities"})
        assert result["status"] == "ok"
        assert "process_video" in result["capabilities"]
        assert "generate_subtitles" in result["capabilities"]
        assert "translate_subtitles" in result["capabilities"]
        assert "burn_subtitles" in result["capabilities"]
        assert "watch_directory" in result["capabilities"]


# ── unknown action ────────────────────────────────────────────────────────────


class TestUnknownAction:
    def test_unknown_action_returns_error(self):
        agent = _make_agent()
        result = agent.run_task({"action": "fly_to_moon"})
        assert result["status"] == "error"
        assert "fly_to_moon" in result["message"]


# ── process_video ─────────────────────────────────────────────────────────────


class TestProcessVideo:
    def test_missing_video_path(self):
        agent = _make_agent()
        result = agent.run_task({"action": "process_video"})
        assert result["status"] == "error"
        assert "video_path" in result["message"]

    def test_delegates_to_processor(self, tmp_path):
        agent = _make_agent()
        agent._processor.process.return_value = {
            "original_srt": tmp_path / "v.srt",
            "translated_srt": tmp_path / "v_zh-TW.srt",
            "burned_video": tmp_path / "v_subtitled.mp4",
        }
        result = agent.run_task({
            "action": "process_video",
            "video_path": str(tmp_path / "v.mp4"),
            "output_dir": str(tmp_path),
        })
        assert result["status"] == "ok"
        assert "burned_video" in result
        agent._processor.process.assert_called_once()


# ── generate_subtitles ────────────────────────────────────────────────────────


class TestGenerateSubtitles:
    def test_missing_video_path(self):
        agent = _make_agent()
        result = agent.run_task({"action": "generate_subtitles"})
        assert result["status"] == "error"

    def test_delegates_to_processor(self, tmp_path):
        agent = _make_agent()
        srt = tmp_path / "test.srt"
        agent._processor.extract_subtitles.return_value = srt
        result = agent.run_task({
            "action": "generate_subtitles",
            "video_path": str(tmp_path / "v.mp4"),
        })
        assert result["status"] == "ok"
        assert "srt_path" in result


# ── translate_subtitles ───────────────────────────────────────────────────────


class TestTranslateSubtitles:
    def test_missing_srt_path(self):
        agent = _make_agent()
        result = agent.run_task({"action": "translate_subtitles"})
        assert result["status"] == "error"

    def test_delegates_to_processor(self, tmp_path):
        agent = _make_agent()
        out_srt = tmp_path / "test_zh-TW.srt"
        agent._processor.translate_subtitles.return_value = out_srt
        result = agent.run_task({
            "action": "translate_subtitles",
            "srt_path": str(tmp_path / "test.srt"),
        })
        assert result["status"] == "ok"
        assert "translated_srt" in result


# ── burn_subtitles ────────────────────────────────────────────────────────────


class TestBurnSubtitles:
    def test_missing_paths(self):
        agent = _make_agent()
        result = agent.run_task({"action": "burn_subtitles", "video_path": "v.mp4"})
        assert result["status"] == "error"
        assert "srt_path" in result["message"]

    def test_delegates_to_processor(self, tmp_path):
        agent = _make_agent()
        burned = tmp_path / "v_subtitled.mp4"
        agent._processor.burn_subtitles.return_value = burned
        result = agent.run_task({
            "action": "burn_subtitles",
            "video_path": str(tmp_path / "v.mp4"),
            "srt_path": str(tmp_path / "v.srt"),
        })
        assert result["status"] == "ok"
        assert "burned_video" in result


# ── run_task_json ─────────────────────────────────────────────────────────────


class TestRunTaskJson:
    def test_valid_json(self):
        agent = _make_agent()
        out = agent.run_task_json('{"action": "list_capabilities"}')
        data = json.loads(out)
        assert data["status"] == "ok"

    def test_invalid_json(self):
        agent = _make_agent()
        out = agent.run_task_json("not json {{{")
        data = json.loads(out)
        assert data["status"] == "error"
        assert "JSON" in data["message"]
