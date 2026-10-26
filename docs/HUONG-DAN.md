# Hướng dẫn dùng Video Bulk Remixer

Tool này tạo nhiều biến thể video quảng cáo từ một video gốc. Làm theo 4 khu vực trên màn hình, từ trái sang phải.

## Trước khi bắt đầu
- Chuẩn bị: video gốc (1 thư mục), các clip thay thế (intro/outro/đoạn giữa — mỗi loại 1 thư mục), file audio (nếu có), bảng text dịch (nếu có).
- Tool chạy hoàn toàn trên máy bạn, không upload gì lên mạng.

## ① Video gốc
Bấm **Chọn thư mục…** và chọn thư mục chứa video gốc. Bấm vào một video để xem trước. Dùng thanh tua và ô "Lấy giây này" để tìm đúng thời điểm cắt.

## ② Chọn đoạn cần thay
Tích **Intro** (từ đầu đến giây X), **Tuỳ chọn** (từ giây A đến B) và/hoặc **Outro** (từ giây Y đến hết).
- Các đoạn không được đè lên nhau. Nếu đè, ô sẽ báo đỏ và nút Chạy bị khoá.
- Muốn thêm hiệu ứng chuyển cảnh: kéo một hiệu ứng từ bảng bên dưới vào ● giữa các đoạn. Bấm vào ● để chọn bằng bàn phím. Bấm ✕ để bỏ.

## ③ Source, audio, text
- **Source thay**: chọn thư mục clip thay thế cho từng đoạn bạn đã tích.
- **Audio**: chọn thư mục audio, rồi chọn ngôn ngữ cho từng file (VI, EN…). Không chọn gì = giữ audio gốc.
- **Text**: bấm **Lấy khung hình**, kéo chuột quanh chữ cũ trên hình, rồi nhập chữ mới cho từng ngôn ngữ. Có thể chỉnh font, cỡ, màu, đậm, bóng, viền.

## ④ Đặt tên, chạy, kết quả
1. Điền tên app, concept, geo, ngày. Khung "Xem trước tên file" cho thấy tên sẽ được đặt.
2. Chọn **thư mục Output**.
3. Xem dòng "Dự kiến: … video". Bấm **Chạy**.
4. Nếu có clip thay thế ngắn hơn đoạn cần thay, tool sẽ hỏi bạn: co đoạn lại theo clip, hay bỏ qua và giữ đoạn gốc. Chọn một cách rồi bấm Chạy lần nữa.
5. Khi xong, bấm **Xem** để xem từng video, hoặc **Mở thư mục kết quả**.

Kết quả nằm trong thư mục Output, chia theo ngôn ngữ (ví dụ `BR_vi/`, `BR_en/`), kèm `report.csv`. Dòng nào lỗi sẽ ghi lý do; các file khác vẫn chạy tiếp.

## Hay gặp
- **"Chưa có video nào"**: kiểm tra thư mục có file .mp4/.mov không.
- **"không đọc được" một file**: file bị hỏng hoặc codec lạ. Bỏ qua file đó, các file khác vẫn xong.
- **Hết dung lượng ổ đĩa**: tool dừng và giữ lại các file đã xong. Giải phóng dung lượng rồi chạy lại.
- **Muốn dừng giữa chừng**: bấm **Dừng**. File đang xử lý sẽ bị xoá, file đã xong được giữ.
- **Text cũ còn vệt mờ**: vùng nền phức tạp hoặc đang chuyển cảnh nhanh. Thử khoanh rộng hơn một chút, hoặc chọn thời điểm có nền phẳng hơn.
