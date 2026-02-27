from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JobOptions:
    transcribe: bool
    smart_segment: bool
    pro_translate_zh_tw: bool
    convert_ass: bool
    bilingual_ass: bool
    burn_in: bool


@dataclass(frozen=True)
class Job:
    input_path: Path
    options: JobOptions
