"""Kiểm logic ghép: ngôn ngữ từ tên file, kế hoạch đầu ra, đổi mốc text, đọc cấu hình từ giao diện."""
from __future__ import annotations

from pathlib import Path

import pytest

from videobulkremixer.audio_mixer import guess_language_from_filename
from videobulkremixer.models import (
    AudioConfig,
    JobConfig,
    TextRegion,
    TextReplacement,
    TransitionConfig,
    TransitionType,
)
from videobulkremixer.orchestrator import Pipeline, build_output_plan, map_texts_to_output
from videobulkremixer.timeline import Part
from web.api.jobs import parse_config


def _text(start: float = 0.0, end: float | None = None, **texts: str) -> TextReplacement:
    region = TextRegion(name="Tiêu đề", x=10, y=10, width=100, height=40)
    return TextReplacement(region=region, texts_by_lang=dict(texts), start_sec=start, end_sec=end)


def test_guess_language_uses_last_segment_only() -> None:
    assert guess_language_from_filename("Voice01_EN.mp3") == "en"
    assert guess_language_from_filename("giong-nu_vi.wav") == "vi"
    assert guess_language_from_filename("en_music.mp3") == ""
    assert guess_language_from_filename("nhac_nen.mp3") == ""


def test_plan_combines_voice_and_music_per_language() -> None:
    config = JobConfig(
        input_dir=Path("."), output_dir=Path("out"),
        audio=AudioConfig(music_files=[Path("a.mp3"), Path("b.mp3")],
                          voice_files=[Path("v1_en.mp3"), Path("v2_en.mp3"), Path("v_vi.mp3")]),
        text_replacements=[_text(vi="Xin chào", ru="Привет")],
    )
    plan = build_output_plan(config)
    keys = sorted((o.folder_lang, o.voice.name if o.voice else None, o.music.name if o.music else None)
                  for o in plan)
    # en: 2 voice × 2 nhạc; vi: 1 voice × 2 nhạc; ru: không có voice → 2 nhạc
    assert len(plan) == 4 + 2 + 2
    assert ("en", "v1_en.mp3", "a.mp3") in keys
    assert ("ru", None, "b.mp3") in keys
    assert sum(1 for o in plan if o.folder_lang == "vi") == 2


def test_plan_without_language_is_music_only() -> None:
    config = JobConfig(input_dir=Path("."), output_dir=Path("out"),
                       audio=AudioConfig(music_files=[Path("a.mp3")], keep_original=True))
    plan = build_output_plan(config)
    assert len(plan) == 1
    assert plan[0].folder_lang == "orig" and plan[0].keep_original


def test_voice_without_language_is_refused(tmp_path: Path) -> None:
    video = tmp_path / "in"
    video.mkdir()
    (video / "a.mp4").write_bytes(b"x")
    config = JobConfig(input_dir=video, output_dir=tmp_path / "out",
                       audio=AudioConfig(voice_files=[Path("giong_nu.mp3")]))
    with pytest.raises(ValueError, match="chưa có ngôn ngữ"):
        Pipeline(config).validate()


def test_text_times_map_onto_keep_parts_only() -> None:
    # video gốc 0–10s: giữ 0–4, thay 4–6, giữ 6–10; nối bằng crossfade 1s
    parts = [Part("keep", 0, 4), Part("segment", 4, 6), Part("keep", 6, 10)]
    durs = [4.0, 2.0, 4.0]
    joints = [TransitionConfig(TransitionType.CROSSFADE, 1.0), TransitionConfig(TransitionType.NONE, 0.5)]
    texts = [_text(start=2, end=8, en="Hi")]
    out, skipped = map_texts_to_output(parts, durs, joints, texts, 10.0)
    assert len(out) == 2
    assert out[0].start_sec == pytest.approx(2.0) and out[0].end_sec == pytest.approx(4.0)
    # đoạn giữ thứ 2 bắt đầu sau 4 + 2 − 1 (crossfade) = 5s
    assert out[1].start_sec == pytest.approx(5.0) and out[1].end_sec == pytest.approx(7.0)
    # text 2–8s có một phần (4–6s) nằm trong đoạn thay thế → báo để người dùng biết
    assert skipped is True


def test_text_inside_replaced_segment_is_flagged() -> None:
    parts = [Part("keep", 0, 4), Part("segment", 4, 6)]
    texts = [_text(start=4.5, end=5.5, en="X")]
    out, skipped = map_texts_to_output(parts, [4.0, 2.0], [TransitionConfig()], texts, 6.0)
    assert out == []
    assert skipped is True


def test_parse_config_reads_points_times_and_volumes() -> None:
    body = {
        "input_dir": "in", "output_dir": "out",
        "music_files": ["m.mp3"], "voice_files": ["v_en.mp3"], "audio_labels": {"v_en.mp3": "en"},
        "keep_original": True, "volumes": {"music": 50, "voice": 150, "original": 0}, "duck_music": True,
        "texts": [{"name": "CTA", "texts": {"en": "Buy"}, "start": 1, "end": "",
                   "region": {"x": 1, "y": 2, "width": 3, "height": 4,
                              "points": [[1, 2], [4, 2], [4, 6], [1, 6]]}}],
    }
    cfg = parse_config(body)
    assert cfg.audio.music_volume == pytest.approx(0.5)
    assert cfg.audio.voice_volume == pytest.approx(1.5)
    assert cfg.audio.original_volume == 0
    assert cfg.audio.duck_music and cfg.audio.keep_original
    assert cfg.audio.language_labels == {"v_en.mp3": "en"}
    tr = cfg.text_replacements[0]
    assert tr.start_sec == 1 and tr.end_sec is None
    assert tr.region.points == ((1.0, 2.0), (4.0, 2.0), (4.0, 6.0), (1.0, 6.0))
