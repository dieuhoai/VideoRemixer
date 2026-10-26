"""Tính chuỗi đoạn trong 1 video: đoạn giữ nguyên gốc xen kẽ đoạn thay thế."""
from __future__ import annotations

from dataclasses import dataclass

from videobulkremixer.models import SegmentConfig, SegmentType

SEG_LABELS = {SegmentType.INTRO: "Intro", SegmentType.CUSTOM: "Tuỳ chọn", SegmentType.OUTRO: "Outro"}


@dataclass(frozen=True)
class Part:
    kind: str  # "keep" (giữ gốc) hoặc "segment" (đoạn cần thay)
    start: float
    end: float
    segment_type: SegmentType | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def label(self) -> str:
        if self.kind == "keep":
            return "Gốc"
        return SEG_LABELS[self.segment_type]


def build_timeline(segments: list[SegmentConfig], duration: float) -> list[Part]:
    """Chia [0, duration] thành các phần; đoạn thay thế được cắt theo độ dài video thật."""
    if duration <= 0:
        raise ValueError("video không có thời lượng")
    clipped = []
    for s in sorted(segments, key=lambda s: s.start_sec):
        start, end = s.start_sec, min(s.end_sec, duration)
        if start >= duration - 0.05:
            raise ValueError(
                f"đoạn {SEG_LABELS[s.segment_type]} bắt đầu sau khi video kết thúc ({duration:.1f}s)"
            )
        clipped.append((start, end, s.segment_type))
    parts: list[Part] = []
    cursor = 0.0
    for start, end, seg in clipped:
        if start > cursor + 0.05:
            parts.append(Part("keep", cursor, start))
        parts.append(Part("segment", start, end, seg))
        cursor = end
    if cursor < duration - 0.05:
        parts.append(Part("keep", cursor, duration))
    return parts


def joint_labels(parts: list[Part]) -> list[str]:
    """Tên từng mối nối, ví dụ 'Intro → Gốc'."""
    return [f"{a.label} → {b.label}" for a, b in zip(parts, parts[1:], strict=False)]
