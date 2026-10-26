"""Cắt + chuẩn hoá một đoạn video về cùng kích thước/fps (chỉ hình, không audio)."""
from __future__ import annotations

from pathlib import Path

from videobulkremixer.ff import CancelCheck, MediaInfo, probe, run_ffmpeg

TARGET_FPS = 30


def get_duration(video: Path) -> float:
    return probe(str(video)).duration


def get_resolution(video: Path) -> tuple[int, int]:
    info = probe(str(video))
    return info.width, info.height


def detect_ratio(video: Path) -> str:
    return probe(str(video)).ratio


def render_clip(
    src: Path,
    start: float,
    duration: float,
    width: int,
    height: int,
    output: Path,
    cancel: CancelCheck | None = None,
) -> Path:
    """Lấy `duration` giây từ `start`, co/đệm về width×height (giữ tỉ lệ, viền đen), bỏ audio.

    Luôn re-encode H.264 để các đoạn ghép lại được với nhau mà không lệch khung hình.
    """
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps={TARGET_FPS},format=yuv420p"
    )
    run_ffmpeg([
        "-ss", f"{max(start, 0):.3f}", "-i", str(src), "-t", f"{max(duration, 0.04):.3f}",
        "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-movflags", "+faststart", str(output),
    ], cancel=cancel)
    return output


def info_of(video: Path) -> MediaInfo:
    return probe(str(video))
