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
    x0: int
    y0: int
    x1: int
    y1: int
    overlay: np.ndarray  # RGBA, kích thước (y1-y0, x1-x0)
    mask: np.ndarray  # 255 = phần text cũ cần xoá; viền đệm (0) là nguồn để nội suy
    clean: np.ndarray | None = None  # nền đã inpaint, làm mới mỗi ~1/3 giây


def _prepare(replacements: list[TextReplacement], language: str, w: int, h: int) -> tuple[list[_Region], list[str]]:
    regions: list[_Region] = []
    notes: list[str] = []
    margin = 6
    for r in replacements:
        reg = r.region
        x0, y0 = max(0, reg.x - margin), max(0, reg.y - margin)
        x1, y1 = min(w, reg.x + reg.width + margin), min(h, reg.y + reg.height + margin)
        if x1 - x0 < 4 or y1 - y0 < 4:
            raise ValueError(f"vùng '{reg.name}' nằm ngoài khung hình hoặc quá nhỏ")
        inner_w, inner_h = reg.width, reg.height
        overlay, note = render_overlay(r.texts_by_lang[language], inner_w, inner_h, r.style)
        full = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
        ox, oy = reg.x - x0, reg.y - y0
        full[oy:oy + inner_h, ox:ox + inner_w] = overlay
        mask = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
        mask[max(oy, 0):max(oy, 0) + inner_h, max(ox, 0):max(ox, 0) + inner_w] = 255
        regions.append(_Region(x0, y0, x1, y1, full, mask))
        if note:
            notes.append(f"{reg.name}: {note}")
    return regions, notes


def replace_text_on_video(
    video: Path,
    replacements: list[TextReplacement],
    language: str,
    output: Path,
    cancel: CancelCheck | None = None,
) -> TextReplaceResult:
    """Xoá text cũ bằng inpaint rồi vẽ text mới cho `language` lên toàn bộ video (chỉ hình)."""
    active = [r for r in replacements if (r.texts_by_lang.get(language) or "").strip()]
    if not active:
        return TextReplaceResult(output=None)

    info = probe(str(video))
    w, h = info.width - info.width % 2, info.height - info.height % 2  # yuv420p cần số chẵn
    regions, notes = _prepare(active, language, w, h)
    frame_bytes = w * h * 3
    fps = f"{info.fps:.3f}"
    refresh = max(1, int(info.fps // 3))  # inpaint lại ~3 lần/giây: đủ cho nền tĩnh và nền chuyển chậm

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
                for reg in regions:
                    if reg.clean is None or index % refresh == 0:
                        reg.clean = cv2.inpaint(frame[reg.y0:reg.y1, reg.x0:reg.x1].copy(), reg.mask, 3,
                                                cv2.INPAINT_TELEA)
                    bg = frame[reg.y0:reg.y1, reg.x0:reg.x1]
                    m = reg.mask == 255
                    bg[m] = reg.clean[m]
                    ov = reg.overlay
                    alpha = ov[..., 3:4].astype(np.float32) / 255.0
                    rgb_bgr = ov[..., [2, 1, 0]].astype(np.float32)
                    sub = frame[reg.y0:reg.y1, reg.x0:reg.x1].astype(np.float32)
                    frame[reg.y0:reg.y1, reg.x0:reg.x1] = (sub * (1 - alpha) + rgb_bgr * alpha).astype(np.uint8)
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
    return TextReplaceResult(output=output, note="; ".join(notes))
