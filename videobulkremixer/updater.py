"""Kiểm tra và cài bản mới từ GitHub Releases.

Chỉ tải từ đúng repo đã cấu hình và chỉ qua HTTPS. File zip được kiểm tra đường dẫn
trước khi giải nén, và chỉ các thư mục/file của app mới được ghi đè (không đụng .venv, bin/, output).
"""
from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from videobulkremixer import __version__

GITHUB_REPO = "dieuhoai/VideoRemixer"
API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ALLOWED_DOWNLOAD_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
# Chỉ các mục này được cập nhật; mọi thứ khác của người dùng giữ nguyên.
UPDATABLE = ("videobulkremixer", "web", "pyproject.toml", "RUN-Mac.command", "RUN-Windows.bat", "README.md")


class UpdateError(RuntimeError):
    """Lỗi cập nhật — message tiếng Việt, hiển thị thẳng cho người dùng."""


def parse_version(text: str) -> tuple[int, ...]:
    """'v1.2.3' → (1, 2, 3). Không đọc được → ValueError."""
    t = text.strip().lstrip("vV")
    parts = t.split(".")
    if not parts or not all(p.isdigit() for p in parts):
        raise ValueError(f"Phiên bản không hợp lệ: {text!r}")
    return tuple(int(p) for p in parts)


def is_newer(latest: str, current: str = __version__) -> bool:
    try:
        return parse_version(latest) > parse_version(current)
    except ValueError:
        return False


def _check_url(url: str) -> None:
    from urllib.parse import urlparse
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_DOWNLOAD_HOSTS:
        raise UpdateError("Đường dẫn tải bản mới không đáng tin cậy, đã dừng.")


def fetch_latest(timeout: float = 8.0) -> dict | None:
    """Thông tin bản phát hành mới nhất: {version, notes_url, zip_url}. Không có mạng → None."""
    req = urllib.request.Request(API_LATEST, headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": "VideoRemixer-updater"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URL cố định, HTTPS
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    tag = str(data.get("tag_name", ""))
    zip_url = ""
    for a in data.get("assets", []):
        name = str(a.get("name", ""))
        if name.startswith("VideoRemixer-") and name.endswith(".zip"):
            zip_url = str(a.get("browser_download_url", ""))
            break
    try:
        parse_version(tag)
    except ValueError:
        return None
    return {"version": tag.lstrip("vV"), "notes_url": str(data.get("html_url", "")), "zip_url": zip_url}


def download(url: str, dest: Path, timeout: float = 120.0) -> None:
    _check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "VideoRemixer-updater"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:  # noqa: S310
            shutil.copyfileobj(resp, f)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UpdateError("Không tải được bản mới. Kiểm tra mạng rồi thử lại.") from e


def safe_extract(zip_path: Path, dest: Path) -> None:
    """Giải nén, từ chối mọi đường dẫn tuyệt đối hoặc thoát ra ngoài dest."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                target = (dest / info.filename).resolve()
                if target != root and root not in target.parents:
                    raise UpdateError("File cập nhật có đường dẫn không an toàn, đã dừng.")
            zf.extractall(dest)
    except zipfile.BadZipFile as e:
        raise UpdateError("File tải về bị hỏng, thử lại sau.") from e


def apply_update(staged: Path, app_root: Path) -> list[str]:
    """Chép các mục được phép từ thư mục đã giải nén vào app_root. Trả về danh sách mục đã cập nhật."""
    if not (staged / "videobulkremixer").is_dir() or not (staged / "web").is_dir():
        raise UpdateError("Bản tải về thiếu thư mục chính, đã dừng để tránh làm hỏng app.")
    updated = []
    for name in UPDATABLE:
        src = staged / name
        if not src.exists():
            continue
        dst = app_root / name
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, dst)
        updated.append(name)
    return updated
