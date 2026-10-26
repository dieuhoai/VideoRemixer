# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), phiên bản theo [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Giao diện 4 khu vực đầy đủ: video gốc + xem trước (có tua), chọn đoạn + timeline kéo thả hiệu ứng, source/audio/text (vẽ vùng text trên khung hình, kiểu chữ), đặt tên + xem trước + tiến độ + bảng kết quả.
- Lõi: thay đoạn Intro/Tuỳ chọn/Outro; source dài thì cắt, source ngắn thì co đoạn hoặc bỏ qua (áp cho cả lô); audio thay thế xuyên suốt (cắt đuôi / đệm im lặng); hiệu ứng crossfade, fade đen/trắng, slide, wipe tại từng mối nối; thay text đa ngôn ngữ (inpaint OpenCV + vẽ Pillow, font Fira Sans đi kèm có dấu tiếng Việt).
- Naming convention `{Appname}_{VID}_{Concept}_{Geo}_{Language}_{Date}_{Ratio}_{STT}`, STT đếm riêng từng thư mục, không ghi đè file cũ.
- `report.csv` đầy đủ cột; file lỗi bị bỏ qua và ghi lý do; huỷ giữa chừng xoá file đang xử lý.
- CLI `python -m videobulkremixer run …`.
- `scripts/fetch_ffmpeg.py` tải ffmpeg vào `bin/` cho Windows/macOS.

### Changed
- Bỏ khung template cũ (presets đếm `.txt/.md`, kiểm tra tạo dự án/plugin) — không thuộc phạm vi tool video.
- Joint (mối nối) đánh số theo timeline của từng video: "Intro → Gốc", "Gốc → Outro", …

## [0.1.0] - 2026-10-04
### Added
- Khung dự án: lõi `videobulkremixer`, CLI, Web UI local (FastAPI + Alpine.js), đóng gói PyInstaller, CI test + release.
