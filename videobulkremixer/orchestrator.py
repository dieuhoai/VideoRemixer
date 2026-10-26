"""Điều phối toàn bộ pipeline: đọc cấu hình → tính tổ hợp → xử lý từng video → ghi report."""
from __future__ import annotations

import errno
import itertools
import os
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from videobulkremixer.audio_mixer import guess_language_from_filename, replace_audio
from videobulkremixer.ff import Cancelled, DiskFull, FFmpegError, probe
from videobulkremixer.models import ItemResult, JobConfig, JobResult, TextReplacement, TransitionType
from videobulkremixer.namer import generate_name
from videobulkremixer.reporter import write_report
from videobulkremixer.text_replacer import replace_text_on_video
from videobulkremixer.timeline import Part, build_timeline, joint_labels
from videobulkremixer.video_cutter import render_clip
from videobulkremixer.video_joiner import join_with_transitions

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv"}
SEG_KEY = {"intro": "intro", "custom": "custom", "outro": "outro"}
SEG_NAME = {"intro": "Intro", "custom": "Giữa", "outro": "Outro"}


def list_videos(directory: Path) -> list[Path]:
    """Video ở thư mục gốc (không đệ quy), bỏ file ẩn và file tạm của Office."""
    if not directory.is_dir():
        return []
    return sorted(
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS and not f.name.startswith((".", "~$"))
    )


@dataclass(frozen=True)
class OutputSpec:
    lang: str  # "" = không có ngôn ngữ (dùng audio + text gốc)
    audio: Path | None  # None = giữ audio gốc của video
    texts: tuple[TextReplacement, ...] = ()

    @property
    def folder_lang(self) -> str:
        return self.lang or "orig"


def build_output_plan(config: JobConfig) -> list[OutputSpec]:
    """Mỗi ngôn ngữ = 1 bộ đầu ra. Audio và text cùng ngôn ngữ được ghép với nhau."""
    audio_by_lang: dict[str, list[Path]] = {}
    for af in config.audio.audio_files:
        label = config.audio.language_labels.get(af.name) or guess_language_from_filename(af.name) or af.stem
        audio_by_lang.setdefault(label, []).append(af)
    langs = set(audio_by_lang)
    for tr in config.text_replacements:
        langs.update(k for k, v in tr.texts_by_lang.items() if v and v.strip())
    if not langs:
        return [OutputSpec(lang="", audio=None)]
    plan: list[OutputSpec] = []
    for lang in sorted(langs):
        texts = tuple(tr for tr in config.text_replacements if (tr.texts_by_lang.get(lang) or "").strip())
        for audio in audio_by_lang.get(lang) or [None]:
            plan.append(OutputSpec(lang=lang, audio=audio, texts=texts))
    return plan


def build_source_combos(config: JobConfig) -> list[dict[str, Path | None]]:
    """Mọi tổ hợp source của các đoạn đang bật (tích Descartes)."""
    if not config.segments:
        return [{}]
    keys = [s.segment_type.value for s in config.segments]
    options = [list_videos(s.source_dir) for s in config.segments]
    return [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*options)]


def _friendly(exc: Exception) -> str:
    if isinstance(exc, FFmpegError):
        return str(exc)
    return f"lỗi không xác định: {str(exc)[:160]}"


