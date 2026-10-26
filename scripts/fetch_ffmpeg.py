"""Tải ffmpeg + ffprobe vào bin/ để đóng gói kèm app (chạy 1 lần trước khi build).

Dùng: python scripts/fetch_ffmpeg.py
- Windows: bản static từ gyan.dev (ffmpeg-release-essentials)
- macOS:   bản static từ evermeet.cx (ffmpeg + ffprobe)
- Linux:   dùng ffmpeg đã cài sẵn (sudo apt install ffmpeg), script không tải gì.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin"
WIN_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
MAC_URLS = {
    "ffmpeg": "https://evermeet.cx/ffmpeg/getrelease/zip",
    "ffprobe": "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip",
}


def _download(url: str, dest: Path) -> None:
    print(f"→ Tải {url}")
    with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:  # noqa: S310 — URL cố định
        shutil.copyfileobj(r, f)


def _extract(zip_path: Path, names: set[str], out_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            base = Path(member).name
            if base in names:
                with z.open(member) as src, open(out_dir / base, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                names.discard(base)
    if names:
        raise RuntimeError(f"không tìm thấy trong gói tải về: {', '.join(sorted(names))}")


def main() -> int:
    BIN.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        if sys.platform == "win32":
            z = tmp_p / "ffmpeg.zip"
            _download(WIN_URL, z)
            _extract(z, {"ffmpeg.exe", "ffprobe.exe"}, BIN)
        elif sys.platform == "darwin":
            for name, url in MAC_URLS.items():
                z = tmp_p / f"{name}.zip"
                _download(url, z)
                _extract(z, {name}, BIN)
                (BIN / name).chmod(0o755)
        else:
            if not shutil.which("ffmpeg"):
                print("Chưa có ffmpeg. Cài bằng: sudo apt install ffmpeg")
                return 1
            print("Linux: dùng ffmpeg của hệ thống, không cần tải.")
            return 0
    print(f"✓ Đã đặt ffmpeg vào {BIN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
