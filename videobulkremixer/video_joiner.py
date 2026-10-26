"""Ghép các clip đã chuẩn hoá thành một video, áp hiệu ứng theo từng mối nối.

Toàn bộ các mối nối được dựng trong MỘT đồ thị ffmpeg → chỉ encode lại một lần.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from videobulkremixer.ff import CancelCheck, run_ffmpeg
from videobulkremixer.models import TransitionConfig, TransitionType
from videobulkremixer.transition import XFADE_MAP
from videobulkremixer.video_cutter import get_duration


def join_with_transitions(
    parts: Sequence[Path],
    transitions: Sequence[TransitionConfig],
    output: Path,
    work_dir: Path,  # noqa: ARG001 — giữ chữ ký thống nhất
    cancel: CancelCheck | None = None,
) -> Path:
    """Ghép parts[0..n-1]; transitions[i] là hiệu ứng tại mối nối giữa parts[i] và parts[i+1]."""
    if not parts:
        raise ValueError("không có đoạn nào để ghép")
    cfgs = [transitions[i] if i < len(transitions) else TransitionConfig(TransitionType.NONE)
            for i in range(len(parts) - 1)]
    if all(c.transition_type == TransitionType.NONE for c in cfgs):
        return _concat_copy(parts, output, cancel)

    durs = [get_duration(p) for p in parts]
    inputs: list[str] = []
    for p in parts:
        inputs += ["-i", str(p)]
    graph: list[str] = []
    cur = "0:v"
    total = durs[0]
    for i in range(1, len(parts)):
        nxt = f"{i}:v"
        label = f"v{i}"
        cfg = cfgs[i - 1]
        if cfg.transition_type == TransitionType.NONE:
            graph.append(f"[{cur}][{nxt}]concat=n=2:v=1:a=0[{label}]")
            total += durs[i]
        else:
            d = max(0.05, min(cfg.duration_sec, total / 2, durs[i] / 2))
            offset = max(0.0, total - d)
            name = XFADE_MAP[cfg.transition_type]
            graph.append(f"[{cur}][{nxt}]xfade=transition={name}:duration={d:.3f}:offset={offset:.3f}[{label}]")
            total += durs[i] - d
        cur = label
    graph.append(f"[{cur}]format=yuv420p[vout]")
    run_ffmpeg([
        *inputs, "-filter_complex", ";".join(graph), "-map", "[vout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-an", str(output),
    ], cancel=cancel)
    return output


def _concat_copy(parts: Sequence[Path], output: Path, cancel: CancelCheck | None) -> Path:
    """Không có hiệu ứng: nối bằng concat demuxer (không encode lại)."""
    listing = output.with_suffix(".list.txt")
    listing.write_text("".join("file '" + str(p).replace("'", "'\\''") + "'\n" for p in parts), encoding="utf-8")
    try:
        run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-an", str(output)],
                   cancel=cancel)
    finally:
        listing.unlink(missing_ok=True)
    return output