class Pipeline:
    def __init__(
        self,
        config: JobConfig,
        on_progress: Callable[[int, int, str], None] | None = None,
        short_source_action: str = "trim",  # "trim" = co đoạn theo source, "skip" = giữ nguyên đoạn gốc
    ) -> None:
        self.config = config
        self.on_progress = on_progress
        self.short_source_action = short_source_action
        self._cancel = threading.Event()
        self._seq = 0
        self._stt: dict[str, int] = {}
        self._work: Path | None = None
        self._clips: dict[tuple, Path] = {}

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        self._cancel.set()

    # ---- kiểm tra trước khi chạy -------------------------------------------------
    def validate(self) -> None:
        cfg = self.config
        if not cfg.input_dir.is_dir():
            raise ValueError("Thư mục video gốc không tồn tại")
        if cfg.output_dir.resolve() == cfg.input_dir.resolve():
            raise ValueError("Thư mục Output không được trùng với thư mục video gốc")
        if not list_videos(cfg.input_dir):
            raise ValueError("Chưa có video nào trong thư mục gốc")
        cfg.validate_no_overlap()
        for seg in cfg.segments:
            if not list_videos(seg.source_dir):
                raise ValueError(f"Thư mục source {SEG_NAME[seg.segment_type.value]} chưa có video nào")
        if not (cfg.segments or cfg.audio.has_replacement or cfg.text_replacements):
            raise ValueError("Chưa chọn việc gì để thay (đoạn, audio hoặc text)")

    def check_short_sources(self) -> list[dict]:
        """Các source ngắn hơn đoạn cần thay (tính theo video gốc đầu tiên)."""
        originals = list_videos(self.config.input_dir)
        if not originals or not self.config.segments:
            return []
        ref = probe(str(originals[0])).duration
        warnings: list[dict] = []
        for seg in self.config.segments:
            seg_dur = min(seg.end_sec, ref) - seg.start_sec
            for src in list_videos(seg.source_dir):
                try:
                    sd = probe(str(src)).duration
                except FFmpegError:
                    continue
                if sd < seg_dur - 0.1:
                    warnings.append({
                        "source": src.name, "segment": SEG_NAME[seg.segment_type.value],
                        "source_dur": round(sd, 1), "segment_dur": round(seg_dur, 1),
                    })
        return warnings

    # ---- chạy --------------------------------------------------------------------
    def run(self) -> JobResult:
        cfg = self.config
        self.validate()
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        result = JobResult()
        originals = list_videos(cfg.input_dir)
        plan = build_output_plan(cfg)
        combos = build_source_combos(cfg)
        total = len(originals) * len(combos) * len(plan)
        current = 0
        with tempfile.TemporaryDirectory(prefix="vbr_") as tmp:
            work = Path(tmp)
            self._work = work
            self._clips.clear()
            for orig in originals:
                if self.cancelled:
                    break
                try:
                    info = probe(str(orig))
                    timeline = build_timeline(cfg.segments, info.duration)
                except Exception as e:  # noqa: BLE001 — một file lỗi không dừng cả lô
                    result.items.append(ItemResult(source_video=orig.name, ok=False, error=_friendly(e)))
                    current += len(combos) * len(plan)
                    continue
                stop = False
                for combo in combos:
                    for spec in plan:
                        if self.cancelled:
                            stop = True
                            break
                        current += 1
                        if self.on_progress:
                            self.on_progress(current, total, orig.name)
                        try:
                            item = self._process_one(orig, info, timeline, combo, spec, work)
                        except Cancelled:
                            stop = True
                            break
                        except DiskFull:
                            result.fatal = "Hết dung lượng ổ đĩa — đã dừng. Các file đã xong vẫn được giữ lại."
                            stop = True
                            break
                        except Exception as e:  # noqa: BLE001
                            item = ItemResult(source_video=orig.name, ok=False, error=_friendly(e),
                                              language=spec.folder_lang)
                        result.items.append(item)
                    if stop:
                        break
                if stop:
                    break
        result.cancelled = self.cancelled
        write_report(result, cfg.output_dir)
        return result

    def _process_one(
        self,
        orig: Path,
        info,
        timeline: list[Part],
        combo: dict[str, Path | None],
        spec: OutputSpec,
        work: Path,
    ) -> ItemResult:
        cfg = self.config
        self._seq += 1
        seq = self._seq
        item_dir = work / f"item_{seq}"
        item_dir.mkdir()
        cancel = self.cancelled_check
        W, H = info.width - info.width % 2, info.height - info.height % 2
        item = ItemResult(source_video=orig.name, duration_in=info.duration, language=spec.folder_lang,
                          audio_file=spec.audio.name if spec.audio else "gốc")
        notes: list[str] = []
        try:
            # 1. Dựng các đoạn hình: giữ gốc hoặc thay bằng source
            parts: list[Path] = []
            for part in timeline:
                if part.kind == "keep":
                    parts.append(self._clip(orig, part.start, part.duration, W, H, cancel))
                    continue
                key = part.segment_type.value
                src = combo.get(key)
                name = SEG_NAME[key]
                if src is None:
                    clip = self._clip(orig, part.start, part.duration, W, H, cancel)
                else:
                    sinfo = probe(str(src))
                    if sinfo.duration > part.duration + 0.1:
                        clip = self._clip(src, 0, part.duration, W, H, cancel)
                        notes.append(f"source {name} bị cắt từ {sinfo.duration:.1f}s → {part.duration:.1f}s")
                    elif sinfo.duration < part.duration - 0.1 and self.short_source_action == "skip":
                        clip = self._clip(orig, part.start, part.duration, W, H, cancel)
                        notes.append(f"bỏ qua source {name} ngắn ({sinfo.duration:.1f}s < {part.duration:.1f}s)")
                        src = None
                    else:
                        clip = self._clip(src, 0, sinfo.duration, W, H, cancel)
                        if sinfo.duration < part.duration - 0.1:
                            notes.append(f"đoạn {name} co lại còn {sinfo.duration:.1f}s theo source")
                    if src is not None:
                        setattr(item, {"intro": "source_intro", "custom": "source_mid",
                                       "outro": "source_outro"}[key], src.name)
                parts.append(clip)

            # 2. Ghép các đoạn với hiệu ứng tại từng mối nối
            joints = [cfg.transition_for_joint(i) for i in range(len(parts) - 1)]
            joined = item_dir / "joined.mp4"
            join_with_transitions(parts, joints, joined, item_dir, cancel)
            used = sorted({t.transition_type.value for t in joints if t.transition_type != TransitionType.NONE})
            item.transition_used = ",".join(used)
            current = joined

            # 3. Thay text theo ngôn ngữ
            if spec.texts:
                res = replace_text_on_video(current, list(spec.texts), spec.lang, item_dir / "text.mp4", cancel)
                if res.output is not None:
                    current = res.output
                    item.text_replaced = True
                if res.note:
                    notes.append(res.note)

            # 4. Audio: 1 track xuyên suốt (audio gốc hoặc audio thay thế)
            final = item_dir / "final.mp4"
            audio_src = spec.audio or orig
            amsg = replace_audio(current, audio_src, final, cancel)
            if amsg:
                notes.append(amsg)

            # 5. Đặt tên theo naming convention, không ghi đè file đã có
            out_path = self._place_output(final, spec, info.ratio)
            item.output_path = out_path
            item.ok = True
            item.duration_out = probe(str(out_path)).duration
            item.size_mb = out_path.stat().st_size / (1024 * 1024)
            item.note = "; ".join(notes)
            if spec.audio is None and not probe(str(orig)).has_audio:
                item.note = (item.note + "; " if item.note else "") + "video gốc không có audio"
            return item
        finally:
            shutil.rmtree(item_dir, ignore_errors=True)

    def _clip(self, src: Path, start: float, duration: float, width: int, height: int,
              cancel: Callable[[], bool]) -> Path:
        """Render một đoạn đúng 1 lần cho cả run; mọi tổ hợp dùng lại cùng file (tiết kiệm thời gian)."""
        key = (str(src), round(start, 3), round(duration, 3), width, height)
        if key not in self._clips:
            assert self._work is not None
            clip_dir = self._work / "clips"
            clip_dir.mkdir(exist_ok=True)
            out = clip_dir / f"clip_{len(self._clips):05d}.mp4"
            render_clip(src, start, duration, width, height, out, cancel)
            self._clips[key] = out
        return self._clips[key]

    def cancelled_check(self) -> bool:
        return self.cancelled

    def _place_output(self, src: Path, spec: OutputSpec, ratio: str) -> Path:
        cfg = self.config
        folder_name = f"{cfg.naming.geo}_{spec.folder_lang}" if cfg.naming.geo else spec.folder_lang
        folder = cfg.output_dir / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        stt = self._stt.get(folder_name, 0) + 1
        while True:
            name = generate_name(cfg.naming, spec.folder_lang, ratio, stt)
            target = folder / name
            if not target.exists():
                break
            stt += 1
        self._stt[folder_name] = stt
        tmp = folder / f".{name}.part"
        try:
            shutil.copyfile(src, tmp)
            os.replace(tmp, target)
        except OSError as e:
            tmp.unlink(missing_ok=True)
            if e.errno == errno.ENOSPC:
                raise DiskFull() from e
            raise
        return target


def describe_joints(timeline: list[Part]) -> list[str]:
    return joint_labels(timeline)


__all__ = ["Pipeline", "OutputSpec", "build_output_plan", "build_source_combos", "list_videos"]
