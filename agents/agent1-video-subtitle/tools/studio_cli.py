import argparse
import sys
from pathlib import Path
from typing import List


def _agent_dir() -> Path:
    # agents/agent1-video-subtitle/tools/studio_cli.py -> agent dir is 1 parent up from tools/
    return Path(__file__).resolve().parents[1]


def _repo_root(agent_dir: Path) -> Path:
    # agents/agent1-video-subtitle -> repo root is 2 parents up (agents -> repo)
    return agent_dir.parents[1]


def _collect_inputs(folder: Path, recursive: bool) -> List[Path]:
    exts = {".mp4", ".mkv", ".mov", ".avi", ".mp3", ".wav", ".flac", ".m4a", ".aac", ".srt"}
    it = folder.rglob("*") if recursive else folder.glob("*")
    files = [p for p in it if p.is_file() and p.suffix.lower() in exts]
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input file or folder")
    parser.add_argument("--output-dir", default="", help="Output directory (default: repo Output/)")
    parser.add_argument("--style-json", default="", help="ASS style json (default: agents/agent1-video-subtitle/style.json)")
    parser.add_argument("--recursive", action="store_true", help="Recursive folder scan")
    parser.add_argument("--transcribe", action="store_true", help="Transcribe media to SRT (ignored if input is .srt)")
    parser.add_argument("--smart-segment", action="store_true", help="Smart segment SRT")
    parser.add_argument("--pro-translate", action="store_true", help="Pro translate to zh-TW (Copilot)")
    parser.add_argument("--ass", action="store_true", help="Generate ASS from SRT")
    parser.add_argument("--bilingual-ass", action="store_true", help="Generate bilingual ASS (top=original, bottom=zh-TW)")
    parser.add_argument("--burn-in", action="store_true", help="Burn ASS into video (requires video input)")
    args = parser.parse_args()

    agent_dir = _agent_dir()
    repo_root = _repo_root(agent_dir)
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))

    from studio.config import load_agent1_config  # noqa: E402
    from studio.services.jobs import Job, JobOptions  # noqa: E402
    from studio.services.runner import run_job  # noqa: E402

    cfg = load_agent1_config(repo_root)
    venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        raise SystemExit("Missing venv. Run: .\\setup.ps1 -Target Agent1")

    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    out_dir = Path(args.output_dir).expanduser() if args.output_dir else (repo_root / cfg.default_output_dir_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    style_json = Path(args.style_json).expanduser() if args.style_json else (agent_dir / "style.json")

    if input_path.is_dir():
        inputs = _collect_inputs(input_path, recursive=bool(args.recursive))
    else:
        inputs = [input_path]

    if not inputs:
        print("No inputs found.")
        return 0

    for i, p in enumerate(inputs, start=1):
        opts = JobOptions(
            transcribe=bool(args.transcribe) and p.suffix.lower() != ".srt",
            smart_segment=bool(args.smart_segment),
            pro_translate_zh_tw=bool(args.pro_translate) or bool(args.bilingual_ass),
            convert_ass=bool(args.ass) or bool(args.bilingual_ass) or bool(args.burn_in),
            bilingual_ass=bool(args.bilingual_ass),
            burn_in=bool(args.burn_in),
        )
        job = Job(input_path=p, options=opts)

        def progress_cb(v: int, msg: str) -> None:
            print(f"[{i}/{len(inputs)}] {v:3d}% {msg}")

        res = run_job(
            job=job,
            repo_root=repo_root,
            cfg=cfg,
            venv_python=venv_python,
            output_dir=out_dir,
            style_json=style_json,
            progress_cb=progress_cb,
        )

        if res.burned_video_path:
            print(f"OK VIDEO: {res.burned_video_path}")
        elif res.bilingual_ass_path:
            print(f"OK ASS: {res.bilingual_ass_path}")
        elif res.ass_path:
            print(f"OK ASS: {res.ass_path}")
        elif res.zh_tw_srt_path:
            print(f"OK SRT: {res.zh_tw_srt_path}")
        else:
            print("OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

