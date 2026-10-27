"""Xoá text cũ (inpaint bằng OpenCV) rồi vẽ text mới (Pillow) lên từng khung hình.

Video được đọc/ghi bằng ffmpeg qua pipe (rawvideo BGR), nên không cần lưu khung hình ra đĩa.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from videobulkremixer.defaults import resource_root
from videobulkremixer.ff import _NO_WINDOW, CancelCheck, Cancelled, DiskFull, FFmpegError, ffmpeg_bin, probe
from videobulkremixer.models import TextReplacement, TextStyle

# Tên font thường gặp → tên file trên Windows / macOS / Linux.
SYSTEM_FONT_FILES = {
    "arial": ["arial.ttf", "Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"],
    "arial bold": ["arialbd.ttf", "Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                   "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"],
    "times new roman": ["times.ttf", "Times New Roman.ttf",
                        "/System/Library/Fonts/Supplemental/Times New Roman.ttf"],
    "tahoma": ["tahoma.ttf", "Tahoma.ttf"],
    "verdana": ["verdana.ttf", "Verdana.ttf", "/System/Library/Fonts/Supplemental/Verdana.ttf"],
}
FONT_DIRS = ["C:/Windows/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts",
             "/usr/share/fonts/truetype/msttcorefonts"]
CJK_FONT_FILES = [
    "C:/Windows/Fonts/msgothic.ttc", "C:/Windows/Fonts/msyh.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def bundled_font(bold: bool) -> Path:
    """Fira Sans đi kèm app — có đủ dấu tiếng Việt."""
    return resource_root() / "videobulkremixer" / "fonts" / ("FiraSans-Bold.ttf" if bold else "FiraSans-Regular.ttf")


def resolve_font(name: str, bold: bool, needs_cjk: bool) -> tuple[Path, str]:
    """Trả (đường dẫn font, ghi chú). Không tìm được font chỉ định → dùng Fira Sans đi kèm."""
    if needs_cjk:
        for c in CJK_FONT_FILES:
            if Path(c).is_file():
                return Path(c), ""
        return bundled_font(bold), "không có font CJK trên máy, chữ Nhật/Hàn/Trung có thể không hiển thị"
    key = (name or "").strip()
    if key and Path(key).is_file():
        return Path(key), ""
    lookup = key.lower()
    if bold and lookup == "arial":
        lookup = "arial bold"
    for candidate in SYSTEM_FONT_FILES.get(lookup, []):
        if Path(candidate).is_absolute() and Path(candidate).is_file():
            return Path(candidate), ""
        for d in FONT_DIRS:
            if Path(d, candidate).is_file():
                return Path(d, candidate), ""
    note = f"font '{key}' không có trên máy, dùng Fira Sans" if key and lookup != "fira sans" else ""
    return bundled_font(bold), note


def _rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise ValueError(f"màu không hợp lệ: {color!r} (dùng dạng #RRGGBB)")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), alpha


def render_overlay(text: str, region_w: int, region_h: int, style: TextStyle) -> tuple[np.ndarray, str]:
    """Vẽ text mới thành lớp RGBA đúng kích thước vùng chọn (tự thu nhỏ nếu quá rộng)."""
    needs_cjk = any(ord(ch) > 0x2E80 and not (0x1E00 <= ord(ch) <= 0x1EFF) for ch in text)
    font_path, note = resolve_font(style.font, style.bold, needs_cjk)
    pad = max(2, style.stroke_width + 2)
    size = max(8, int(style.size))
    shrunk = False
    limit_w = max(4, region_w - 2 * pad)
    probe_img = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    while True:
        font = ImageFont.truetype(str(font_path), size)
        bbox = probe_img.textbbox((0, 0), text, font=font, stroke_width=style.stroke_width)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= limit_w or size <= 8:
            break
        shrunk = True
        size -= 2
    if shrunk:
        note = (note + "; " if note else "") + "chữ được thu nhỏ để vừa vùng"
    canvas = Image.new("RGBA", (region_w, region_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    if style.align == "left":
        x = pad
    elif style.align == "right":
        x = region_w - pad - tw
    else:
        x = (region_w - tw) / 2
    y = (region_h - th) / 2 - bbox[1]
    x = x - bbox[0]
    if style.shadow:
        draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 140), stroke_width=style.stroke_width,
                  stroke_fill=(0, 0, 0, 140))
    stroke = _rgba(style.stroke_color, 255) if style.stroke_color and style.stroke_width > 0 else None
    draw.text((x, y), text, font=font, fill=_rgba(style.color), stroke_width=style.stroke_width if stroke else 0,
              stroke_fill=stroke)
    return np.asarray(canvas, dtype=np.uint8), note


@dataclass
class TextReplaceResult:
    output: Path | None  # None = không có text nào cho ngôn ngữ này, giữ nguyên video
    note: str = ""


@dataclass
class _Region:
    name: str
    x0: int
    y0: int
    overlay: np.ndarray  # RGBA, đúng kích thước khung chứa tứ giác đã cắt theo khung hình
    poly: np.ndarray  # 255 = bên trong vùng text cũ (tứ giác)
    start: float
    end: float
    clean: tuple[np.ndarray, np.ndarray] | None = None  # (nền đã xoá chữ cũ, alpha trộn), làm mới định kỳ

    @property
    def x1(self) -> int:
        return self.x0 + self.poly.shape[1]

    @property
    def y1(self) -> int:
        return self.y0 + self.poly.shape[0]


def _quad_overlay(text: str, corners: tuple[tuple[float, float], ...], style: TextStyle, w: int, h: int
                  ) -> tuple[np.ndarray, np.ndarray, int, int, str] | None:
    """Vẽ text vào tứ giác: render phẳng rồi biến dạng theo phối cảnh. None nếu tứ giác nằm ngoài khung hình."""
    pts = np.array(corners, dtype=np.float32)
    top = float(np.linalg.norm(pts[1] - pts[0]))
    bottom = float(np.linalg.norm(pts[2] - pts[3]))
    left = float(np.linalg.norm(pts[3] - pts[0]))
    right = float(np.linalg.norm(pts[2] - pts[1]))
    tw = max(4, int(round(max(top, bottom))))
    th = max(4, int(round(max(left, right))))
    flat, note = render_overlay(text, tw, th, style)
    x0 = int(np.floor(pts[:, 0].min()))
    y0 = int(np.floor(pts[:, 1].min()))
    bw = int(np.ceil(pts[:, 0].max())) - x0 + 1
    bh = int(np.ceil(pts[:, 1].max())) - y0 + 1
    dst = pts - np.array([x0, y0], dtype=np.float32)
    src = np.float32([[0, 0], [tw - 1, 0], [tw - 1, th - 1], [0, th - 1]])
    m = cv2.getPerspectiveTransform(src, dst)
    overlay = cv2.warpPerspective(flat, m, (bw, bh), flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    poly = np.zeros((bh, bw), dtype=np.uint8)
    cv2.fillPoly(poly, [np.round(dst).astype(np.int32)], 255)
    # Cắt phần nằm ngoài khung hình
    sx, sy = max(0, -x0), max(0, -y0)
    ex, ey = min(bw, w - x0), min(bh, h - y0)
    if ex <= sx or ey <= sy:
        return None
    return overlay[sy:ey, sx:ex], poly[sy:ey, sx:ex], x0 + sx, y0 + sy, note


def _prepare(replacements: list[TextReplacement], language: str, w: int, h: int) -> tuple[list[_Region], list[str]]:
    regions: list[_Region] = []
    notes: list[str] = []
    for r in replacements:
        text = (r.texts_by_lang.get(language) or "").strip()
        if not text:
            continue
        built = _quad_overlay(text, r.region.corners(), r.style, w, h)
        if built is None:
            raise ValueError(f"vùng '{r.region.name}' nằm ngoài khung hình")
        overlay, poly, x0, y0, note = built
        if note:
            notes.append(f"{r.region.name}: {note}")
        end = float("inf") if r.end_sec is None else float(r.end_sec)
        regions.append(_Region(r.region.name, x0, y0, overlay, poly, float(r.start_sec), end))
    return regions, notes


def _clean_background(roi: np.ndarray, poly: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Xoá chữ cũ theo nét chữ thay vì cả hộp: lấy màu nền quanh vùng, chỉ inpaint pixel khác màu nền."""
    inside = poly > 0
    ring = (cv2.dilate(poly, np.ones((9, 9), np.uint8)) > 0) & ~inside
    sample = roi[ring] if ring.any() else roi[inside]
    bg = np.median(sample, axis=0) if len(sample) else np.median(roi.reshape(-1, 3), axis=0)
    diff = np.abs(roi.astype(np.int16) - bg.astype(np.int16)).max(axis=2)
    ink = (diff > 12) & inside
    if ink.sum() < 0.02 * inside.sum():  # nền gần giống màu chữ: không tách được nét, xoá cả vùng
        ink = inside
    mask = cv2.dilate(ink.astype(np.uint8) * 255, np.ones((7, 7), np.uint8))
    mask = np.where(inside, mask, 0).astype(np.uint8)
    ring_ink = np.abs(sample.astype(np.int16) - bg.astype(np.int16)).max(axis=1) if len(sample) else np.zeros(1)
    if ring.any() and float((ring_ink > 12).mean()) < 0.15:  # gần như toàn màu nền (chữ cũ không lấn ra viền)
        # Nền phẳng (một màu): tô cả vùng bằng đúng màu nền, không inpaint nên không còn vệt
        mask = inside.astype(np.uint8) * 255
        clean = np.broadcast_to(bg.astype(np.uint8), roi.shape).copy()
    else:
        clean = cv2.inpaint(roi, mask, 5, cv2.INPAINT_TELEA)
        soft = cv2.GaussianBlur(clean, (0, 0), 2.5)  # nền có chi tiết: làm mềm vùng vừa xoá
        clean = np.where(mask[..., None] > 0, soft, clean).astype(np.uint8)
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (7, 7), 0)  # mép mờ, không có viền cứng
    return clean, alpha


