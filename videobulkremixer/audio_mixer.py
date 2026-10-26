"""Thay / giữ audio — 1 track xuyên suốt video, không cắt theo từng đoạn hình."""
from __future__ import annotations

from pathlib import Path

from videobulkremixer.ff import CancelCheck, probe, run_ffmpeg
from videobulkremixer.video_cutter import get_duration


def replace_audio(
    video: Path,
    audio_source: Path,
    output: Path,
    cancel: CancelCheck | None = None,
) -> str:
    """Ghép audio của `audio_source` (file audio, hoặc chính video gốc) vào `video`.

    - Audio dài hơn video → cắt đuôi cho bằng video.
    - Audio ngắn hơn video → đệm im lặng ở cuối.
    - Nguồn không có audio → output không có tiếng.
    Trả về ghi chú ngắn để đưa vào report.
    """
    video_dur = get_duration(video)
    if not probe(str(audio_source)).has_audio:
        run_ffmpeg(["-i", str(video), "-an", "-c:v", "copy", str(output)], cancel=cancel)
        return "gốc không có audio, output không có tiếng"
    audio_dur = get_duration(audio_source)
    note = ""
    af = "aresample=44100"
    if audio_dur > video_dur + 0.05:
        note = f"audio cắt đuôi {audio_dur:.1f}s → {video_dur:.1f}s"
    elif audio_dur < video_dur - 0.05:
        note = f"audio đệm {video_dur - audio_dur:.1f}s im lặng cuối"
        af += f",apad=whole_dur={video_dur:.3f}"
    run_ffmpeg([
        "-i", str(video), "-i", str(audio_source),
        "-map", "0:v:0", "-map", "1:a:0",
        "-af", af, "-t", f"{video_dur:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output),
    ], cancel=cancel)
    return note


LANGUAGES = [
    "vi", "en", "es", "pt", "fr", "de", "ja", "ko", "zh",
    "th", "id", "ar", "ru", "it", "tr", "pl", "nl", "sv", "hi", "ms", "tl",
]


def guess_language_from_filename(filename: str) -> str:
    """Đoán mã ngôn ngữ từ tên file: voice_EN.mp3 → en, audio-pt.mp3 → pt."""
    stem = Path(filename).stem.lower()
    parts = stem.replace("-", "_").replace(" ", "_").split("_")
    for part in reversed(parts):
        if part in LANGUAGES:
            return part
    return ""
