"""Ghép audio + text theo ngôn ngữ, tổ hợp source, đếm số video đầu ra (F15, F20, AC7, AC10)."""

from videobulkremixer.models import (
    AudioConfig,
    JobConfig,
    SegmentConfig,
    SegmentType,
    TextRegion,
    TextReplacement,
)
from videobulkremixer.orchestrator import build_output_plan, build_source_combos


def _tr(name, langs):
    return TextReplacement(TextRegion(name, 0, 0, 10, 10), {lang: "x" for lang in langs})


def test_no_audio_no_text_gives_single_output_with_original_audio(tmp_path):
    cfg = JobConfig(input_dir=tmp_path, output_dir=tmp_path / "o")
    plan = build_output_plan(cfg)
    assert len(plan) == 1 and plan[0].audio is None and plan[0].lang == ""


def test_each_audio_language_becomes_its_own_output_and_text_follows_its_language(tmp_path):
    en, vi = tmp_path / "voice_EN.mp3", tmp_path / "voice_VI.mp3"
    cfg = JobConfig(input_dir=tmp_path, output_dir=tmp_path / "o",
                    audio=AudioConfig(audio_files=[en, vi]),
                    text_replacements=[_tr("Tiêu đề", ["vi", "en"])])
    plan = {(s.lang, s.audio.name if s.audio else None): s for s in build_output_plan(cfg)}
    assert set(plan) == {("en", "voice_EN.mp3"), ("vi", "voice_VI.mp3")}
    assert len(plan[("vi", "voice_VI.mp3")].texts) == 1


def test_text_language_without_audio_uses_original_audio(tmp_path):
    cfg = JobConfig(input_dir=tmp_path, output_dir=tmp_path / "o",
                    text_replacements=[_tr("CTA", ["ja"])])
    plan = build_output_plan(cfg)
    assert [(s.lang, s.audio) for s in plan] == [("ja", None)]


def test_source_combinations_are_cartesian_product(tmp_path):
    intro, outro = tmp_path / "i", tmp_path / "o"
    intro.mkdir()
    outro.mkdir()
    for n in ("a.mp4", "b.mp4"):
        (intro / n).write_bytes(b"x")
    (outro / "c.mp4").write_bytes(b"x")
    cfg = JobConfig(input_dir=tmp_path, output_dir=tmp_path / "out", segments=[
        SegmentConfig(SegmentType.INTRO, 0, 5, intro),
        SegmentConfig(SegmentType.OUTRO, 25, float("inf"), outro),
    ])
    combos = build_source_combos(cfg)
    assert len(combos) == 2
    assert all(c["outro"].name == "c.mp4" for c in combos)
