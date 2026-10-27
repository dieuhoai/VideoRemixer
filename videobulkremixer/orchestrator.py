"""Điều phối toàn bộ pipeline: đọc cấu hình → tính tổ hợp → xử lý từng video → ghi report."""
from __future__ import annotations

import errno
import itertools
import os
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from videobulkremixer.audio_mixer import MixPlan, guess_language_from_filename, mix_audio
from videobulkremixer.ff import Cancelled, DiskFull, FFmpegError, probe
from videobulkremixer.models import (
    ItemResult,
    JobConfig,
    JobResult,
    TextReplacement,
    TransitionConfig,
    TransitionType,
)
from videobulkremixer.namer import generate_name
from videobulkremixer.reporter import write_report
from videobulkremixer.text_replacer import replace_text_on_video
from videobulkremixer.timeline import Part, build_timeline, joint_labels
from videobulkremixer.video_cutter import get_duration, render_clip
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
    lang: str  # "" = không có ngôn ngữ
    music: Path | None  # nhạc nền (ngôn ngữ tuỳ chọn)
    voice: Path | None  # voice thay thế (ngôn ngữ = lang)
    keep_original: bool  # giữ tiếng và nhạc gốc của video
    texts: tuple[TextReplacement, ...] = ()
    music_lang: str = ""  # ngôn ngữ nhạc nền, chỉ dùng khi không có lang từ voice/text

    @property
    def folder_lang(self) -> str:
        return self.lang or self.music_lang or "orig"


def _name_lang(spec: OutputSpec, orig_name: str) -> str:
    """Ngôn ngữ dùng để đặt tên: voice/text → nhạc nền có ngôn ngữ → ngôn ngữ trong tên video gốc → orig."""
    return spec.lang or spec.music_lang or guess_language_from_filename(orig_name) or "orig"


def build_output_plan(config: JobConfig) -> list[OutputSpec]:
    """Mỗi ngôn ngữ = một nhóm đầu ra. Voice và text cùng ngôn ngữ được ghép lại; nhạc nền dùng chung."""
    audio = config.audio
    voices_by_lang: dict[str, list[Path]] = {}
    for vf in audio.voice_files:
        voices_by_lang.setdefault(audio.voice_language(vf), []).append(vf)
    langs = {lang for lang in voices_by_lang if lang}
    for tr in config.text_replacements:
        langs.update(k for k, v in tr.texts_by_lang.items() if v and v.strip())
    musics: list[Path | None] = list(audio.music_files) or [None]
    if not langs:
        return [OutputSpec(lang="", music=m, voice=None, keep_original=audio.keep_original,
                           music_lang=audio.music_language(m) if m else "") for m in musics]
    plan: list[OutputSpec] = []
    for lang in sorted(langs):
        texts = tuple(tr for tr in config.text_replacements if (tr.texts_by_lang.get(lang) or "").strip())
        voices: list[Path | None] = list(voices_by_lang.get(lang, [])) or [None]
        for voice in voices:
            for music in musics:
                plan.append(OutputSpec(lang=lang, music=music, voice=voice,
                                       keep_original=audio.keep_original, texts=texts))
    return plan


def map_texts_to_output(
    parts: list[Part],
    part_durs: list[float],
    joints: list[TransitionConfig],
    texts: tuple[TextReplacement, ...] | list[TextReplacement],
    orig_duration: float,
) -> tuple[list[TextReplacement], bool]:
    """Đổi mốc thời gian text (theo video gốc) sang mốc của video đã ghép.

    Chỉ đoạn giữ nguyên từ gốc mới có text; đoạn thay thế (source) không được gắn text.
    Trả về (danh sách đoạn text đã đổi mốc, có đoạn text nào rơi vào đoạn thay thế không).
    """
    starts: list[float] = []
    total = 0.0
    for i, d in enumerate(part_durs):
        if i == 0:
            starts.append(0.0)
            total = d
            continue
        cfg = joints[i - 1]
        ov = 0.0 if cfg.transition_type == TransitionType.NONE else max(0.05, min(cfg.duration_sec, total / 2, d / 2))
        starts.append(total - ov)
        total = total - ov + d
    out: list[TextReplacement] = []
    skipped = False
    for tr in texts:
        a = tr.start_sec
        b = orig_duration if tr.end_sec is None else min(tr.end_sec, orig_duration)
        covered = 0.0
        for part, o_start, d in zip(parts, starts, part_durs, strict=True):
            if part.kind != "keep":
                continue
            lo, hi = max(a, part.start), min(b, part.end)
            if hi - lo <= 0.01:
                continue
            new_lo = o_start + (lo - part.start)
            new_hi = min(o_start + d, o_start + (hi - part.start))
            out.append(replace(tr, start_sec=new_lo, end_sec=new_hi))
            covered += hi - lo
        if b - a - covered > 0.05:
            skipped = True
    return out, skipped


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