def _apply_regions(frame: np.ndarray, regions: list[_Region], t: float, refresh_now: bool) -> None:
    """Xoá text cũ rồi vẽ text mới lên `frame` (BGR, sửa tại chỗ) cho các vùng đang hiện tại t giây."""
    for reg in regions:
        if not (reg.start <= t < reg.end):
            reg.clean = None  # lần sau hiện lại sẽ xoá nền từ khung mới
            continue
        roi = frame[reg.y0:reg.y1, reg.x0:reg.x1]
        if reg.clean is None or refresh_now:
            reg.clean = _clean_background(roi.copy(), reg.poly)
        clean, alpha = reg.clean
        a = alpha[..., None]
        base = roi.astype(np.float32) * (1 - a) + clean.astype(np.float32) * a
        ov = reg.overlay
        oa = ov[..., 3:4].astype(np.float32) / 255.0
        rgb_bgr = ov[..., [2, 1, 0]].astype(np.float32)
        roi[...] = (base * (1 - oa) + rgb_bgr * oa).astype(np.uint8)


def decode_frame(video: Path, t: float, w: int, h: int) -> np.ndarray:
    """Đọc đúng 1 khung hình (BGR) tại giây t, cắt về w x h (số chẵn)."""
    r = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video),
         "-frames:v", "1", "-an", "-vf", f"crop={w}:{h}:0:0", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        capture_output=True, timeout=60, creationflags=_NO_WINDOW,
    )
    if r.returncode != 0 or len(r.stdout) < w * h * 3:
        raise FFmpegError("không lấy được khung hình để xem trước")
    return np.frombuffer(r.stdout[: w * h * 3], dtype=np.uint8).reshape(h, w, 3).copy()


