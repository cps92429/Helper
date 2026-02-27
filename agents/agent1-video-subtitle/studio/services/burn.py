from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import subprocess


ProgressCb = Callable[[int, str], None]


@dataclass(frozen=True)
class BurnResult:
    output_video: Path


def burn_in_ass(
    *,
    ffmpeg_exe: str,
    video_path: Path,
    ass_path: Path,
    output_video: Path,
    progress_cb: Optional[ProgressCb] = None,
) -> BurnResult:
    if progress_cb:
        progress_cb(96, "燒錄字幕進影片（ffmpeg）...")

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not ass_path.exists():
        raise FileNotFoundError(f"ASS not found: {ass_path}")

    output_video.parent.mkdir(parents=True, exist_ok=True)

    # Burn-in requires re-encode video; keep audio stream copy.
    proc = subprocess.run(
        [ffmpeg_exe, "-y", "-i", str(video_path), "-vf", f"ass={ass_path}", "-c:a", "copy", str(output_video)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"燒錄失敗（exit={proc.returncode}）：\n{proc.stdout}\n{proc.stderr}")

    if progress_cb:
        progress_cb(100, f"燒錄完成：{output_video.name}")
    return BurnResult(output_video=output_video)

