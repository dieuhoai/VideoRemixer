"""API file: liệt kê video/audio, đọc thông tin, ảnh khung hình, phát video có tua, chọn thư mục."""
from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from videobulkremixer.ff import _NO_WINDOW, FFmpegError, ffmpeg_bin, probe
from videobulkremixer.orchestrator import VIDEO_EXTS, list_videos

router = APIRouter(prefix="/api/fs")
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac"}
MEDIA_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/mp4", ".webm": "video/webm",
               ".mkv": "video/x-matroska", ".avi": "video/x-msvideo", ".mp3": "audio/mpeg", ".wav": "audio/wav",
               ".m4a": "audio/mp4", ".aac": "audio/aac", ".ogg": "audio/ogg", ".flac": "audio/flac"}


def _checked_file(path: str, allowed: set[str]) -> Path:
    p = Path(path)
    if p.suffix.lower() not in allowed or not p.is_file():
        raise HTTPException(404, "Không tìm thấy file")
    return p


def _info(p: Path) -> dict[str, Any]:
    try:
        m = probe(str(p))
    except FFmpegError as e:
        return {"name": p.name, "path": str(p), "duration": None, "resolution": "", "error": str(e)}
    res = f"{m.width}×{m.height}" if m.width else ""
    return {"name": p.name, "path": str(p), "duration": round(m.duration, 2), "resolution": res,
            "ratio": m.ratio if m.width else "", "has_audio": m.has_audio}


@router.get("/list")
def list_files(dir: str = Query(...), kind: str = Query("video")) -> dict:
    d = Path(dir)
    if not d.is_dir():
        return {"files": [], "error": "Thư mục không tồn tại"}
    files = list_videos(d) if kind == "video" else sorted(
        f for f in d.iterdir() if f.is_file() and f.suffix.lower() in AUDIO_EXTS and not f.name.startswith("."))
    files = files[:500]
    with ThreadPoolExecutor(max_workers=6) as pool:
        infos = list(pool.map(_info, files))
    return {"files": infos}


@router.get("/probe")
def probe_file(path: str = Query(...)) -> dict:
    p = _checked_file(path, VIDEO_EXTS | AUDIO_EXTS)
    return _info(p)


@router.get("/pick")
def pick_dir() -> dict:
    """Mở hộp thoại chọn thư mục của hệ điều hành. Không mở được → trả chuỗi rỗng (người dùng gõ đường dẫn)."""
    try:
        from ..picker import pick_directory
        path = pick_directory()
    except Exception:  # noqa: BLE001
        path = None
    return {"path": str(path) if path else ""}


@router.get("/media")
def media(request: Request, path: str = Query(...)) -> Response:
    """Phát video trong trình duyệt — hỗ trợ Range để tua được."""
    p = _checked_file(path, VIDEO_EXTS | AUDIO_EXTS)
    ctype = MEDIA_TYPES.get(p.suffix.lower(), "application/octet-stream")
    size = p.stat().st_size
    rng = request.headers.get("range")
    if not rng or not rng.startswith("bytes="):
        return FileResponse(p, media_type=ctype, headers={"Accept-Ranges": "bytes"})
    start_s, _, end_s = rng[6:].partition("-")
    start = int(start_s) if start_s else max(0, size - int(end_s))
    end = min(int(end_s), size - 1) if end_s and start_s else size - 1
    if start > end or start >= size:
        raise HTTPException(416, "Vượt quá kích thước file")
    length = end - start + 1

    def chunks():
        with open(p, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                data = f.read(min(1 << 16, left))
                if not data:
                    break
                left -= len(data)
                yield data

    headers = {"Content-Range": f"bytes {start}-{end}/{size}", "Accept-Ranges": "bytes",
               "Content-Length": str(length)}
    return StreamingResponse(chunks(), status_code=206, media_type=ctype, headers=headers)


@router.get("/frame")
def frame(path: str = Query(...), t: float = Query(0.0, ge=0), w: int = Query(1280, ge=40, le=3840)) -> Response:
    """Ảnh một khung hình (JPEG) để vẽ vùng text — trả kèm kích thước thật của video."""
    p = _checked_file(path, VIDEO_EXTS)
    try:
        info = probe(str(p))
    except FFmpegError as e:
        raise HTTPException(422, str(e)) from e
    t = min(t, max(info.duration - 0.05, 0))
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(p),
           "-frames:v", "1", "-vf", f"scale='min({w},iw)':-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=_NO_WINDOW)
    if r.returncode != 0 or not r.stdout:
        raise HTTPException(422, "Không lấy được khung hình tại thời điểm này")
    return Response(r.stdout, media_type="image/jpeg",
                    headers={"X-Video-Width": str(info.width), "X-Video-Height": str(info.height),
                             "X-Video-Duration": f"{info.duration:.2f}", "Cache-Control": "no-store"})


@router.post("/open")
def open_folder(body: dict) -> dict:
    """Mở thư mục kết quả trong Finder / Explorer."""
    d = Path(str(body.get("path", "")))
    if not d.is_dir():
        raise HTTPException(404, "Thư mục không tồn tại")
    if sys.platform == "win32":
        os.startfile(str(d))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(d)])
    else:
        subprocess.Popen(["xdg-open", str(d)])
    return {"opened": True}


__all__ = ["router", "FileResponse"]