def place_file(src: Path, target: Path) -> None:
    """Đặt file src thành target (target chưa tồn tại).

    Ưu tiên liên kết cứng: cùng ổ đĩa thì không sao chép dữ liệu nên nhanh hơn nhiều.
    Không được (khác ổ, ổ FAT/exFAT...) thì sao chép như cũ.
    """
    tmp = target.with_name(f".{target.name}.part")
    tmp.unlink(missing_ok=True)
    try:
        try:
            os.link(src, tmp)
        except OSError:
            shutil.copyfile(src, tmp)
        os.replace(tmp, target)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


class Pipeline:
    def __init__(
        self,
        config: JobConfig,
        on_progress: Callable[[int, int, str], None] | None = None,
        short_source_action: str = "trim",  # "trim" = co đoạn theo source, "skip" = giữ nguyên đoạn gốc
        preview: bool = False,  # True = chỉ chạy thử 1 video gốc, 1 tổ hợp, 1 ngôn ngữ
    ) -> None:
        self.config = config
        self.preview = preview
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
        for vf in cfg.audio.voice_files:
            if not cfg.audio.voice_language(vf):
                raise ValueError(f"File voice '{vf.name}' chưa có ngôn ngữ. Hãy chọn ngôn ngữ cho file này.")
        if not (cfg.segments or cfg.audio.has_replacement or cfg.audio.keep_original or cfg.text_replacements):
            raise ValueError("Chưa chọn việc gì để thay (đoạn, audio, voice hoặc text)")

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
        if self.preview:
            originals, combos, plan = originals[:1], combos[:1], plan[:1]
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
                                              language=_name_lang(spec, orig.name))
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
        audio_names = [f.name for f in (spec.music, spec.voice) if f is not None]
        if spec.keep_original:
            audio_names.append("gốc")
        lang = _name_lang(spec, orig.name)
        item = ItemResult(source_video=orig.name, duration_in=info.duration, language=lang,
                          audio_file=" + ".join(audio_names) or "không có")
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

            # 3. Thay text theo ngôn ngữ: mốc thời gian của text tính theo video gốc, đổi sang video đã ghép
            if spec.texts:
                part_durs = [get_duration(p) for p in parts]
                mapped, skipped = map_texts_to_output(timeline, part_durs, joints, spec.texts, info.duration)
                if skipped:
                    notes.append("có đoạn text rơi vào đoạn thay thế nên không được thay")
                res = (replace_text_on_video(current, mapped, spec.lang, item_dir / "text.mp4", cancel)
                       if mapped else None)
                if res is not None and res.output is not None:
                    current = res.output
                    item.text_replaced = True
                    if res.note:
                        notes.append(res.note)

            # 4. Audio: nhạc nền + voice + tiếng gốc, mỗi nguồn một âm lượng
            final = item_dir / "final.mp4"
            ac = cfg.audio
            plan = MixPlan(music=spec.music, voice=spec.voice, keep_original=spec.keep_original,
                           music_volume=ac.music_volume, voice_volume=ac.voice_volume,
                           original_volume=ac.original_volume, duck_music=ac.duck_music)
            amsg = mix_audio(current, plan, final, cancel)
            if amsg:
                notes.append(amsg)

            # 5. Đặt tên theo naming convention, không ghi đè file đã có
            out_path = self._place_output(final, spec, info.ratio, lang)
            item.output_path = out_path
            item.ok = True
            item.duration_out = probe(str(out_path)).duration
            item.size_mb = out_path.stat().st_size / (1024 * 1024)
            item.note = "; ".join(notes)
            if spec.keep_original and not probe(str(orig)).has_audio:
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

    def _place_output(self, src: Path, spec: OutputSpec, ratio: str, lang: str) -> Path:
        cfg = self.config
        folder_name = f"{cfg.naming.geo}_{lang}" if cfg.naming.geo else lang
        folder = cfg.output_dir / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        stt = self._stt.get(folder_name, 0) + 1
        while True:
            name = generate_name(cfg.naming, lang, ratio, stt)
            target = folder / name
            if not target.exists():
                break
            stt += 1
        self._stt[folder_name] = stt
        try:
            place_file(src, target)
        except OSError as e:
            if e.errno == errno.ENOSPC:
                raise DiskFull() from e
            raise
        return target


def describe_joints(timeline: list[Part]) -> list[str]:
    return joint_labels(timeline)


__all__ = ["Pipeline", "OutputSpec", "build_output_plan", "build_source_combos", "list_videos"]
