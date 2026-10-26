# Spec: Video Bulk Remixer

- Ngày: 2026-10-26 · Trạng thái: Đã duyệt · Người duyệt: người dùng (qua phiếu tool)

## 1. Bối cảnh & vấn đề
Đội UA/marketing cần tạo hàng trăm biến thể video quảng cáo từ video gốc: thay intro/outro, đổi voiceover theo ngôn ngữ, dịch text trên video. Hiện làm tay trên Premiere/CapCut, mỗi video mất 5–10 phút × hàng trăm biến thể = hàng ngày công. Cần tool batch xử lý hàng loạt, người không rành edit video vẫn dùng được.

## 2. Người dùng mục tiêu
- UA, marketing, creative producer — không biết code, không rành ffmpeg
- Windows (chính), macOS (phụ)
- Khối lượng điển hình: 10–50 video gốc × 2–5 source × 2–5 audio × 3–6 ngôn ngữ = 100–7500 video đầu ra
- Giao diện tiếng Việt, trực quan, không cần đọc hướng dẫn

## 3. Luồng chính

### 3.1 Thay đoạn video
1. Chọn thư mục video gốc (hàng loạt)
2. Tích chọn đoạn cần thay (chọn 1, 2, hoặc cả 3 cùng lúc):
   - ☑ Intro — từ đầu đến giây X
   - ☑ Outro — từ giây Y đến hết
   - ☑ Tuỳ chọn — từ giây A đến giây B
3. Với mỗi đoạn, chọn thư mục source thay thế (1 hoặc nhiều file)
4. Các đoạn không được chồng lấn — nếu chồng, báo đỏ, không cho chạy

### 3.2 Thay audio (tuỳ chọn)
1. Không import audio → giữ nguyên audio gốc (audio gốc chạy liền mạch, chỉ thay hình)
2. Import 1 file → thay audio cho tất cả video đầu ra
3. Import nhiều file → mỗi audio ghép với mỗi video, nhân thêm số lượng đầu ra
4. Đặt nhãn ngôn ngữ cho mỗi audio (VI, EN, JP, KR…) — tool tự gợi ý từ tên file

Nguyên tắc: audio là 1 track xuyên suốt, không cắt theo từng đoạn hình. Audio dài hơn video → cắt đuôi. Audio ngắn hơn → pad silence.

### 3.3 Thay text trên video (tuỳ chọn)
1. Preview video, chọn frame có text
2. Kéo bounding box quanh text cũ — nhiều vùng trên 1 video, đặt tên (Tiêu đề, CTA, Subtitle…)
3. Nhập bảng text thay thế theo ngôn ngữ (mỗi cột = 1 bộ video đầu ra)
4. Tuỳ chỉnh: font, cỡ, màu, bold/italic, vị trí, viền/bóng chữ
5. Xoá text cũ bằng inpaint → render text mới lên vùng sạch

### 3.4 Hiệu ứng chuyển cảnh (tuỳ chọn)
1. Timeline trực quan hiện các mối nối giữa các đoạn
2. Kéo thả hiệu ứng từ palette vào mối nối (drop zone)
3. Hiệu ứng: Không (mặc định), Crossfade, Fade to black, Fade to white, Slide, Wipe
4. Chỉnh thời lượng: 0.3s / 0.5s / 1s
5. Preview animation tại mối nối

### 3.5 Naming convention
1. Nhập mẫu tên: `{Appname}_{VID}_{Concept}_{Geo}_{Language}_{Date}_{Ratio}_{STT}`
2. Appname: tên app-viết tắt store, Geo: WW/BR/US…, Language: en/es/pt…, Date: ddmmyy, Ratio: tự detect, STT: tự tăng 001, 002…
3. Preview 5 tên đầu trước khi chạy

### 3.6 Bấm Chạy
Công thức đầu ra: N gốc × M₁ intro × M₂ giữa × M₃ outro × A audio × L ngôn ngữ text

## 4. Yêu cầu chức năng

