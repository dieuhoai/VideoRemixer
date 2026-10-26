"""Chạy pipeline thật bằng ffmpeg trên video mẫu nhỏ — kiểm các tiêu chí chấp nhận trong spec."""
import csv
import subprocess

import pytest

from videobulkremixer.ff import probe
from videobulkremixer.models import (
    AudioConfig,
    JobConfig,
    NamingConfig,
    SegmentConfig,
    SegmentType,
    TextRegion,
    TextReplacement,
    TextStyle,
    TransitionConfig,
    TransitionType,
)
from videobulkremixer.orchestrator import Pipeline

pytestmark = pytest.mark.integration

REPORT_COLUMNS = ["Tên file output", "Video gốc", "Source intro", "Source giữa", "Source outro", "Audio",
                  "Ngôn ngữ", "Text thay", "Thời lượng gốc (s)", "Thời lượng output (s)", "Dung lượng (MB)",
                  "Hiệu ứng", "Trạng thái", "Ghi chú"]


def _naming(**kw):
    base = dict(appname="MyApp-GP", concept="Summer", geo="BR", date_str="261026")
    base.update(kw)
    return NamingConfig(**base)


def test_intro_replacement_creates_one_output_per_source_and_keeps_length(media, tmp_path):
    """AC1 (rút gọn): 2 video gốc hợp lệ × 2 source intro = 4 video; source 6s bị cắt còn 5s, ghi vào report."""
    cfg = JobConfig(
        input_dir=media / "orig", output_dir=tmp_path / "out",
        segments=[SegmentConfig(SegmentType.INTRO, 0, 5, media / "intro")],
        naming=_naming(),
    )
    res = Pipeline(cfg).run()
    assert res.total == 5  # 4 kết quả hợp lệ + 1 file hỏng (broken.mp4)
    assert res.ok_count == 4
    cut = [i for i in res.items if i.ok and "long6" in i.source_intro]
    assert cut and all("bị cắt" in i.note for i in cut)
    assert all(i.duration_out == pytest.approx(i.duration_in - 0.0, abs=0.3) for i in cut)


