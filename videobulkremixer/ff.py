"""Gọi ffmpeg/ffprobe: tìm binary, chạy có thể huỷ, đọc thông tin video (có cache)."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from videobulkremixer.defaults import resource_root

CancelCheck = Callable[[], bool]
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class FFmpegError(RuntimeError):
    """ffmpeg chạy lỗi — message đã rút gọn, không kèm log kỹ thuật dài."""


class Cancelled(RuntimeError):
    """Người dùng bấm Dừng giữa chừng."""


class DiskFull(RuntimeError):
    """Ổ đĩa đầy khi đang ghi file."""


def _binary(name: str) -> str:
    exe = f"{name}.exe" if os.name == "nt" else name
    local = resource_root() / "bin" / exe
    return str(local) if local.is_file() else name


def ffmpeg_bin() -> str:
    return _binary("ffmpeg")


def ffprobe_bin() -> str:
    return _binary("ffprobe")


def run_ffmpeg(args: list[str], cancel: CancelCheck | None = None, timeout: float | None = None) -> None:
    """Chạy ffmpeg; nếu cancel() trả True thì giết tiến trình và ném Cancelled."""
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(
            [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y", *args],
            stdout=subprocess.DEVNULL, stderr=err, creationflags=_NO_WINDOW,
        )
        started = time.monotonic()
        while True:
            try:
                rc = proc.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                if cancel and cancel():
                    proc.kill()
                    proc.wait()
                    raise Cancelled() from None
                if timeout and time.monotonic() - started > timeout:
                    proc.kill()
                    proc.wait()
                    raise FFmpegError("xử lý quá lâu, bỏ qua file này") from None
        if rc != 0:
            err.seek(0)
            tail = err.read()[-600:].decode("utf-8", "replace")
            if "No space left" in tail:
                raise DiskFull()
            raise FFmpegError(_friendly(tail))


def _friendly(tail: str) -> str:
    low = tail.lower()
    if "no such file" in low:
        return "không tìm thấy file"
    if "invalid data" in low or "moov atom not found" in low or "could not find codec" in low:
        return "file video bị hỏng hoặc codec không hỗ trợ"
    return "ffmpeg không xử lý được file này"


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool

    @property
    def ratio(self) -> str:
        from math import gcd
        g = gcd(self.width, self.height) or 1
        rw, rh = self.width // g, self.height // g
        names = {(9, 16): "9x16", (16, 9): "16x9", (1, 1): "1x1", (4, 5): "4x5", (5, 4): "5x4"}
        return names.get((rw, rh), f"{rw}x{rh}")


@lru_cache(maxsize=512)
def probe(path: str) -> MediaInfo:
    """Đọc thời lượng, kích thước, fps, có audio hay không. Lỗi → ném FFmpegError."""
    cmd = [ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, creationflags=_NO_WINDOW)
    except FileNotFoundError as e:
        raise FFmpegError("không tìm thấy ffmpeg trong bin/") from e
    if r.returncode != 0:
        raise FFmpegError("file video bị hỏng hoặc không đọc được")
    info = json.loads(r.stdout or "{}")
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = any(s.get("codec_type") == "audio" for s in streams)
    dur = float(info.get("format", {}).get("duration") or 0)
    if video is None:
        if not audio or dur <= 0:
            raise FFmpegError("file không có hình ảnh hoặc âm thanh (không phải video/audio)")
        return MediaInfo(duration=dur, width=0, height=0, fps=0.0, has_audio=True)
    num, _, den = str(video.get("avg_frame_rate") or "30/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    dur = dur or float(video.get("duration") or 0)
    return MediaInfo(
        duration=dur, width=int(video["width"]), height=int(video["height"]),
        fps=fps if fps > 0 else 30.0, has_audio=audio,
    )


def clear_probe_cache() -> None:
    probe.cache_clear()
