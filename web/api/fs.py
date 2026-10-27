"""API file: liệt kê video/audio, đọc thông tin, ảnh khung hình, phát video có tua, chọn thư mục."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from videobulkremixer.ff import _NO_WINDOW, FFmpegError, ffmpeg_bin, probe
from videobulkremixer.models import TransitionConfig, TransitionType
from videobulkremixer.orchestrator import VIDEO_EXTS, list_videos
from videobulkremixer.text_replacer import decode_frame, render_text_on_frame, replace_text_on_video
from videobulkremixer.video_joiner import join_with_transitions
from web.api.jobs import parse_texts

router = APIRouter(prefix="/api/fs")
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac", ".opus", ".wma", ".aif", ".aiff"}
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


@router.post("/frame-text")
def frame_with_text(body: dict) -> Response:
    """Khung hình (JPEG) đã thay text theo đúng cách chạy thật — để xem trước trên giao diện."""
    p = _checked_file(str(body.get("path", "")), VIDEO_EXTS)
    lang = str(body.get("language", "")).strip().lower()
    if not lang:
        raise HTTPException(422, "Chưa chọn ngôn ngữ để xem trước")
    try:
        info = probe(str(p))
        w_even, h_even = info.width - info.width % 2, info.height - info.height % 2
        t = min(max(float(body.get("t", 0) or 0), 0.0), max(info.duration - 0.05, 0.0))
        replacements = parse_texts(body.get("regions") or [])
        frame = decode_frame(p, t, w_even, h_even)
        out = render_text_on_frame(frame, replacements, lang, t=t)
    except FFmpegError as e:
        raise HTTPException(422, str(e)) from e
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(422, f"Vùng text chưa đúng: {e}") from e
    max_w = min(max(int(body.get("w", 1280) or 1280), 40), 3840)
    if out.shape[1] > max_w:
        scale = max_w / out.shape[1]
        out = cv2.resize(out, (max_w, max(2, int(out.shape[0] * scale) // 2 * 2)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise HTTPException(422, "Không tạo được ảnh xem trước")
    return Response(buf.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/clip-text")
def clip_with_text(body: dict) -> Response:
    """Đoạn video ngắn (có tiếng) đã thay text đúng cách chạy thật — để xem trước trong trình phát."""
    p = _checked_file(str(body.get("path", "")), VIDEO_EXTS)
    lang = str(body.get("language", "")).strip().lower()
    if not lang:
        raise HTTPException(422, "Chưa chọn ngôn ngữ để xem trước")
    work = Path(tempfile.mkdtemp(prefix="vrm_clip_"))
    try:
        info = probe(str(p))
        start = min(max(float(body.get("t", 0) or 0), 0.0), max(info.duration - 1.0, 0.0))
        dur = min(max(float(body.get("duration", 8) or 8), 2.0), 15.0, info.duration - start)
        replacements = parse_texts(body.get("regions") or [])
        clip = work / "clip.mp4"
        r = subprocess.run(
            [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
             "-i", str(p), "-vf", "scale='2*floor(min(1280,iw)/2)':-2", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(clip)],
            capture_output=True, timeout=120, creationflags=_NO_WINDOW,
        )
        if r.returncode != 0:
            raise FFmpegError("không cắt được đoạn xem trước")
        res = replace_text_on_video(clip, replacements, lang, work / "text.mp4", time_offset=start)
        if res.output is None:
            raise HTTPException(422, "Chưa có text nào cho ngôn ngữ này")
        final = work / "preview.mp4"
        r = subprocess.run(
            [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(res.output), "-i", str(clip),
             "-map", "0:v:0", "-map", "1:a:0?", "-c", "copy", "-movflags", "+faststart", str(final)],
            capture_output=True, timeout=120, creationflags=_NO_WINDOW,
        )
        if r.returncode != 0:
            raise FFmpegError("không ghép được đoạn xem trước")
        data = final.read_bytes()
    except FFmpegError as e:
        raise HTTPException(422, str(e)) from e
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(422, f"Vùng text chưa đúng: {e}") from e
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return Response(data, media_type="video/mp4", headers={"Cache-Control": "no-store"})


def _cut_clip(src: Path, start: float, dur: float, out: Path) -> None:
    r = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
         "-i", str(src), "-vf", "scale='2*floor(min(1280,iw)/2)':-2", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(out)],
        capture_output=True, timeout=120, creationflags=_NO_WINDOW,
    )
    if r.returncode != 0:
        raise FFmpegError("không cắt được đoạn xem thử")


@router.post("/transition-preview")
def transition_preview(body: dict) -> Response:
    """Đoạn 3 giây thật: 2 giây từ video đang xem + 2 giây sau, nối bằng đúng hiệu ứng đã chọn."""
    p = _checked_file(str(body.get("path", "")), VIDEO_EXTS)
    try:
        kind = TransitionType(str(body.get("type", "")))
    except ValueError as e:
        raise HTTPException(422, "Hiệu ứng không hợp lệ") from e
    if kind == TransitionType.NONE:
        raise HTTPException(422, "Chưa chọn hiệu ứng để xem thử")
    try:
        duration = float(body.get("duration", 1.0))
    except (TypeError, ValueError) as e:
        raise HTTPException(422, "Thời lượng hiệu ứng không hợp lệ") from e
    if not 0.2 <= duration <= 1.5:
        raise HTTPException(422, "Thời lượng hiệu ứng phải từ 0,2 đến 1,5 giây")
    work = Path(tempfile.mkdtemp(prefix="vrm_tr_"))
    try:
        info = probe(str(p))
        start = min(max(float(body.get("t", 0) or 0), 0.0), max(info.duration - 4.0, 0.0))
        if info.duration < 4.0:
            raise HTTPException(422, "Video quá ngắn để xem thử (cần ít nhất 4 giây)")
        a, b, out = work / "a.mp4", work / "b.mp4", work / "preview.mp4"
        _cut_clip(p, start, 2.0, a)
        _cut_clip(p, start + 2.0, 2.0, b)
        join_with_transitions([a, b], [TransitionConfig(kind, duration)], out, work)
        data = out.read_bytes()
    except FFmpegError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return Response(data, media_type="video/mp4", headers={"Cache-Control": "no-store"})


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