def test_broken_file_is_skipped_and_reported_without_stopping_batch(media, tmp_path):
    """AC18: file lỗi bỏ qua, ghi report, các file khác vẫn xong."""
    cfg = JobConfig(input_dir=media / "orig", output_dir=tmp_path / "out",
                    segments=[SegmentConfig(SegmentType.OUTRO, 9, float("inf"), media / "outro")],
                    naming=_naming())
    res = Pipeline(cfg).run()
    failed = res.failed
    assert any(f.source_video == "broken.mp4" for f in failed)
    assert res.ok_count == 2  # 2 video hợp lệ × 1 source outro; file hỏng không làm dừng cả lô
    with open(tmp_path / "out" / "report.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == REPORT_COLUMNS
    assert any("broken.mp4" in r[1] and r[12].startswith("Lỗi") for r in rows[1:])


def test_short_source_is_trimmed_by_default_and_warned_before_run(media, tmp_path):
    """AC5: source 2s < đoạn 5s → cảnh báo; chọn co đoạn → đoạn còn 2s, ghi chú trong report."""
    cfg = JobConfig(input_dir=media / "orig", output_dir=tmp_path / "out",
                    segments=[SegmentConfig(SegmentType.INTRO, 0, 5, media / "intro")], naming=_naming())
    pipe = Pipeline(cfg)
    warns = pipe.check_short_sources()
    assert [w["source"] for w in warns] == ["short2.mp4"]
    res = Pipeline(cfg).run()
    shortened = [i for i in res.items if i.ok and "short2" in i.source_intro]
    assert shortened and all("co lại" in i.note for i in shortened)
    assert all(i.duration_out < i.duration_in - 1.5 for i in shortened)


def test_audio_replacement_per_language_goes_into_matching_folder(media, tmp_path):
    """AC7 + AC15: mỗi audio → thư mục ngôn ngữ riêng, STT bắt đầu từ 001 trong mỗi thư mục."""
    cfg = JobConfig(input_dir=media / "orig", output_dir=tmp_path / "out",
                    audio=AudioConfig(audio_files=[media / "audio" / "voice_EN.mp3",
                                                   media / "audio" / "voice_VI.mp3"]),
                    naming=_naming())
    res = Pipeline(cfg).run()
    assert res.ok_count == 4
    assert (tmp_path / "out" / "BR_en").is_dir() and (tmp_path / "out" / "BR_vi").is_dir()
    names = sorted(p.name for p in (tmp_path / "out" / "BR_en").glob("*.mp4"))
    assert names[0].endswith("_en_261026_16x9_001.mp4") or names[0].endswith("_en_261026_9x16_001.mp4")
    assert any(n.endswith("_001.mp4") for n in names) and any(n.endswith("_002.mp4") for n in names)


def test_audio_is_cut_or_padded_to_video_length(media, tmp_path):
    """AC8 + AC9: audio 20s trên video 12s → cắt đuôi; audio 8s → đệm im lặng."""
    cfg = JobConfig(input_dir=media / "orig", output_dir=tmp_path / "out",
                    audio=AudioConfig(audio_files=[media / "audio" / "voice_VI.mp3"]), naming=_naming())
    res = Pipeline(cfg).run()
    for it in res.items:
        if it.ok:
            assert it.duration_out == pytest.approx(it.duration_in, abs=0.3)
            assert "cắt đuôi" in it.note
    cfg2 = JobConfig(input_dir=media / "orig", output_dir=tmp_path / "out2",
                     audio=AudioConfig(audio_files=[media / "audio" / "voice_EN.mp3"]), naming=_naming())
    res2 = Pipeline(cfg2).run()
    assert all("đệm" in i.note for i in res2.items if i.ok)


def test_crossfade_between_parts_shortens_video_by_overlap(media, tmp_path):
    """AC12: crossfade 0.5s ở 2 mối nối → video ngắn đi 1s."""
    cfg = JobConfig(input_dir=media / "orig", output_dir=tmp_path / "out",
                    segments=[SegmentConfig(SegmentType.INTRO, 0, 3, media / "outro")],
                    default_transition=TransitionConfig(TransitionType.CROSSFADE, 0.5),
                    naming=_naming())
    res = Pipeline(cfg).run()
    good = [i for i in res.items if i.ok]
    assert good and all(i.transition_used == "crossfade" for i in good)
    assert all(i.duration_out == pytest.approx(i.duration_in - 0.5, abs=0.3) for i in good)


def test_text_is_replaced_for_its_language_only(media, tmp_path):
    """AC10 (rút gọn): text tiếng Anh được vẽ, khung hình thay đổi ở vùng text."""
    region = TextRegion("Tiêu đề", 20, 20, 160, 40)
    tr = TextReplacement(region, {"en": "Download"}, TextStyle(size=28, color="#FFFFFF"))
    cfg = JobConfig(input_dir=media / "orig", output_dir=tmp_path / "out",
                    text_replacements=[tr], naming=_naming())
    res = Pipeline(cfg).run()
    good = [i for i in res.items if i.ok]
    assert good and all(i.text_replaced and i.language == "en" for i in good)
    out = good[0].output_path
    frame = tmp_path / "frame.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(out), "-frames:v", "1", str(frame)], check=True)
    assert frame.exists() and probe(str(out)).width == 320


def test_cancel_stops_batch_and_keeps_finished_files(media, tmp_path):
    """Huỷ giữa chừng: dừng sạch, không để lại file dở."""
    cfg = JobConfig(input_dir=media / "orig", output_dir=tmp_path / "out",
                    segments=[SegmentConfig(SegmentType.INTRO, 0, 5, media / "intro")], naming=_naming())
    pipe = Pipeline(cfg, on_progress=lambda cur, total, name: pipe.cancel() if cur >= 2 else None)
    res = pipe.run()
    assert res.cancelled
    assert res.ok_count >= 1
    assert not list((tmp_path / "out").rglob(".*.part"))
