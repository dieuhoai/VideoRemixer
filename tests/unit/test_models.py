"""Test models — T1."""
from pathlib import Path

import pytest

from videobulkremixer.models import (
    AudioConfig,
    ItemResult,
    JobConfig,
    JobResult,
    NamingConfig,
    SegmentConfig,
    SegmentType,
    TextRegion,
    TextReplacement,
)


class TestSegmentConfig:
    def test_valid_segment(self, tmp_path):
        seg = SegmentConfig(SegmentType.INTRO, 0, 5, tmp_path)
        assert seg.start_sec == 0
        assert seg.end_sec == 5

    def test_negative_start_raises(self, tmp_path):
        with pytest.raises(ValueError, match="start_sec phải >= 0"):
            SegmentConfig(SegmentType.INTRO, -1, 5, tmp_path)

    def test_end_before_start_raises(self, tmp_path):
        with pytest.raises(ValueError, match="end_sec.*phải > start_sec"):
            SegmentConfig(SegmentType.INTRO, 5, 3, tmp_path)


class TestJobConfigOverlap:
    """AC3: đoạn chồng lấn → báo lỗi."""

    def test_no_overlap_ok(self, tmp_path):
        cfg = JobConfig(
            input_dir=tmp_path, output_dir=tmp_path,
            segments=[
                SegmentConfig(SegmentType.INTRO, 0, 5, tmp_path),
                SegmentConfig(SegmentType.OUTRO, 25, 30, tmp_path),
            ],
        )
        cfg.validate_no_overlap()  # không raise

    def test_overlap_raises(self, tmp_path):
        cfg = JobConfig(
            input_dir=tmp_path, output_dir=tmp_path,
            segments=[
                SegmentConfig(SegmentType.INTRO, 0, 10, tmp_path),
                SegmentConfig(SegmentType.CUSTOM, 5, 15, tmp_path),
            ],
        )
        with pytest.raises(ValueError, match="chồng lấn"):
            cfg.validate_no_overlap()

    def test_three_segments_no_overlap(self, tmp_path):
        cfg = JobConfig(
            input_dir=tmp_path, output_dir=tmp_path,
            segments=[
                SegmentConfig(SegmentType.INTRO, 0, 5, tmp_path),
                SegmentConfig(SegmentType.CUSTOM, 10, 15, tmp_path),
                SegmentConfig(SegmentType.OUTRO, 25, 30, tmp_path),
            ],
        )
        cfg.validate_no_overlap()


class TestNamingConfig:
    """AC14: naming convention đúng format."""

    def test_format_name_full(self):
        nc = NamingConfig(
            appname="MyApp-GP", concept="SummerSale",
            geo="BR", date_str="261026",
        )
        result = nc.format_name(language="pt", ratio="9x16", stt=1)
        assert result == "MyApp-GP_VID_SummerSale_BR_pt_261026_9x16_001.mp4"

    def test_stt_auto_pad(self):
        nc = NamingConfig(appname="App", concept="Test", date_str="261026")
        result = nc.format_name(language="en", ratio="16x9", stt=42)
        assert "_042.mp4" in result

    def test_default_date_is_today(self):
        from datetime import date
        nc = NamingConfig(appname="App", concept="C")
        expected = date.today().strftime("%d%m%y")
        assert nc.date_str == expected


class TestComboCount:
    def test_basic_combo(self, tmp_path):
        cfg = JobConfig(
            input_dir=tmp_path, output_dir=tmp_path,
            audio=AudioConfig(audio_files=[Path("a.mp3"), Path("b.mp3")]),
            text_replacements=[
                TextReplacement(
                    region=TextRegion("Title", 0, 0, 100, 50),
                    texts_by_lang={"vi": "Xin chào", "en": "Hello", "ja": "こんにちは"},
                ),
            ],
        )
        # sources: intro=2, outro=3 → 2*3 = 6 * 2 audio * 3 lang = 36
        count = cfg.compute_combo_count({"intro": 2, "outro": 3})
        assert count == 36

    def test_no_audio_no_text(self, tmp_path):
        cfg = JobConfig(input_dir=tmp_path, output_dir=tmp_path)
        count = cfg.compute_combo_count({"intro": 5})
        assert count == 5


class TestJobResult:
    def test_ok_count(self):
        jr = JobResult(items=[
            ItemResult(ok=True), ItemResult(ok=True), ItemResult(ok=False, error="fail"),
        ])
        assert jr.ok_count == 2
        assert len(jr.failed) == 1
        assert jr.total == 3
