import subprocess
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable, Optional, List

from .paths import ensure_dir, find_best_srt


ProgressCb = Callable[[int, str], None]


@dataclass(frozen=True)
class TranscribeResult:
    srt_path: Path


def choose_model_by_file_size(media_path: Path, model_policy: dict) -> str:
    policy = model_policy or {}
    if not policy.get("enabled", False):
        return str(policy.get("fallback_model") or "turbo")

    fallback = str(policy.get("fallback_model") or "turbo")
    try:
        size_mb = media_path.stat().st_size / (1024 * 1024)
    except Exception:
        return fallback

    rules = policy.get("rules") or []
    for rule in rules:
        try:
            model = str(rule.get("model") or "").strip()
            max_mb = rule.get("max_mb", None)
            if not model:
                continue
            if max_mb is None:
                return model
            if float(size_mb) <= float(max_mb):
                return model
        except Exception:
            continue

    return fallback


def faster_whisper_exe_transcribe(
    *,
    whisper_exe: Path,
    media_path: Path,
    output_dir: Path,
    language: str = "zh",
    model: str = "turbo",
    translate_to_english: bool,
    progress_cb: Optional[ProgressCb] = None,
) -> TranscribeResult:
    if progress_cb:
        progress_cb(0, "準備轉錄（faster-whisper-xxl.exe）...")

    if not whisper_exe.exists():
        raise FileNotFoundError(f"faster-whisper-xxl.exe not found: {whisper_exe}")
    if not media_path.exists():
        raise FileNotFoundError(f"Media not found: {media_path}")

    ensure_dir(output_dir)

    args = [
        str(whisper_exe),
        str(media_path),
        "-l",
        language,
        "-m",
        model,
        "-o",
        str(output_dir),
        "--sentence",
        "--standard_asia",
        "--print_progress",
        "--output_format",
        "srt",
        "vtt",
        "txt",
    ]
    if translate_to_english:
        args += ["--task", "translate"]

    if progress_cb:
        progress_cb(5, "轉錄中（背景執行）...")

    # Stream stdout so we can surface progress without blocking the UI.
    pct_re = re.compile(r"(?P<pct>\\b\\d{1,3})%")
    output_lines: List[str] = []
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        output_lines.append(line)
        m = pct_re.search(line)
        if m and progress_cb:
            try:
                pct = int(m.group("pct"))
                pct = max(0, min(100, pct))
                # Map 0-100 -> 5-60 for the transcribe stage.
                progress_cb(5 + int(pct * 0.55), f"轉錄中... {pct}%")
            except Exception:
                pass

    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"轉錄失敗（exit={rc}）：\n{''.join(output_lines)}")

    srt_path = find_best_srt(output_dir, base_name=media_path.stem)
    if progress_cb:
        progress_cb(60, f"轉錄完成：{srt_path.name}")
    return TranscribeResult(srt_path=srt_path)


def turbo_transcribe(
    *,
    pwsh_exe: str,
    turbo_transcribe_ps1: Path,
    media_path: Path,
    output_dir: Path,
    translate_to_english: bool,
    progress_cb: Optional[ProgressCb] = None,
) -> TranscribeResult:
    if progress_cb:
        progress_cb(0, "準備轉錄...")

    if not turbo_transcribe_ps1.exists():
        raise FileNotFoundError(f"turbo-transcribe.ps1 not found: {turbo_transcribe_ps1}")
    if not media_path.exists():
        raise FileNotFoundError(f"Media not found: {media_path}")

    ensure_dir(output_dir)

    args = [
        pwsh_exe,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(turbo_transcribe_ps1),
        str(media_path),
        "-OutputDir",
        str(output_dir),
        "-Sentence",
        "-Progress",
    ]
    if translate_to_english:
        args.append("-Translate")

    if progress_cb:
        progress_cb(5, "轉錄中（背景執行）...")

    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"轉錄失敗（exit={proc.returncode}）：\n{proc.stdout}\n{proc.stderr}")

    base = media_path.stem
    srt_path = find_best_srt(output_dir, base_name=base)
    if progress_cb:
        progress_cb(60, f"轉錄完成：{srt_path.name}")

    return TranscribeResult(srt_path=srt_path)
