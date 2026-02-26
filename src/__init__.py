"""
Local Copilot AI – Video Subtitle Generation & Translation System
=================================================================
Package initialiser – exposes core public API.
"""

from .subtitle_generator import SubtitleGenerator
from .subtitle_translator import SubtitleTranslator
from .subtitle_renderer import SubtitleRenderer
from .video_processor import VideoProcessor
from .agent import CopilotAgent

__all__ = [
    "SubtitleGenerator",
    "SubtitleTranslator",
    "SubtitleRenderer",
    "VideoProcessor",
    "CopilotAgent",
]

__version__ = "1.0.0"
