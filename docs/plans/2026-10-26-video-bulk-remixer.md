# Plan: Video Bulk Remixer

- Spec: [docs/specs/2026-10-26-video-bulk-remixer.md](../specs/2026-10-26-video-bulk-remixer.md)
- Ngày: 2026-10-26

## Task

### T1 — Models: dataclass cho toàn bộ config & result
- File: `videobulkremixer/models.py`, `tests/unit/test_models.py`
- Test viết trước: `test_segment_config_validation` (AC3 — chồng lấn), `test_naming_config_format` (AC14), `test_job_config_combo_count`
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_models.py`
- Commit: `feat(core): models cho segment, audio, text, transition, naming, job`

### T2 — Video cutter: cắt video theo timestamp
- File: `videobulkremixer/video_cutter.py`, `tests/unit/test_video_cutter.py`
- Test viết trước: `test_cut_segment`, `test_cut_returns_correct_duration`
- Phụ thuộc: T1
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_video_cutter.py`
- Commit: `feat(core): cắt video theo timestamp bằng ffmpeg`

### T3 — Video joiner: ghép đoạn + xử lý source dài/ngắn
- File: `videobulkremixer/video_joiner.py`, `tests/unit/test_video_joiner.py`
- Test viết trước: `test_join_segments_basic`, `test_source_longer_trimmed` (AC4), `test_source_shorter_detected` (AC5), `test_multi_segment_join` (AC2)
- Phụ thuộc: T1, T2
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_video_joiner.py`
- Commit: `feat(core): ghép video + xử lý source dài/ngắn`

### T4 — Audio mixer: thay/giữ audio, pad/cắt, nhãn ngôn ngữ
- File: `videobulkremixer/audio_mixer.py`, `tests/unit/test_audio_mixer.py`
- Test viết trước: `test_keep_original_audio` (AC6), `test_replace_audio_multi_lang` (AC7), `test_audio_shorter_pad_silence` (AC8), `test_audio_longer_trim` (AC9), `test_audio_xuyên_suốt` (AC5 — audio không cắt theo đoạn hình)
- Phụ thuộc: T1
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_audio_mixer.py`
- Commit: `feat(core): audio mixer — thay/giữ audio, pad silence, cắt đuôi`

### T5 — Transition: hiệu ứng chuyển cảnh tại mối nối
- File: `videobulkremixer/transition.py`, `tests/unit/test_transition.py`
- Test viết trước: `test_crossfade_applied` (AC12), `test_different_transitions_per_joint` (AC13), `test_no_transition_default`
- Phụ thuộc: T1, T3
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_transition.py`
- Commit: `feat(core): hiệu ứng chuyển cảnh — crossfade, fade, slide, wipe`

### T6 — Text replacer: inpaint xoá text + render text mới
- File: `videobulkremixer/text_replacer.py`, `tests/unit/test_text_replacer.py`
- Test viết trước: `test_inpaint_clean` (AC11), `test_render_text_multilang` (AC10), `test_text_style_applied`
- Phụ thuộc: T1
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_text_replacer.py`
- Commit: `feat(core): inpaint xoá text + render text đa ngôn ngữ`

### T7 — Namer: sinh tên output + preview
- File: `videobulkremixer/namer.py`, `tests/unit/test_namer.py`
- Test viết trước: `test_naming_convention_format` (AC14), `test_stt_auto_increment`, `test_ratio_auto_detect`, `test_date_default_today`
- Phụ thuộc: T1
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_namer.py`
- Commit: `feat(core): naming convention Appname_VID_Concept_Geo_Language_Date_Ratio_STT`

### T8 — Reporter: tạo report.csv
- File: `videobulkremixer/reporter.py`, `tests/unit/test_reporter.py`
- Test viết trước: `test_report_columns_complete` (AC15), `test_report_error_logged` (AC18), `test_report_trim_note` (AC4)
- Phụ thuộc: T1
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_reporter.py`
- Commit: `feat(core): report.csv chi tiết`

