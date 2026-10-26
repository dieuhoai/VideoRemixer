"""Model dữ liệu cho Video Bulk Remixer."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path


class SegmentType(str, Enum):
    INTRO = "intro"
    OUTRO = "outro"
    CUSTOM = "custom"


class TransitionType(str, Enum):
    NONE = "none"
    CROSSFADE = "crossfade"
    FADE_BLACK = "fade_black"
    FADE_WHITE = "fade_white"
    SLIDE_LR = "slide_lr"
    SLIDE_RL = "slide_rl"
    WIPE_TB = "wipe_tb"
    WIPE_BT = "wipe_bt"


@dataclass
class SegmentConfig:
    """Một đoạn cần thay trong video gốc."""
    segment_type: SegmentType
    start_sec: float
    end_sec: float
    source_dir: Path  # thư mục chứa source thay thế

    def __post_init__(self) -> None:
        if self.start_sec < 0:
            raise ValueError(f"start_sec phải >= 0, nhận {self.start_sec}")
        if self.end_sec <= self.start_sec:
            raise ValueError(
                f"end_sec ({self.end_sec}) phải > start_sec ({self.start_sec})"
            )


@dataclass
class TransitionConfig:
    """Hiệu ứng chuyển cảnh tại 1 mối nối."""
    transition_type: TransitionType = TransitionType.NONE
    duration_sec: float = 0.5

    def __post_init__(self) -> None:
        if self.duration_sec < 0:
            raise ValueError("duration_sec phải >= 0")


@dataclass
class AudioConfig:
    """Cấu hình audio thay thế."""
    audio_files: list[Path] = field(default_factory=list)
    language_labels: dict[str, str] = field(default_factory=dict)
    # key = tên file audio, value = mã ngôn ngữ (vi, en, ja...)

    @property
    def has_replacement(self) -> bool:
        return len(self.audio_files) > 0


@dataclass
class TextRegion:
    """Một vùng text trên video."""
    name: str  # "Tiêu đề", "CTA"...
    x: int
    y: int
    width: int
    height: int


@dataclass
class TextStyle:
    """Kiểu text mới."""
    font: str = "Arial"
    size: int = 32
    color: str = "#FFFFFF"
    bold: bool = False
    italic: bool = False
    align: str = "center"  # left, center, right
    stroke_color: str | None = None
    stroke_width: int = 0
    shadow: bool = False


@dataclass
class TextReplacement:
    """Thay text trên video cho 1 ngôn ngữ."""
    region: TextRegion
    texts_by_lang: dict[str, str] = field(default_factory=dict)
    # key = mã ngôn ngữ, value = text mới
    style: TextStyle = field(default_factory=TextStyle)


@dataclass
class NamingConfig:
    """Cấu hình naming convention."""
    appname: str = ""
    vid_prefix: str = "VID"
    concept: str = ""
    geo: str = "WW"
    date_str: str = ""  # ddmmyy, mặc định = ngày chạy

    def __post_init__(self) -> None:
        if not self.date_str:
            self.date_str = date.today().strftime("%d%m%y")

    def format_name(
        self,
        language: str,
        ratio: str,
        stt: int,
    ) -> str:
        parts = [
            self.appname,
            self.vid_prefix,
            self.concept,
            self.geo,
            language,
            self.date_str,
            ratio,
            f"{stt:03d}",
        ]
        return "_".join(p for p in parts if p) + ".mp4"


@dataclass
class JobConfig:
    """Cấu hình toàn bộ job."""
    input_dir: Path
    output_dir: Path
    segments: list[SegmentConfig] = field(default_factory=list)
    transitions: dict[str, TransitionConfig] = field(default_factory=dict)
    # key = "j0", "j1"... (thứ tự mối nối trong timeline của từng video)
    default_transition: TransitionConfig = field(default_factory=TransitionConfig)
    # áp cho mọi mối nối không có cấu hình riêng
    audio: AudioConfig = field(default_factory=AudioConfig)
    text_replacements: list[TextReplacement] = field(default_factory=list)
    naming: NamingConfig = field(default_factory=NamingConfig)

    def transition_for_joint(self, index: int) -> TransitionConfig:
        return self.transitions.get(f"j{index}", self.default_transition)

    def validate_no_overlap(self) -> None:
        """Kiểm tra các segment không chồng lấn."""
        sorted_segs = sorted(self.segments, key=lambda s: s.start_sec)
        for i in range(len(sorted_segs) - 1):
            if sorted_segs[i].end_sec > sorted_segs[i + 1].start_sec:
                raise ValueError(
                    f"Đoạn {sorted_segs[i].segment_type.value} "
                    f"({sorted_segs[i].start_sec}–{sorted_segs[i].end_sec}s) "
                    f"chồng lấn với đoạn {sorted_segs[i+1].segment_type.value} "
                    f"({sorted_segs[i+1].start_sec}–{sorted_segs[i+1].end_sec}s)"
                )

    def compute_combo_count(
        self, source_counts: dict[str, int] | None = None
    ) -> int:
        """Tính tổng số video đầu ra."""
        seg_multiplier = 1
        if source_counts:
            for count in source_counts.values():
                seg_multiplier *= max(count, 1)
        audio_count = max(len(self.audio.audio_files), 1)
        lang_count = 1
        if self.text_replacements:
            all_langs: set[str] = set()
            for tr in self.text_replacements:
                all_langs.update(tr.texts_by_lang.keys())
            lang_count = max(len(all_langs), 1)
        return seg_multiplier * audio_count * lang_count


@dataclass
class ItemResult:
    """Kết quả xử lý 1 video output."""
    output_path: Path | None = None
    source_video: str = ""
    source_intro: str = ""
    source_mid: str = ""
    source_outro: str = ""
    audio_file: str = ""
    language: str = ""
    duration_in: float = 0.0
    duration_out: float = 0.0
    size_mb: float = 0.0
    transition_used: str = ""
    text_replaced: bool = False
    ok: bool = True
    error: str = ""
    note: str = ""


@dataclass
class JobResult:
    """Kết quả toàn bộ job."""
    items: list[ItemResult] = field(default_factory=list)
    fatal: str = ""  # lý do dừng cả batch (ví dụ hết dung lượng ổ đĩa)
    cancelled: bool = False

    @property
    def ok_count(self) -> int:
        return sum(1 for i in self.items if i.ok)

    @property
    def failed(self) -> list[ItemResult]:
        return [i for i in self.items if not i.ok]

    @property
    def total(self) -> int:
        return len(self.items)
