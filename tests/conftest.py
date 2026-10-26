import os
import shutil
import subprocess

import pytest


def pytest_collection_modifyitems(config, items):
    skip_real = pytest.mark.skip(reason="đặt VIDEOBULKREMIXER_REAL_DATA để chạy")
    for it in items:
        if "real" in it.keywords and not os.environ.get("VIDEOBULKREMIXER_REAL_DATA"):
            it.add_marker(skip_real)


@pytest.fixture(autouse=True)
def isolated_user_dir(tmp_path, monkeypatch):
    """Không bao giờ để test ghi vào thư mục cấu hình thật của người dùng."""
    from videobulkremixer import defaults as D
    monkeypatch.setattr(D, "USER_DIR", tmp_path / "_user")
    monkeypatch.setattr(D, "USER_PRESET_DIR", tmp_path / "_user" / "presets")
    monkeypatch.setattr(D, "SETTINGS_FILE", tmp_path / "_user" / "settings.json")


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True, timeout=120)


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    """Bộ video/audio mẫu nhỏ (sinh bằng ffmpeg) dùng cho test tích hợp."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("cần ffmpeg/ffprobe trên PATH")
    root = tmp_path_factory.mktemp("media")
    (root / "orig").mkdir()
    (root / "intro").mkdir()
    (root / "outro").mkdir()
    (root / "audio").mkdir()
    # 12s, 16:9, có tiếng sine
    _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=12", "-f", "lavfi", "-i",
        "sine=frequency=440:duration=12", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(root / "orig" / "a_land.mp4"))
    # 12s, 9:16
    _ff("-f", "lavfi", "-i", "testsrc2=size=180x320:rate=25:duration=12", "-f", "lavfi", "-i",
        "sine=frequency=330:duration=12", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(root / "orig" / "b_port.mp4"))
    # source intro dài 6s và ngắn 2s
    _ff("-f", "lavfi", "-i", "color=c=blue:size=320x180:rate=25:duration=6", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", str(root / "intro" / "long6.mp4"))
    _ff("-f", "lavfi", "-i", "color=c=green:size=320x180:rate=25:duration=2", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", str(root / "intro" / "short2.mp4"))
    _ff("-f", "lavfi", "-i", "color=c=red:size=320x180:rate=25:duration=3", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", str(root / "outro" / "outro3.mp4"))
    _ff("-f", "lavfi", "-i", "sine=frequency=600:duration=8", str(root / "audio" / "voice_EN.mp3"))
    _ff("-f", "lavfi", "-i", "sine=frequency=700:duration=20", str(root / "audio" / "voice_VI.mp3"))
    # file hỏng: không phải video
    (root / "orig" / "broken.mp4").write_bytes(b"not a video at all" * 50)
    return root
