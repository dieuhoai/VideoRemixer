"""Kiểm tra cập nhật: so phiên bản, giải nén an toàn, chỉ ghi đè mục được phép."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from videobulkremixer import updater
from videobulkremixer.updater import UpdateError


def test_version_compare():
    assert updater.parse_version("v0.10.0") == (0, 10, 0)
    assert updater.is_newer("0.2.0", "0.1.0")
    assert updater.is_newer("v1.0.0", "0.9.9")
    assert not updater.is_newer("0.1.0", "0.1.0")
    assert not updater.is_newer("0.0.9", "0.1.0")
    assert not updater.is_newer("abc", "0.1.0")


def test_bad_version_raises():
    with pytest.raises(ValueError):
        updater.parse_version("1.x")


def test_download_refuses_foreign_host():
    with pytest.raises(UpdateError):
        updater._check_url("https://evil.example.com/VideoRemixer-0.2.0.zip")
    with pytest.raises(UpdateError):
        updater._check_url("http://github.com/x.zip")
    updater._check_url("https://github.com/dieuhoai/VideoRemixer/releases/download/v0.2.0/a.zip")


def _zip(path: Path, entries: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return path


def test_safe_extract_rejects_path_traversal(tmp_path):
    z = _zip(tmp_path / "bad.zip", {"../evil.txt": "x"})
    with pytest.raises(UpdateError):
        updater.safe_extract(z, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_safe_extract_accepts_normal_files(tmp_path):
    z = _zip(tmp_path / "ok.zip", {"web/a.txt": "1", "videobulkremixer/b.py": "2"})
    updater.safe_extract(z, tmp_path / "out")
    assert (tmp_path / "out" / "web" / "a.txt").read_text() == "1"


def test_apply_update_only_touches_allowed_items(tmp_path):
    staged = tmp_path / "staged"
    (staged / "videobulkremixer").mkdir(parents=True)
    (staged / "videobulkremixer" / "new.py").write_text("new")
    (staged / "web").mkdir()
    (staged / "web" / "index.html").write_text("new")
    (staged / "pyproject.toml").write_text("v2")
    app = tmp_path / "app"
    (app / "videobulkremixer").mkdir(parents=True)
    (app / "videobulkremixer" / "old.py").write_text("old")
    (app / "bin").mkdir()
    (app / "bin" / "ffmpeg").write_text("keep")
    (app / ".venv").mkdir()
    (app / "output").mkdir()
    (app / "output" / "result.mp4").write_text("keep")

    updated = updater.apply_update(staged, app)

    assert set(updated) == {"videobulkremixer", "web", "pyproject.toml"}
    assert not (app / "videobulkremixer" / "old.py").exists()  # thư mục app cũ được thay hoàn toàn
    assert (app / "videobulkremixer" / "new.py").read_text() == "new"
    assert (app / "bin" / "ffmpeg").read_text() == "keep"
    assert (app / ".venv").is_dir()
    assert (app / "output" / "result.mp4").read_text() == "keep"


def test_apply_update_rejects_incomplete_bundle(tmp_path):
    staged = tmp_path / "staged"
    staged.mkdir()
    with pytest.raises(UpdateError):
        updater.apply_update(staged, tmp_path / "app")


def test_check_reports_update_when_newer(monkeypatch):
    from web.api import update as api

    monkeypatch.setattr(updater, "fetch_latest", lambda timeout=8.0: {
        "version": "9.9.9", "notes_url": "https://github.com/x", "zip_url": "https://github.com/x.zip"})
    api._CACHE.update(at=0.0, info=None)
    res = api.check(force=True)
    assert res["has_update"] is True and res["latest"] == "9.9.9" and res["online"] is True


def test_check_offline_is_silent(monkeypatch):
    from web.api import update as api

    monkeypatch.setattr(updater, "fetch_latest", lambda timeout=8.0: None)
    api._CACHE.update(at=0.0, info=None)
    res = api.check(force=True)
    assert res["has_update"] is False and res["online"] is False