| ID | Yêu cầu | Ưu tiên |
|----|---------|---------|
| F1 | Thay 1/2/3 đoạn video cùng lúc (Intro, Outro, Tuỳ chọn) với thư mục source riêng | P0 |
| F2 | Source dài hơn đoạn cần thay → cắt hình ảnh cho bằng, audio không cắt theo | P0 |
| F3 | Source ngắn hơn → cảnh báo, cho chọn co đoạn lại hoặc bỏ qua, áp hàng loạt | P0 |
| F4 | Import audio thay thế (1 hoặc nhiều), phân nhãn ngôn ngữ | P0 |
| F5 | Audio là 1 track xuyên suốt, không cắt theo đoạn hình | P0 |
| F6 | Không import audio → giữ nguyên audio gốc | P0 |
| F7 | Chọn vùng text trên video, nhập bảng text đa ngôn ngữ thay thế | P1 |
| F8 | Xoá text cũ bằng inpaint, render text mới lên vùng sạch | P1 |
| F9 | Tuỳ chỉnh font/cỡ/màu/bold/stroke/shadow cho text mới | P1 |
| F10 | Hiệu ứng chuyển cảnh tại mối nối (Crossfade, Fade, Slide, Wipe) | P1 |
| F11 | Kéo thả hiệu ứng vào mối nối trên timeline trực quan | P1 |
| F12 | Preview animation hiệu ứng 2-3s tại mối nối | P1 |
| F13 | Naming convention: Appname_VID_Concept_Geo_Language_Date_Ratio_STT | P0 |
| F14 | Preview tên output trước khi chạy, sửa → cập nhật ngay | P0 |
| F15 | Output phân thư mục theo Geo_Language | P0 |
| F16 | File report.csv chi tiết: tên, source, audio, ngôn ngữ, thời lượng, trạng thái, ghi chú | P0 |
| F17 | Preview video gốc trong tool (player có seek, play/pause, hiện giây) | P0 |
| F18 | Preview video output sau khi xong | P1 |
| F19 | Thanh tiến độ %, nút Dừng | P0 |
| F20 | Kết hợp audio + text cùng ngôn ngữ vào đúng thư mục | P0 |

## 5. Yêu cầu phi chức năng
- Chạy offline, không cần mạng
- ffmpeg đóng kèm trong bin/ (tải bằng script build, không gọi mạng lúc chạy)
- 50 gốc × 5 source = 250 video: chạy đúng, thời gian tuỳ cấu hình máy
- File lỗi không dừng batch — bỏ qua, ghi report
- File gốc chỉ đọc, không bị sửa
- Giao diện tiếng Việt, thiết kế cho người không chuyên
- Mỗi bước đánh số, nút to, tooltip, báo lỗi bằng câu hướng dẫn
- Windows (chính) + macOS

## 6. Tiêu chí chấp nhận

### Thay đoạn video
- [ ] AC1: Cho 3 video gốc + 2 source intro, khi tích Intro + nhập giây 5s + bấm Chạy, thì ra 6 video = 3 gốc × 2 intro, mỗi video có 5s đầu thay bằng source
- [ ] AC2: Cho video gốc + tích cả 3 (Intro 0-5s, Tuỳ chọn 10-15s, Outro 25-30s) + mỗi đoạn 1 source, khi Chạy, thì ra video ghép đúng 3 đoạn thay + 2 đoạn giữ nguyên
- [ ] AC3: Cho 2 đoạn chồng lấn (Intro 0-10s, Tuỳ chọn 5-15s), khi nhập, thì hiện cảnh báo đỏ + nút Chạy bị khoá

### Source dài/ngắn
- [ ] AC4: Cho source intro 8s + đoạn cần thay 5s, khi Chạy, thì hình source bị cắt còn 5s, report ghi "source hình bị cắt từ 8s → 5s"
- [ ] AC5: Cho source intro 3s + đoạn cần thay 5s, khi xử lý, thì hiện cảnh báo + 2 lựa chọn (co đoạn / bỏ qua) + hỏi áp hàng loạt

### Audio
- [ ] AC6: Cho không import audio, khi Chạy, thì video output giữ nguyên audio gốc chạy liền mạch
- [ ] AC7: Cho 2 audio (voice_EN.mp3, voice_VI.mp3), khi Chạy, thì mỗi video gốc ra 2 bản, audio EN vào thư mục EN, audio VI vào thư mục VI
- [ ] AC8: Cho audio 25s + video output 30s, thì 5s cuối im lặng
- [ ] AC9: Cho audio 35s + video output 30s, thì audio bị cắt đuôi còn 30s

### Text
- [ ] AC10: Cho 1 video + 2 vùng text (Tiêu đề, CTA) + 3 ngôn ngữ (VI, EN, JP), khi Chạy, thì ra 3 video, text cũ bị xoá sạch không lộ viền, text mới đúng font/màu
- [ ] AC11: Cho vùng text trên nền tĩnh, khi inpaint, thì vùng lấp nền tự nhiên, không thấy dấu vết text cũ

