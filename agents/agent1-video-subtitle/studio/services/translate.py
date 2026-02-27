import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


ProgressCb = Callable[[int, str], None]


@dataclass(frozen=True)
class TranslateResult:
    zh_tw_srt_path: Path


def pro_translate_srt_to_zh_tw(
    *,
    venv_python: Path,
    tool_script: Path,
    input_srt: Path,
    output_srt: Path,
    progress_cb: Optional[ProgressCb] = None,
) -> TranslateResult:
    if progress_cb:
        progress_cb(65, "專業翻譯（繁中）中（背景執行）...")

    if not venv_python.exists():
        raise FileNotFoundError(f"venv python not found: {venv_python}")
    if not tool_script.exists():
        raise FileNotFoundError(f"translator tool not found: {tool_script}")
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
        raise RuntimeError(f"專業翻譯失敗（exit={proc.returncode}）：\n{proc.stdout}\n{proc.stderr}")

    if progress_cb:
        progress_cb(85, f"翻譯完成：{output_srt.name}")
    return TranslateResult(zh_tw_srt_path=output_srt)

