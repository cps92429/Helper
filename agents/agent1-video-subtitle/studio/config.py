import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, Dict, List


@dataclass(frozen=True)
class Agent1Config:
    turbo_transcribe_ps1: Path
    faster_whisper_exe: Optional[Path]
    model_policy: Dict[str, Any]
    ffmpeg_exe: str
    default_output_dir_name: str


def load_agent1_config(repo_root: Path) -> Agent1Config:
    cfg_path = repo_root / "agents" / "agent1-video-subtitle" / "agent1.config.json"
    data = json.loads(cfg_path.read_text(encoding="utf-8"))

    turbo = Path(data["transcription"]["turbo_transcribe_ps1"])
    fw = data.get("transcription", {}).get("faster_whisper_exe", "")
    fw_path = Path(fw) if fw else None
    model_policy = data.get("transcription", {}).get("model_policy", {}) or {}
    ffmpeg = data.get("ffmpeg", {}).get("ffmpeg_exe", "ffmpeg")
    output_dir_name = data.get("defaults", {}).get("output_dir_name", "Output")

    return Agent1Config(
        turbo_transcribe_ps1=turbo,
        faster_whisper_exe=fw_path,
        model_policy=model_policy,
        ffmpeg_exe=str(ffmpeg),
        default_output_dir_name=str(output_dir_name),
    )


def resolve_repo_root_from_file(this_file: Path) -> Path:
    # agents/agent1-video-subtitle/studio/... -> repo root is 3 parents up
    return this_file.resolve().parents[3]
