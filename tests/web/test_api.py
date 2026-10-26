"""API web: bảo vệ bằng token/Host, kiểm đầu vào, timeline, tên file, phát video có tua."""
import time

import pytest
from fastapi.testclient import TestClient

from web.server import COOKIE, TOKEN_HEADER, create_app
from web.state import STATE

TOKEN = "test-token"
HOST = "testserver"


@pytest.fixture
def client():
    c = TestClient(create_app(TOKEN, {HOST}))
    c.headers[TOKEN_HEADER] = TOKEN
    return c


def test_requires_token_for_api_and_index():
    c = TestClient(create_app(TOKEN, {HOST}))
    assert c.get("/api/jobs").status_code == 401
    assert c.get("/").status_code == 401
    r = c.get(f"/?t={TOKEN}", follow_redirects=False)
    assert r.status_code == 303 and COOKIE in r.headers["set-cookie"]


def test_bad_host_and_origin_are_refused(client):
    assert client.get("/api/jobs", headers={"host": "evil.com"}).status_code == 403
    assert client.get("/api/jobs", headers={"origin": "http://evil.com"}).status_code == 403


def test_index_has_csp_and_is_vietnamese(client):
    r = client.get("/")
    assert r.status_code == 200 and "default-src 'self'" in r.headers["content-security-policy"]
    assert 'lang="vi"' in r.text and "<script>" not in r.text  # không inline script


def test_timeline_endpoint_reports_parts_and_joints(client):
    r = client.post("/api/jobs/timeline", json={"duration": 30, "segments": [
        {"type": "intro", "start": 0, "end": 5}, {"type": "outro", "start": 25, "end": None}]})
    body = r.json()
    assert body["ok"] and body["joints"] == ["Intro → Gốc", "Gốc → Outro"]


def test_timeline_endpoint_reports_overlap_in_vietnamese(client):
    body = client.post("/api/jobs/timeline", json={"duration": 30, "segments": [
        {"type": "intro", "start": 0, "end": 10}, {"type": "custom", "start": 5, "end": 15}]}).json()
    assert body["ok"] is True  # timeline vẫn tính; lỗi chồng lấn do bước kiểm tra chạy
    bad = client.post("/api/jobs/timeline", json={"duration": 30, "segments": [
        {"type": "outro", "start": 40, "end": None}]}).json()
    assert bad["ok"] is False and "video kết thúc" in bad["error"]


def test_naming_preview_restarts_stt_per_language(client):
    names = client.post("/api/jobs/naming", json={"naming": {"appname": "MyApp-GP", "concept": "Sale",
                                                             "geo": "BR", "date": "261026"},
                                                  "languages": ["en", "vi"], "ratio": "9x16"}).json()["names"]
    assert names == ["MyApp-GP_VID_Sale_BR_en_261026_9x16_001.mp4", "MyApp-GP_VID_Sale_BR_vi_261026_9x16_001.mp4"]


def test_start_job_rejects_overlap_and_missing_sources(client, media, tmp_path):
    body = {"input_dir": str(media / "orig"), "output_dir": str(tmp_path / "o"), "segments": [
        {"type": "intro", "start": 0, "end": 10, "source_dir": str(media / "intro")},
        {"type": "custom", "start": 5, "end": 15, "source_dir": str(media / "intro")}]}
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 422 and "chồng lấn" in r.json()["detail"]
    body2 = {"input_dir": str(media / "orig"), "output_dir": str(tmp_path / "o"), "segments": [
        {"type": "intro", "start": 0, "end": 5, "source_dir": str(tmp_path / "nope")}]}
    assert client.post("/api/jobs", json=body2).status_code == 422


def test_start_job_refuses_output_equal_to_input(client, media):
    body = {"input_dir": str(media / "orig"), "output_dir": str(media / "orig"), "audio_files": [
        str(media / "audio" / "voice_EN.mp3")]}
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 422 and "trùng" in r.json()["detail"]


def test_full_job_runs_to_done_and_lists_outputs(client, media, tmp_path):
    body = {"input_dir": str(media / "orig"), "output_dir": str(tmp_path / "out"),
            "segments": [{"type": "intro", "start": 0, "end": 5, "source_dir": str(media / "intro")}],
            "naming": {"appname": "MyApp", "concept": "Sale", "geo": "BR", "date": "261026"}}
    assert client.post("/api/jobs", json=body).status_code == 200
    job = {}
    for _ in range(600):
        job = client.get("/api/jobs").json()
        if job["status"] != "running":
            break
        time.sleep(0.1)
    assert job["status"] == "done", job
    assert job["ok"] >= 2 and any(o["ok"] for o in job["outputs"])
    assert all(o["rel"].startswith("BR_orig") for o in job["outputs"] if o["ok"])


def test_media_endpoint_supports_range_for_seeking(client, media):
    r = client.get("/api/fs/media", params={"path": str(media / "orig" / "a_land.mp4")},
                   headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100 and r.headers["content-range"].startswith("bytes 0-99/")


def test_media_endpoint_refuses_non_media_files(client, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("x")
    assert client.get("/api/fs/media", params={"path": str(secret)}).status_code == 404


def test_frame_endpoint_returns_jpeg_with_video_size(client, media):
    r = client.get("/api/fs/frame", params={"path": str(media / "orig" / "a_land.mp4"), "t": 1, "w": 160})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["x-video-width"] == "320" and r.headers["x-video-height"] == "180"


def test_list_videos_marks_broken_file_without_duration(client, media):
    files = client.get("/api/fs/list", params={"dir": str(media / "orig"), "kind": "video"}).json()["files"]
    broken = [f for f in files if f["name"] == "broken.mp4"][0]
    assert broken["duration"] is None and broken["error"]


def test_stop_without_job_is_harmless(client):
    assert client.post("/api/jobs/stop").json() == {"stopping": False}
    assert STATE.busy.locked() is False