### T9 — Orchestrator: điều phối pipeline + output folders
- File: `videobulkremixer/orchestrator.py`, `tests/unit/test_orchestrator.py`
- Test viết trước: `test_full_pipeline_basic` (AC1), `test_multi_segment_pipeline` (AC2), `test_lang_folder_structure` (AC15), `test_error_skip_continue` (AC18), `test_cancel_midway`, `test_audio_text_lang_match` (AC20)
- Phụ thuộc: T2–T8
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_orchestrator.py`
- Commit: `feat(core): orchestrator — điều phối pipeline + phân thư mục ngôn ngữ`

### T10 — CLI entry point
- File: `videobulkremixer/processor.py`, `videobulkremixer/__main__.py`, `tests/unit/test_cli.py`
- Test viết trước: `test_cli_run_basic`, `test_cli_help`
- Phụ thuộc: T9
- Kiểm: `.venv/bin/python -m pytest -q tests/unit/test_cli.py`
- Commit: `feat(cli): entry point CLI`

### T11 — Web API: endpoints cho UI
- File: `web/api/routes.py`, `tests/web/test_api.py`
- Test viết trước: `test_upload_sources`, `test_start_job`, `test_progress_sse`, `test_preview_names`, `test_cancel_job`
- Phụ thuộc: T9
- Kiểm: `.venv/bin/python -m pytest -q tests/web/test_api.py`
- Commit: `feat(web): API endpoints`

### T12 — Web UI: màn hình chính — 4 khu vực + video player
- File: `web/static/index.html`, `web/static/app.js`, `web/static/style.css`
- Phụ thuộc: T11
- AC liên quan: AC16, AC17
- Commit: `feat(ui): màn hình chính + video preview player`

### T13 — Web UI: timeline kéo thả hiệu ứng
- File: `web/static/timeline.js`
- Phụ thuộc: T12
- AC liên quan: AC12, AC13
- Commit: `feat(ui): timeline kéo thả hiệu ứng vào mối nối`

### T14 — Web UI: tab Text — bảng nhập đa ngôn ngữ + bounding box
- File: `web/static/text-editor.js`
- Phụ thuộc: T12
- AC liên quan: AC10
- Commit: `feat(ui): bảng text đa ngôn ngữ + chọn vùng text`

### T15 — Web UI: naming preview + thanh tiến độ + kết quả
- File: `web/static/output.js`
- Phụ thuộc: T12
- AC liên quan: AC14, AC19
- Commit: `feat(ui): naming preview + progress + bảng kết quả`

## Song song
- T2, T4, T6, T7, T8 [song song] — không phụ thuộc nhau
- T5 chờ T3
- T9 chờ tất cả core
- T12–T15 [song song] sau T11

## Rủi ro / cần lưu ý
- **ffmpeg phải đóng kèm** — script build tải ffmpeg static vào bin/, không yêu cầu cài trên máy user
- **Inpaint text trên nền động** — chất lượng phụ thuộc loại nền; nền phức tạp (chuyển cảnh nhanh) có thể không sạch 100% → fallback: lấy frame liền kề patch, hoặc đè hộp màu nền + text mới
- **Hiệu năng batch lớn** — 500+ video: dùng thread pool cho ffmpeg subprocess, tránh chạy quá nhiều ffmpeg song song gây hết RAM
- **Codec khác nhau** — source VP9 + gốc H.264: phải re-encode → chậm hơn stream-copy; ghi chú trong report
- **Windows long path** — dùng `\\?\` prefix cho đường dẫn > 260 ký tự

## Định nghĩa xong
- [ ] Mọi AC trong spec (AC1–AC18) có test xanh
- [ ] `ruff check .` sạch, `pytest -q` xanh
- [ ] CHANGELOG `[Unreleased]` đã cập nhật
- [ ] Giao diện dùng thử được, người không chuyên thao tác không cần hỏi
