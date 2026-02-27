from pathlib import Path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def find_best_srt(output_dir: Path, base_name: str) -> Path:
    # Preferred: exact base.srt
    candidate = output_dir / f"{base_name}.srt"
    if candidate.exists():
        return candidate

    # Fallback: newest SRT that starts with base name.
    matches = sorted(
        [p for p in output_dir.glob(f"{base_name}*.srt") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]

    # Last resort: newest SRT in directory.
    any_srt = sorted(
        [p for p in output_dir.glob("*.srt") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if any_srt:
        return any_srt[0]

    raise FileNotFoundError(f"No .srt found in: {output_dir}")

