import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


ProgressCb = Callable[[int, str], None]


@dataclass(frozen=True)
class ConvertResult:
    ass_path: Path


def srt_to_ass(
    *,
    venv_python: Path,
    tool_script: Path,
    srt_path: Path,
    ass_path: Path,
    style_json: Optional[Path] = None,
    alignment: int = 2,
    progress_cb: Optional[ProgressCb] = None,
) -> ConvertResult:
    if progress_cb:
        progress_cb(85, "轉換 ASS...")

    if not venv_python.exists():
        raise FileNotFoundError(f"venv python not found: {venv_python}")
    if not tool_script.exists():
        raise FileNotFoundError(f"srt_to_ass tool not found: {tool_script}")
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT not found: {srt_path}")

    ass_path.parent.mkdir(parents=True, exist_ok=True)

    args = [str(venv_python), str(tool_script), "--input", str(srt_path), "--output", str(ass_path)]
    if style_json:
        args += ["--style-json", str(style_json)]
    args += ["--alignment", str(int(alignment))]

    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ASS 轉換失敗（exit={proc.returncode}）：\n{proc.stdout}\n{proc.stderr}")

    if progress_cb:
        progress_cb(95, f"已產生 ASS：{ass_path.name}")
    return ConvertResult(ass_path=ass_path)
