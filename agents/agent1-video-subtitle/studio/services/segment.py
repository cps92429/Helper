from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import subprocess


ProgressCb = Callable[[int, str], None]


@dataclass(frozen=True)
class SegmentResult:
    srt_path: Path


def smart_segment_srt(
    *,
    venv_python: Path,
    tool_script: Path,
    input_srt: Path,
    output_srt: Path,
    progress_cb: Optional[ProgressCb] = None,
) -> SegmentResult:
    if progress_cb:
        progress_cb(62, "智慧斷句最佳化...")

    if not venv_python.exists():
        raise FileNotFoundError(f"venv python not found: {venv_python}")
    if not tool_script.exists():
        raise FileNotFoundError(f"smart_segment tool not found: {tool_script}")
    if not input_srt.exists():
        raise FileNotFoundError(f"Input SRT not found: {input_srt}")

    output_srt.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [str(venv_python), str(tool_script), "--input", str(input_srt), "--output", str(output_srt)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"智慧斷句失敗（exit={proc.returncode}）：\n{proc.stdout}\n{proc.stderr}")

    if progress_cb:
        progress_cb(65, f"斷句完成：{output_srt.name}")
    return SegmentResult(srt_path=output_srt)

