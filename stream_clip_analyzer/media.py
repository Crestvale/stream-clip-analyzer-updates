from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Iterable

from .models import ClipCandidate

ProgressCallback = Callable[[str], None]


def _bundled_binary(name: str) -> str | None:
    if not getattr(sys, "frozen", False):
        return None

    roots: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root).resolve())
    executable = Path(sys.executable).resolve()
    roots.append(executable.parent)

    seen: set[Path] = set()
    for root in roots:
        candidates = (
            root / "bin" / name,
            root / name,
            root.parent / "Frameworks" / "bin" / name,
            root.parent / "Resources" / "bin" / name,
        )
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if resolved == executable:
                continue
            if resolved.name == name and resolved.is_file() and os.access(resolved, os.X_OK):
                return str(resolved)
    return None


def find_binary(name: str) -> str:
    path = _bundled_binary(name) or shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} が見つかりません。FFmpegをインストールしてください。")
    return path


def run_command(command: list[str]) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(command, capture_output=True, text=True, creationflags=flags)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "動画処理に失敗しました")


def media_duration(source: str | Path) -> float:
    command = [
        find_binary("ffprobe"), "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(source),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def safe_filename(name: str) -> str:
    cleaned = "".join("_" if c in '/\\:*?\"<>|' or ord(c) < 32 else c for c in name).strip(" .")
    return cleaned or "clip"


def video_filter(vertical: bool) -> str | None:
    if not vertical:
        return None
    return "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1"


def render_clip(source: str | Path, candidate: ClipCandidate, output: str | Path, vertical: bool | None = None) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    use_vertical = candidate.vertical if vertical is None else vertical
    command = [
        find_binary("ffmpeg"), "-y", "-ss", f"{candidate.start:.3f}", "-i", str(source),
        "-t", f"{candidate.duration:.3f}",
    ]
    vf = video_filter(use_vertical)
    if vf:
        command += ["-vf", vf]
    command += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output),
    ]
    run_command(command)


class PreviewManager:
    def __init__(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="stream-clip-analyzer-preview-")

    @property
    def directory(self) -> Path:
        return Path(self._temp.name)

    def create(self, source: str | Path, candidate: ClipCandidate, index: int) -> Path:
        old = Path(candidate.preview_path) if candidate.preview_path else None
        output = self.directory / f"preview_{index:03d}_{uuid.uuid4().hex}.mp4"
        staging = output.with_suffix(".tmp.mp4")
        staging.unlink(missing_ok=True)
        render_clip(source, candidate, staging)
        os.replace(staging, output)
        if old and old != output:
            old.unlink(missing_ok=True)
        candidate.preview_path = str(output)
        candidate.confirmed = False
        return output

    def invalidate(self, candidate: ClipCandidate) -> None:
        if candidate.preview_path:
            Path(candidate.preview_path).unlink(missing_ok=True)
        candidate.preview_path = None
        candidate.confirmed = False

    def cleanup(self) -> None:
        self._temp.cleanup()


def confirmed_candidates(candidates: Iterable[ClipCandidate]) -> list[ClipCandidate]:
    return [item for item in candidates if item.confirmed]


def export_individual(source: str | Path, candidates: Iterable[ClipCandidate], output_dir: str | Path) -> list[Path]:
    items = confirmed_candidates(candidates)
    if not items:
        raise ValueError("確定済みの切り抜き候補がありません")
    output_dir = Path(output_dir)
    outputs: list[Path] = []
    used: set[str] = set()
    for number, item in enumerate(items, 1):
        base = safe_filename(item.name)
        name = base
        suffix = 2
        while name.casefold() in used:
            name = f"{base}_{suffix}"
            suffix += 1
        used.add(name.casefold())
        output = output_dir / f"{name}.mp4"
        render_clip(source, item, output)
        outputs.append(output)
    return outputs


def export_combined(
    source: str | Path,
    candidates: Iterable[ClipCandidate],
    output_file: str | Path,
    vertical: bool = False,
) -> Path:
    items = confirmed_candidates(candidates)
    if not items:
        raise ValueError("確定済みの切り抜き候補がありません")
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stream-clip-analyzer-export-") as folder:
        root = Path(folder)
        parts: list[Path] = []
        for number, item in enumerate(items):
            part = root / f"part_{number:04d}.mp4"
            render_clip(source, item, part, vertical=vertical)
            parts.append(part)
        manifest = root / "concat.txt"
        manifest.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        run_command([
            find_binary("ffmpeg"), "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
            "-c", "copy", "-movflags", "+faststart", str(output_file),
        ])
    return output_file
