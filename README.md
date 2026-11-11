# DATN — Quản lý định danh tài xế và kiểm soát nồng độ cồn bằng RFID

Hệ thống tại một bưu cục logistics: quản lý hồ sơ tài xế và xe máy cá nhân, đối chiếu RFID/biển số, kiểm tra nồng độ cồn trước khi cho xe ra và theo dõi lịch sử.

## Thành phần

- `Alcohol Detection/`: dashboard web, đăng ký nhân viên, theo dõi và mô phỏng cấp/thu hồi/xóa thẻ.
- `LicensePlate_Test/`: giao diện Python tại cổng, nhận diện biển số, bộ dữ liệu và mô hình.
- `sketch_aug7a/`: firmware ESP32 điều khiển mô hình cổng.
- `CardWriter_ESP32/`: firmware ESP32 + RC522 riêng để cấp, ghi, đọc lại và xóa thẻ.
- `Logistics_System/`: mô hình phần mềm và tài liệu giải pháp.
- `KhoaXeApp/`: ứng dụng React Native.
- `BaoCao_DeCuong/` và tài liệu ở thư mục gốc: báo cáo, thuyết trình và bảng tính của đề tài.

## Chạy dashboard

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory "Alcohol Detection"
```

Mở `http://127.0.0.1:8765/dashboard.html`; dùng `?simulate=1` để thử cấp/thu hồi/xóa thẻ với bộ nhớ riêng, không ghi Firebase.

## Cấu hình riêng trên máy

- ESP32 cổng: sao chép `sketch_aug7a/wifi_config.example.h` thành `wifi_config.h` và nhập Wi-Fi.
- ESP32 cấp thẻ: làm theo [hướng dẫn](CardWriter_ESP32/README.md), tạo `station_config.h` từ file mẫu.
- Python: cung cấp khóa quản trị Firebase riêng tại `LicensePlate_Test/firebase_key.json`; không commit khóa này.
- Cài thư viện theo hướng dẫn từng thành phần; thư viện cài sẵn và kết quả build không nằm trong repo.

Repo công khai không bao gồm khóa quản trị, mật khẩu Wi-Fi, cấu hình riêng, dữ liệu vận hành cục bộ, ảnh chụp sự kiện, cache, thư viện đã cài hoặc các bản nén trùng lặp. Các file này vẫn được giữ tại máy gốc. Cấu hình Firebase dành cho web không thay thế quy tắc phân quyền Firebase.

Số đo ADC của mô hình chưa được hiệu chuẩn sang mg/L; kiểm thử phần mềm không thay thế kiểm tra phần cứng thực tế.
