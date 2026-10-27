"""Đóng gói bản phát hành: python scripts/make_release.py → dist/VideoRemixer-<version>.zip.

Zip chỉ chứa phần app (không có .venv, bin/ ffmpeg, output). Bản này dùng để đính kèm vào GitHub Release,
app đang chạy sẽ tải đúng file này khi người dùng bấm "Cập nhật ngay".
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ["videobulkremixer", "web", "pyproject.toml", "RUN-Mac.command", "RUN-Windows.bat",
         "README.md", "LICENSE", "docs/HUONG-DAN-CAI-DAT.md"]


def version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("Không đọc được version trong pyproject.toml")
    return m.group(1)


def main() -> None:
    ver = version()
    out = ROOT / "dist" / f"VideoRemixer-{ver}.zip"
    out.parent.mkdir(exist_ok=True)
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in ITEMS:
            src = ROOT / item
            files = [src] if src.is_file() else [p for p in src.rglob("*") if p.is_file()]
            for f in files:
                if "__pycache__" in f.parts:
                    continue
                zf.write(f, f.relative_to(ROOT).as_posix())
                count += 1
    print(f"Đã tạo {out} ({count} file)")


if __name__ == "__main__":
    main()
