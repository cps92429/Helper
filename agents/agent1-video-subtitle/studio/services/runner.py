from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from ..config import Agent1Config
import subprocess
from .convert import srt_to_ass
from .burn import burn_in_ass
from .jobs import Job
from .paths import ensure_dir
from .segment import smart_segment_srt
from .transcribe import choose_model_by_file_size, faster_whisper_exe_transcribe, turbo_transcribe
from .translate import pro_translate_srt_to_zh_tw


ProgressCb = Callable[[int, str], None]


@dataclass(frozen=True)
class JobResult:
    input_path: Path
    srt_path: Optional[Path]
    smart_srt_path: Optional[Path]
    zh_tw_srt_path: Optional[Path]
    ass_path: Optional[Path]
    bilingual_ass_path: Optional[Path]
    burned_video_path: Optional[Path]


def run_job(
    *,
    job: Job,
    repo_root: Path,
    cfg: Agent1Config,
    venv_python: Path,
    output_dir: Path,
    style_json: Optional[Path] = None,
    pwsh_exe: str = "pwsh",
    progress_cb: Optional[ProgressCb] = None,
) -> JobResult:
    ensure_dir(output_dir)

    srt_path: Optional[Path] = None
    smart_srt: Optional[Path] = None
    zh_tw_srt: Optional[Path] = None
    ass_path: Optional[Path] = None
    bilingual_ass: Optional[Path] = None
    burned_video: Optional[Path] = None

    if job.options.transcribe:
        tr = None
        if cfg.faster_whisper_exe and cfg.faster_whisper_exe.exists():
            try:
                model = choose_model_by_file_size(job.input_path, cfg.model_policy)
                if progress_cb:
                    progress_cb(1, f"自動選模型：{model}")
                tr = faster_whisper_exe_transcribe(
                    whisper_exe=cfg.faster_whisper_exe,
                    media_path=job.input_path,
                    output_dir=output_dir,
                    model=model,
                    translate_to_english=False,
                    progress_cb=progress_cb,
                )
            except Exception as e:
                # Graceful downgrade (inspired by auto_subtitle_pro4.py).
                if progress_cb:
                    progress_cb(5, f"faster-whisper 失敗，回退 turbo-transcribe... ({e})")

        if tr is None:
            tr = turbo_transcribe(
                pwsh_exe=pwsh_exe,
                turbo_transcribe_ps1=cfg.turbo_transcribe_ps1,
                media_path=job.input_path,
                output_dir=output_dir,
                translate_to_english=False,
                progress_cb=progress_cb,
            )
        srt_path = tr.srt_path
    else:
        # If not transcribing, expect input is an SRT.
        srt_path = job.input_path
        if progress_cb:
            progress_cb(60, f"使用既有字幕：{srt_path.name}")

    # Smart segmentation (improves readability vs. raw whisper output).
    if getattr(job.options, "smart_segment", False):
        if not srt_path:
            raise RuntimeError("Missing SRT for smart segmentation step.")
        out_srt = output_dir / f"{srt_path.stem}.smart.srt"
        seg = smart_segment_srt(
            venv_python=venv_python,
            tool_script=repo_root / "agents" / "agent1-video-subtitle" / "tools" / "smart_segment.py",
            input_srt=srt_path,
            output_srt=out_srt,
            progress_cb=progress_cb,
        )
        smart_srt = seg.srt_path
        srt_path = smart_srt

    if job.options.pro_translate_zh_tw:
        if not srt_path:
            raise RuntimeError("Missing SRT for translation step.")
        out_srt = output_dir / f"{srt_path.stem}.zh-TW.srt"
        zh = pro_translate_srt_to_zh_tw(
            venv_python=venv_python,
            tool_script=repo_root / "agents" / "agent1-video-subtitle" / "tools" / "copilot_translate_srt.py",
            input_srt=srt_path,
            output_srt=out_srt,
            progress_cb=progress_cb,
        )
        zh_tw_srt = zh.zh_tw_srt_path

    if job.options.convert_ass and not getattr(job.options, "bilingual_ass", False):
        # Prefer converting the translated SRT if present.
        src = zh_tw_srt or srt_path
        if not src:
            raise RuntimeError("Missing SRT for ASS conversion step.")
        out_ass = output_dir / f"{src.stem}.ass"
        conv = srt_to_ass(
            venv_python=venv_python,
            tool_script=repo_root / "agents" / "agent1-video-subtitle" / "tools" / "srt_to_ass.py",
            srt_path=src,
            ass_path=out_ass,
            style_json=style_json or (repo_root / "agents" / "agent1-video-subtitle" / "style.json"),
            alignment=2,
            progress_cb=progress_cb,
        )
        ass_path = conv.ass_path

    if getattr(job.options, "bilingual_ass", False):
        # Bilingual ASS: top=original, bottom=zh-TW.
        if not srt_path or not zh_tw_srt:
            raise RuntimeError("雙語 ASS 需要原文 SRT 與 zh-TW SRT。")
        out_ass = output_dir / f"{srt_path.stem}.bilingual.ass"
        proc = subprocess.run(
            [
                str(venv_python),
                str(repo_root / "agents" / "agent1-video-subtitle" / "tools" / "bilingual_ass.py"),
                "--en-srt",
                str(srt_path),
                "--zh-srt",
                str(zh_tw_srt),
                "--output",
                str(out_ass),
                "--style-json",
                str(style_json or (repo_root / "agents" / "agent1-video-subtitle" / "style.json")),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            raise RuntimeError(f"雙語 ASS 產生失敗（exit={proc.returncode}）：\n{proc.stdout}\n{proc.stderr}")
        bilingual_ass = out_ass
        if progress_cb:
            progress_cb(95, f"已產生雙語 ASS：{out_ass.name}")

    if getattr(job.options, "burn_in", False):
        # Burn-in requires a video input.
        if job.input_path.suffix.lower() in (".srt", ".ass"):
            raise RuntimeError("一鍵燒錄需要影片檔作為輸入。")
        src_ass = bilingual_ass or ass_path
        if not src_ass:
            raise RuntimeError("一鍵燒錄需要先產生 ASS。")
        out_vid = output_dir / f"{job.input_path.stem}.burned.mp4"
        burn = burn_in_ass(
            ffmpeg_exe=cfg.ffmpeg_exe,
            video_path=job.input_path,
            ass_path=src_ass,
            output_video=out_vid,
            progress_cb=progress_cb,
        )
        burned_video = burn.output_video

    if progress_cb:
        progress_cb(100, "完成")

    return JobResult(
        input_path=job.input_path,
        srt_path=srt_path,
        smart_srt_path=smart_srt,
        zh_tw_srt_path=zh_tw_srt,
        ass_path=ass_path,
        bilingual_ass_path=bilingual_ass,
        burned_video_path=burned_video,
    )
