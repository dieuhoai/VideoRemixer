"""Ghép audio cho video thành phẩm: nhạc nền, voice thay thế và tiếng gốc, mỗi nguồn một âm lượng riêng."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from videobulkremixer.ff import CancelCheck, probe, run_ffmpeg
from videobulkremixer.video_cutter import get_duration

# Mã ngôn ngữ theo bảng quy ước đặt tên của Team (30 mã) + ru (Nga, giữ theo yêu cầu).
LANGUAGES = [
    "ar", "bn", "da", "de", "en", "es", "fi", "fr", "hi", "id", "is", "it", "ja", "km", "ko", "lo",
    "mr", "ms", "my", "nl", "no", "pl", "pt", "ru", "sv", "th", "tl", "tr", "ur", "vi", "zh",
]


def guess_language_from_filename(filename: str) -> str:
    """Đoán mã ngôn ngữ từ tên file: Voice01_EN.mp3 → en, giong-nu_vi.wav → vi. Không đoán được → ''."""
    stem = Path(filename).stem.lower()
    parts = stem.replace("-", "_").replace(" ", "_").split("_")
    last = parts[-1] if parts else ""
    return last if last in LANGUAGES else ""


@dataclass(frozen=True)
class MixPlan:
    music: Path | None = None
    voice: Path | None = None
    keep_original: bool = False
    music_volume: float = 1.0
    voice_volume: float = 1.0
    original_volume: float = 1.0
    duck_music: bool = False

    @property
    def is_empty(self) -> bool:
        return self.music is None and self.voice is None and not self.keep_original


def mix_audio(video: Path, plan: MixPlan, output: Path, cancel: CancelCheck | None = None) -> str:
    """Ghi video ra `output` với audio theo `plan`. Trả về ghi chú ngắn cho report.

    - Nhạc nền: lặp lại nếu ngắn hơn video, cắt và fade out 0,8 giây cuối nếu dài hơn.
    - Voice: đệm im lặng nếu ngắn hơn video, cắt nếu dài hơn.
    - Tiếng gốc: lấy từ chính video nguồn (nếu video có tiếng).
    - duck_music: khi có voice, nhạc nền tự giảm xuống theo voice.
    - Không có nguồn nào → video không có tiếng.
    """
    dur = get_duration(video)
    src_has_audio = probe(str(video)).has_audio
    keep = plan.keep_original and src_has_audio
    inputs: list[str] = ["-i", str(video)]
    chains: list[str] = []
    notes: list[str] = []
    labels: list[str] = []
    idx = 1

    if plan.is_empty or (plan.music is None and plan.voice is None and not keep):
        if plan.keep_original and not src_has_audio:
            notes.append("gốc không có audio")
        run_ffmpeg(["-i", str(video), "-an", "-c:v", "copy", "-movflags", "+faststart", str(output)],
                   cancel=cancel)
        return "; ".join(notes) if notes else "video không có tiếng"

    voice_label = None
    if plan.voice is not None:
        vdur = get_duration(plan.voice)
        inputs += ["-i", str(plan.voice)]
        voice_label = f"[{idx}:a]"
        idx += 1
        if vdur < dur - 0.05:
            notes.append(f"voice đệm {dur - vdur:.1f}s im lặng cuối")
        elif vdur > dur + 0.05:
            notes.append(f"voice cắt đuôi {vdur:.1f}s → {dur:.1f}s")
    if plan.music is not None:
        inputs += ["-stream_loop", "-1", "-i", str(plan.music)]
        mdur = get_duration(plan.music)
        if mdur < dur - 0.05:
            notes.append(f"nhạc lặp lại để đủ {dur:.1f}s")
        music_label = f"[{idx}:a]"
        idx += 1
        fade_at = max(0.0, dur - 0.8)
        chains.append(f"{music_label}volume={plan.music_volume:.3f},aresample=44100,"
                      f"atrim=0:{dur:.3f},afade=t=out:st={fade_at:.3f}:d=0.8[music]")
        if plan.voice is not None and plan.duck_music:
            chains.append(f"{voice_label}volume={plan.voice_volume:.3f},aresample=44100,apad,"
                          f"atrim=0:{dur:.3f},asplit=2[voice_mix][voice_key]")
            chains.append("[music][voice_key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400"
                          "[music_ducked]")
            labels.append("[music_ducked]")
            notes.append("nhạc tự giảm khi có voice")
        else:
            labels.append("[music]")
            if plan.voice is not None:
                chains.append(f"{voice_label}volume={plan.voice_volume:.3f},aresample=44100,apad,"
                              f"atrim=0:{dur:.3f}[voice_mix]")
    elif plan.voice is not None:
        chains.append(f"{voice_label}volume={plan.voice_volume:.3f},aresample=44100,apad,"
                      f"atrim=0:{dur:.3f}[voice_mix]")
    if plan.voice is not None:
        labels.append("[voice_mix]")
    if keep:
        chains.append(f"[0:a]volume={plan.original_volume:.3f},aresample=44100,atrim=0:{dur:.3f}[orig]")
        labels.append("[orig]")
    elif plan.keep_original and not src_has_audio:
        notes.append("gốc không có audio")

    if len(labels) == 1:
        chains.append(f"{labels[0]}alimiter=limit=0.95[aout]")
    else:
        chains.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
                      "alimiter=limit=0.95[aout]")
    run_ffmpeg([
        *inputs, "-filter_complex", ";".join(chains), "-map", "0:v:0", "-map", "[aout]",
        "-t", f"{dur:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output),
    ], cancel=cancel)
    return "; ".join(notes)