### Hiệu ứng
- [ ] AC12: Cho kéo thả Crossfade 0.5s vào mối nối Intro→Giữa, khi Chạy, thì video output có hiệu ứng hoà mờ 0.5s tại mối nối
- [ ] AC13: Cho chọn riêng Intro→Giữa = Crossfade, Giữa→Outro = Fade to black, khi Chạy, thì 2 mối nối dùng hiệu ứng khác nhau

### Naming + Output
- [ ] AC14: Cho nhập Appname=MyApp-GP, Concept=Summer, Geo=BR, khi Chạy, thì tên file = MyApp-GP_VID_Summer_BR_pt_261026_9x16_001.mp4, STT tăng đúng
- [ ] AC15: Cho Chạy xong, thì Output/ có thư mục BR_pt/, US_en/… và report.csv đầy đủ cột

### Giao diện
- [ ] AC16: Cho chọn thư mục gốc, khi bấm vào thumbnail, thì mở player preview có seek + hiển thị giây
- [ ] AC17: Cho nhập giây cắt, thì player tự nhảy đến frame đó
- [ ] AC18: Cho file lỗi (codec lạ, file hỏng), khi Chạy, thì bỏ qua file đó, ghi report, tiếp tục batch

## 7. Edge case
- Thư mục gốc rỗng → báo "Chưa có video nào"
- File trong thư mục không phải video (ảnh, txt…) → bỏ qua, ghi report
- Tên file có dấu, khoảng trắng, emoji → chuẩn hoá trong tên output, giữ mapping trong report
- Đường dẫn dài (> 260 ký tự Windows) → dùng \\?\ prefix
- Ổ đầy giữa chừng → dừng, báo rõ "Hết dung lượng ổ …", giữ nguyên file đã xong
- Huỷ giữa chừng (bấm Dừng) → dừng sạch, file đang xử lý bị xoá, file đã xong giữ nguyên
- Input = output directory → không cho chọn, báo lỗi
- Video gốc không có audio track → ghép bình thường, nếu không import audio thì output không có audio
- Source video codec khác gốc (VP9 vs H.264) → re-encode về H.264 AAC
- Nhiều video gốc có resolution khác nhau → xử lý từng video theo resolution của nó, Ratio tự detect

## 8. Kiến trúc

### Module lõi (`videobulkremixer/`)
- `models.py` — dataclass: SegmentConfig, AudioConfig, TextReplacement, TransitionEffect, NamingConfig, JobConfig, JobResult
- `video_cutter.py` — cắt video theo timestamp (ffmpeg subprocess)
- `video_joiner.py` — ghép các đoạn + source thành video output (ffmpeg concat/filter)
- `audio_mixer.py` — thay/ghép audio track, pad silence, cắt đuôi
- `text_replacer.py` — inpaint xoá text (OpenCV), render text mới (Pillow/OpenCV)
- `transition.py` — áp hiệu ứng chuyển cảnh tại mối nối (ffmpeg xfade filter)
- `namer.py` — sinh tên output theo naming convention
- `reporter.py` — tạo report.csv
- `orchestrator.py` — điều phối toàn bộ pipeline: đọc config → tính combo → chạy từng video → ghi report
- `processor.py` — entry point CLI

### Web UI (`web/`)
- Giao diện 4 khu vực: Video gốc / Chọn đoạn + Timeline / Source + Audio + Text / Chạy + Kết quả
- Player preview (video.js hoặc HTML5 video player)
- Timeline kéo thả hiệu ứng (Alpine.js drag-and-drop)
- Bảng nhập text đa ngôn ngữ
- Preview tên output realtime

### Ranh giới
- Lõi (`videobulkremixer/`) không import `web`
- Web gọi lõi qua API (`web/api/`)
- ffmpeg nằm trong `bin/`, gọi qua subprocess

## 9. Ngoài phạm vi
- Không tự dịch text (người dùng nhập sẵn bảng dịch)
- Không upload video lên đâu
- Không chỉnh màu / colour grading
- Không thêm hiệu ứng trong nội dung đoạn (chỉ tại mối nối)
- Không hỗ trợ video > 4K

## 10. Câu hỏi mở
(Không còn.)
