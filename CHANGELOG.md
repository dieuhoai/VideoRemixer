# Nhật ký thay đổi

## [Unreleased]

### Sửa lỗi
- Hiệu ứng chuyển cảnh giờ được áp đúng mối nối; trước đây giao diện gửi sai khoá nên hiệu ứng bị bỏ qua.
- Hiệu ứng chỉ áp cho hình. Tiếng được cắt thẳng tại mối nối, không còn mờ theo.
- Ghép các đoạn có hiệu ứng không còn làm mất tiếng.
- Khi không chọn ngôn ngữ nào, tên file lấy mã ngôn ngữ trong tên video gốc (ví dụ `Clip_01_VI.mp4` → `vi`), không có thì dùng `orig`.
- Thư mục audio không có file hoặc sai đường dẫn sẽ hiện thông báo rõ ràng thay vì trống im lặng.

### Thêm mới
- 14 kiểu chuyển cảnh, gồm thêm Hoà tan, Quét lên/xuống, Quét trái/phải tách riêng, Nở tròn và Phóng to.
- Voice và nhạc nền có hai khu riêng, tick chọn áp dụng từng nguồn.
- Nhạc nền có thể chọn ngôn ngữ (không bắt buộc), ngôn ngữ này chỉ dùng để ghép vào tên file.
- Thanh âm lượng 0–200% cho nhạc nền, voice và audio gốc.
- Nhận thêm các định dạng audio opus, wma, aif và aiff.
- Nút “Xem thử 3 giây” trong mục hiệu ứng: dựng đoạn 3 giây thật từ video đang xem, nối bằng đúng hiệu ứng đã chọn, có tiếng.