def render_text_on_frame(frame: np.ndarray, replacements: list[TextReplacement], language: str,
                         t: float = 0.0) -> np.ndarray:
    """Áp text thay thế của `language` lên một khung hình BGR tại giây t (dùng cho xem trước). Trả về ảnh mới."""
    out = frame.copy()
    h, w = out.shape[:2]
    regions, _ = _prepare(replacements, language, w, h)
    _apply_regions(out, regions, t, refresh_now=True)
    return out


def replace_text_on_video(
    video: Path,
    replacements: list[TextReplacement],
    language: str,
    output: Path,
    cancel: CancelCheck | None = None,
    time_offset: float = 0.0,  # giây của khung hình đầu tiên trong `video`, để khớp mốc thời gian của đoạn text
) -> TextReplaceResult:
    """Thay text cho `language` lên đúng các khoảng thời gian đã chọn (chỉ hình, giữ nguyên âm thanh)."""
    active = [r for r in replacements if (r.texts_by_lang.get(language) or "").strip()]
    if not active:
        return TextReplaceResult(output=None)

    info = probe(str(video))
    w, h = info.width - info.width % 2, info.height - info.height % 2  # yuv420p cần số chẵn
    regions, notes = _prepare(active, language, w, h)
    frame_bytes = w * h * 3
    fps = f"{info.fps:.3f}"
    refresh = max(1, int(info.fps // 3))  # xoá nền lại ~3 lần/giây: đủ cho nền tĩnh và nền chuyển chậm

    with tempfile.TemporaryFile() as dec_err, tempfile.TemporaryFile() as enc_err:
        dec = subprocess.Popen(
            [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(video),
             "-an", "-vf", f"crop={w}:{h}:0:0", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
            stdout=subprocess.PIPE, stderr=dec_err, creationflags=_NO_WINDOW,
        )
        enc = subprocess.Popen(
            [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", fps, "-i", "-",
             "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(output)],
            stdin=subprocess.PIPE, stderr=enc_err, creationflags=_NO_WINDOW,
        )

        def _kill() -> None:
            for p in (dec, enc):
                if p.poll() is None:
                    p.kill()
                    p.wait()

        try:
            index = 0
            while True:
                raw = dec.stdout.read(frame_bytes)
                if len(raw) < frame_bytes:
                    break
                if cancel and index % 10 == 0 and cancel():
                    raise Cancelled()
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3).copy()
                _apply_regions(frame, regions, time_offset + index / info.fps, index % refresh == 0)
                enc.stdin.write(frame.tobytes())
                index += 1
            enc.stdin.close()
            enc_rc = enc.wait()
            dec_rc = dec.wait()
        except Cancelled:
            _kill()
            output.unlink(missing_ok=True)
            raise
        except BrokenPipeError as e:
            _kill()
            enc_err.seek(0)
            if b"No space left" in enc_err.read():
                raise DiskFull() from e
            raise FFmpegError("ghi video thay text thất bại") from e
        finally:
            _kill()
        if enc_rc != 0:
            enc_err.seek(0)
            if b"No space left" in enc_err.read():
                raise DiskFull()
            raise FFmpegError("ghi video thay text thất bại")
        if dec_rc != 0:
            dec_err.seek(0)
            raise FFmpegError("không đọc được frame để thay text")
    if os.path.getsize(output) == 0:
        raise FFmpegError("ghi video thay text thất bại")
    return TextReplaceResult(output=output, note="; ".join(dict.fromkeys(notes)))
