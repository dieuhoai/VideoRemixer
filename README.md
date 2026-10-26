# 🎬 Video Bulk Remixer

Tạo hàng trăm biến thể video quảng cáo từ một video gốc: thay đoạn đầu / đoạn cuối / đoạn giữa, thay audio theo ngôn ngữ, thay text trên video, thêm hiệu ứng chuyển cảnh. Chạy offline trên máy của bạn, giao diện tiếng Việt.

Hướng dẫn cho người dùng không biết kỹ thuật: xem [docs/HUONG-DAN.md](docs/HUONG-DAN.md).

## Chạy thử (Windows / macOS)

1. Cài [Python 3.12+](https://www.python.org/downloads/) (Windows: nhớ tích **Add Python to PATH**).
2. Đặt ffmpeg vào thư mục `bin/` (xem bên dưới).
3. Windows: bấm đúp `RUN-Windows.bat`. macOS: bấm đúp `RUN-Mac.command` (nếu báo "không xác minh nhà phát triển": System Settings → Privacy & Security → Open Anyway).
4. Lần đầu sẽ cài thư viện (~1–2 phút). Trình duyệt tự mở giao diện.

### ffmpeg
Tool cần `ffmpeg` và `ffprobe` trong thư mục `bin/`:
- Tự động (Windows/macOS): `python scripts/fetch_ffmpeg.py`
- Thủ công: tải bản static, copy `ffmpeg` + `ffprobe` (hoặc `.exe`) vào `bin/`.
- Linux: `sudo apt install ffmpeg` (tool sẽ dùng ffmpeg hệ thống khi không có `bin/`).

## Giao diện — 4 khu vực

1. **Video gốc** — chọn thư mục, bấm video để xem trước, tua được.
2. **Chọn đoạn + timeline** — tích Intro / Tuỳ chọn / Outro, kéo hiệu ứng (Crossfade, Fade to black/white, Slide, Wipe) vào mối nối.
3. **Source · Audio · Text** — thư mục source thay thế cho từng đoạn; audio theo ngôn ngữ; vẽ vùng text trên khung hình và nhập text từng ngôn ngữ.
4. **Đặt tên · chạy · kết quả** — naming convention `{Appname}_{VID}_{Concept}_{Geo}_{Language}_{Date}_{Ratio}_{STT}`, xem trước tên, tiến độ, Dừng, bảng kết quả.

Output: thư mục `Geo_Language/` cho từng bộ, kèm `report.csv` (tên file, source đã dùng, audio, ngôn ngữ, thời lượng, hiệu ứng, trạng thái, ghi chú).

## Dòng lệnh (CLI)

```bash
python -m videobulkremixer run <thư_mục_gốc> <thư_mục_output> \
  --intro 5:<thư_mục_source_intro> --outro 25:<thư_mục_source_outro> \
  --audio voice_EN.mp3 --audio voice_VI.mp3 \
  --appname MyApp-GP --concept SummerSale --geo BR --transition crossfade
```

## Phát triển

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"   # Windows (macOS/Linux: .venv/bin/...)
.venv/Scripts/python -m pytest -q -m "not ui"                    # test lõi + API (cần ffmpeg)
.venv/Scripts/python -m pytest -q -m ui                          # test giao diện (Playwright)
.venv/Scripts/ruff check .                                       # lint
.venv/Scripts/python -m web.server --no-browser --port 8765 --token devtoken   # chạy UI dev
```

Kiến trúc: lõi `videobulkremixer/` (không import `web`), web/API `web/` gọi lõi. Xem `docs/specs/` và `docs/plans/`.

## Giới hạn đã biết
- Xoá text bằng inpaint (OpenCV) đạt tốt trên nền phẳng; nền rất phức tạp hoặc chuyển cảnh nhanh có thể còn vệt mờ.
- Text CJK (Nhật/Hàn/Trung) cần font CJK trên máy; app ghi chú nếu không tìm thấy.
- Không tự dịch text — bảng dịch do người dùng nhập.
