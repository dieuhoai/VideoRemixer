"""Chuỗi đoạn trong video: giữ gốc xen kẽ đoạn thay (F1, AC1–AC3)."""
from pathlib import Path

import pytest

from videobulkremixer.models import SegmentConfig, SegmentType
from videobulkremixer.timeline import build_timeline, joint_labels


def seg(kind, start, end, src="x"):
    return SegmentConfig(kind, start, end, Path(src))


def test_intro_only_keeps_rest_of_video():
    parts = build_timeline([seg(SegmentType.INTRO, 0, 5)], 30)
    assert [(p.kind, p.start, p.end) for p in parts] == [("segment", 0, 5), ("keep", 5, 30)]


def test_three_segments_make_two_keep_parts_between():
    parts = build_timeline([seg(SegmentType.INTRO, 0, 5), seg(SegmentType.CUSTOM, 10, 15),
                            seg(SegmentType.OUTRO, 25, float("inf"))], 30)
    kinds = [(p.kind, p.label) for p in parts]
    assert kinds == [("segment", "Intro"), ("keep", "Gốc"), ("segment", "Tuỳ chọn"),
                     ("keep", "Gốc"), ("segment", "Outro")]
    assert parts[-1].end == 30
    assert joint_labels(parts) == ["Intro → Gốc", "Gốc → Tuỳ chọn", "Tuỳ chọn → Gốc", "Gốc → Outro"]


def test_overlap_is_rejected_by_config_validation():
    from videobulkremixer.models import JobConfig
    cfg = JobConfig(input_dir=Path("."), output_dir=Path("o"),
                    segments=[seg(SegmentType.INTRO, 0, 10), seg(SegmentType.CUSTOM, 5, 15)])
    with pytest.raises(ValueError, match="chồng lấn"):
        cfg.validate_no_overlap()


def test_segment_starting_after_video_end_is_an_error():
    with pytest.raises(ValueError, match="sau khi video kết thúc"):
        build_timeline([seg(SegmentType.OUTRO, 40, float("inf"))], 30)


def test_segment_end_is_clipped_to_video_duration():
    parts = build_timeline([seg(SegmentType.OUTRO, 25, float("inf"))], 27.5)
    assert parts[-1].end == pytest.approx(27.5)
