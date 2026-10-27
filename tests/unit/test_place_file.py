"""Lưu file thành phẩm: không sao chép dữ liệu khi cùng ổ, và không để lại file tạm khi lỗi."""
import pytest

from videobulkremixer import orchestrator
from videobulkremixer.orchestrator import place_file


def test_place_file_keeps_content_and_source(tmp_path):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"video-data")
    dst = tmp_path / "out" / "b.mp4"
    dst.parent.mkdir()
    place_file(src, dst)
    assert dst.read_bytes() == b"video-data"
    assert src.read_bytes() == b"video-data"
    assert not (dst.parent / ".b.mp4.part").exists()


def test_place_file_uses_hard_link_on_same_disk(tmp_path):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    dst = tmp_path / "b.mp4"
    place_file(src, dst)
    assert dst.stat().st_ino == src.stat().st_ino  # không sao chép dữ liệu


def test_place_file_falls_back_to_copy_when_link_fails(tmp_path, monkeypatch):
    def no_link(*_args, **_kwargs):
        raise OSError("khác ổ đĩa")

    monkeypatch.setattr(orchestrator.os, "link", no_link)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"video-data")
    dst = tmp_path / "b.mp4"
    place_file(src, dst)
    assert dst.read_bytes() == b"video-data"
    assert dst.stat().st_ino != src.stat().st_ino


def test_place_file_cleans_up_on_error(tmp_path):
    dst = tmp_path / "b.mp4"
    with pytest.raises(OSError):
        place_file(tmp_path / "khong_ton_tai.mp4", dst)
    assert not dst.exists()
    assert not (tmp_path / ".b.mp4.part").exists()
