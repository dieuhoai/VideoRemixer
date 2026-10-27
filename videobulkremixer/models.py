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
    DISSOLVE = "dissolve"
    FADE_BLACK = "fade_black"
    FADE_WHITE = "fade_white"
    SLIDE_LR = "slide_lr"  # cảnh mới trượt từ trái sang phải
    SLIDE_RL = "slide_rl"  # cảnh mới trượt từ phải sang trái
    SLIDE_UP = "slide_up"  # cảnh mới trượt từ dưới lên
    SLIDE_DOWN = "slide_down"  # cảnh mới trượt từ trên xuống
    WIPE_LR = "wipe_lr"  # quét từ trái sang phải
    WIPE_RL = "wipe_rl"  # quét từ phải sang trái
    WIPE_TB = "wipe_tb"  # quét từ trên xuống
    WIPE_BT = "wipe_bt"  # quét từ dưới lên
    CIRCLE_OPEN = "circle_open"  # cảnh mới nở tròn từ giữa
    ZOOM_IN = "zoom_in"  # cảnh cũ phóng to rồi chuyển sang cảnh mới


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
        if self.transition_type != TransitionType.NONE and not 0.2 <= self.duration_sec <= 1.5:
            raise ValueError("thời lượng hiệu ứng phải từ 0,2 đến 1,5 giây")


@dataclass
class AudioConfig:
    """Audio của video thành phẩm: nhạc nền, voice thay thế và tiếng gốc, mỗi nguồn một âm lượng riêng."""
    music_files: list[Path] = field(default_factory=list)  # nhạc nền, không cần ngôn ngữ
    voice_files: list[Path] = field(default_factory=list)  # voice thay thế, bắt buộc có ngôn ngữ
    language_labels: dict[str, str] = field(default_factory=dict)  # tên file voice -> mã ngôn ngữ
    keep_original: bool = False  # giữ tiếng và nhạc của video gốc
    music_volume: float = 1.0  # 0 – 2 (1 = 100%)
    voice_volume: float = 1.0
    original_volume: float = 1.0
    duck_music: bool = False  # tự giảm nhạc nền khi có voice

    @property
    def has_replacement(self) -> bool:
        return bool(self.music_files or self.voice_files)

    def voice_language(self, path: Path) -> str:
        """Mã ngôn ngữ của file voice: ưu tiên nhãn người dùng chọn, sau đó đoán từ tên file."""
        from videobulkremixer.audio_mixer import guess_language_from_filename
        return (self.language_labels.get(path.name) or guess_language_from_filename(path.name) or "").lower()


@dataclass
class TextRegion:
    """Một vùng text trên video. Nếu có `points` (4 góc theo chiều kim đồng hồ) thì vùng là tứ giác (có thể nghiêng)."""
    name: str  # "Tiêu đề", "CTA"...
    x: int
    y: int
    width: int
    height: int
    points: tuple[tuple[float, float], ...] = ()

    def corners(self) -> tuple[tuple[float, float], ...]:
        if self.points:
            if len(self.points) != 4:
                raise ValueError(f"vùng '{self.name}' cần đúng 4 góc")
            return tuple((float(x), float(y)) for x, y in self.points)
        x, y, w, h = self.x, self.y, self.width, self.height
        return ((x, y), (x + w, y), (x + w, y + h), (x, y + h))


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
    """Một đoạn thay text: vùng + khoảng thời gian + text mới theo ngôn ngữ.

    Thời gian tính theo video gốc. end_sec = None nghĩa là đến hết video.
    """
    region: TextRegion
    texts_by_lang: dict[str, str] = field(default_factory=dict)
    # key = mã ngôn ngữ, value = text mới
    style: TextStyle = field(default_factory=TextStyle)
    start_sec: float = 0.0
    end_sec: float | None = None

    def __post_init__(self) -> None:
        if self.start_sec < 0:
            raise ValueError("thời điểm bắt đầu của đoạn text phải >= 0")
        if self.end_sec is not None and self.end_sec <= self.start_sec:
            raise ValueError(f"đoạn text '{self.region.name}': giây kết thúc phải lớn hơn giây bắt đầu")


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
        audio_count = max(len(self.audio.music_files), 1) * max(len(self.audio.voice_files), 1)
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
