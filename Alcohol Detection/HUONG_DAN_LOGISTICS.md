# Phân chia hệ thống theo yêu cầu mới

## Web dashboard.html — quản lý

Tab **Nhân viên & Theo dõi** dùng để đăng ký mã nhân viên, họ tên, bộ phận, biển số xe máy cá nhân, UID thẻ và hiệu lực hồ sơ. Có tìm kiếm, chỉnh sửa, xem xe đang trong bãi, lọc lịch sử theo nhân viên/ngày và xuất CSV. Nút **Dùng UID vừa quét** điền UID ESP32 gửi lên Firebase trong vòng 90 giây; không tự ghi hồ sơ khi chỉ quét thẻ.

Mỗi nhân viên có một thẻ và một xe trong hồ sơ hiện hành. Ghi hồ sơ và các chỉ mục qua transaction để chặn trùng UID/biển số và tránh ghi đè phiên bản hồ sơ mới hơn. Không đổi UID/biển số nếu trạng thái Firebase cho biết xe còn trong bãi. Nên thực hiện đổi xe/thẻ khi làn đã ngừng xử lý nhân viên đó; mô hình chưa có khóa giao dịch phân tán giữa web và thiết bị.

## Python dashboard_parking.py — vận hành cổng

Giữ giao diện camera vào/ra, YOLO, PaddleOCR, ảnh xe. Python tra biển số đã đăng ký, gửi yêu cầu đối chiếu có thời hạn và hiển thị nhân viên theo lần quét RFID của ESP32. Không có biểu mẫu đăng ký nhân viên trong Python. Module `employee_registry.py` chỉ đọc hồ sơ và cập nhật phần hiển thị.

## ESP32 — đọc thẻ, đo cảm biến, điều khiển mô hình

Nạp lại `sketch_aug7a/sketch_aug7a.ino` cùng tệp `logistics_firebase.h` trong cùng thư mục. Cài ArduinoJson 6.x/7.x bên cạnh các thư viện đang dùng. Wi-Fi phải có Internet/NTP: yêu cầu camera hết hạn sau 90 giây, thiết bị chưa đồng bộ giờ sẽ từ chối xử lý.

ESP32 gửi UID lên `SuKienRFID`, kiểm tra hồ sơ còn hiệu lực, đúng UID và biển số, trạng thái trong bãi. Lối ra lấy mẫu ADC trong 3 giây, ghi từng kết quả PASS/FAIL/ERROR vào nhật ký theo nhân viên. Không dùng lại giá trị đo lần trước. Ngưỡng thử nghiệm nằm ở `CauHinh/NguongADC`, chỉ được đặt tại tab **Điều khiển từ xa**; thiếu ngưỡng thì không mở lối ra. Đây là ADC thô, không phải mg/L và không phải ngưỡng pháp lý.

Mô hình chưa xác nhận luồng hơi thổi hoặc hiệu chuẩn cảm biến. Bảo vệ cần giám sát phép đo và đối chiếu người cầm thẻ. UID không phải số CCCD và chưa chứng minh danh tính sinh trắc học.

## Cấu trúc Firebase dùng chung

```text
HoSoNhanVien/
  nhanVien/{maNhanVien}/
    maNhanVien, hoTen, boPhan, bienSo, rfid, hoatDong, updatedAt
  theRFID/{UID}: maNhanVien
  bienSo/{bienSoChuanHoa}: maNhanVien
SuKienRFID/{IN|OUT}/
  rfid, huong, eventId, timestamp
XeDangVao/ hoặc XeDangRa/
  bienSo, rfid, maNhanVien, hoTen, requestId, timestamp
XeTrongBai/{UID}: true
BienSoXe/{UID}/
  bienSo, rfid, maNhanVien, hoTen, trangThai, timestamp
NhatKyNhanVien/{eventId}/
  timestamp, maNhanVien, hoTen, rfid, bienSo, huong, loai, lyDo
  adc, nguongADC, requestId (khi có)
CauHinh/NguongADC: ngưỡng thử nghiệm đã xác lập
```

`timestamp` được Firebase gán bằng server timestamp. Nhật ký giữ tên, mã, UID và biển số tại thời điểm phát sinh, không lấy tên mới để viết lại lịch sử cũ. Web đếm từng lần đo, không xóa lần không đạt khi đo lại đạt.

## Chạy và thử nghiệm

1. Mở PowerShell tại `E:\Nam4\DATN\Alcohol Detection`, chạy `python -m http.server 8765 --bind 127.0.0.1`.
2. Mở `http://127.0.0.1:8765/dashboard.html`. Không mở bằng `file://` vì trang có JavaScript module.
3. Chọn **Nhân viên & Theo dõi**, nhập hồ sơ và bấm **Lưu lên Firebase**. Hồ sơ trong bản SQLite mô phỏng không tự được tải lên Firebase; nhập lại hồ sơ cần dùng tại đây.
4. Cài/nạp firmware mới; vào **Điều khiển từ xa** để đặt ngưỡng ADC thử nghiệm phù hợp thiết bị. Các số liệu cũ ở `NguongCon` không được tự chuyển sang ADC.
5. Chạy `dashboard_parking.py` từ thư mục `LicensePlate_Test` bằng môi trường Python hiện có. Quét thẻ đúng làn để hiện hồ sơ nhân viên. ESP32 chờ khoảng 15 giây cho camera nhận đúng biển số; camera nhận trước khi quét cũng được chấp nhận nếu yêu cầu còn hiệu lực. Nếu hết thời gian chờ, chỉnh lại vị trí xe và quét lại thẻ.
6. Thử đúng thẻ/xe, sai thẻ, xe chưa đăng ký, thẻ ngừng hiệu lực, lần đo không đạt và đo lại. Quan sát tab theo dõi cập nhật.

`dashboard.html?demo=1` chỉ xem giao diện, không đăng ký các listener dữ liệu và không ghi Firebase. Không có dữ liệu nhân viên giả tự chèn vào cơ sở dữ liệu thật.

## Giới hạn cần nêu đúng

- Chưa chạy kiểm thử với Firebase thật, camera hoặc ESP32 thật trong lần chỉnh sửa này. Chưa biên dịch sketch do chưa có arduino-cli trong PATH.
- Lượt IN/OUT và trạng thái trong bãi của bản tích hợp này được cập nhật khi chấp nhận lệnh mở cổng, kế thừa cách vận hành mô hình cũ. Chưa có cảm biến xe đi qua, nên không phải bằng chứng xe đã thực sự qua cổng. Nhật ký ghi rõ `GATE_COMMAND_ACCEPTED_NO_PASSAGE_SENSOR`.
- Điều khiển mở cổng khẩn cấp của trang cũ vẫn là đường vận hành riêng, không tạo lượt xe theo nhân viên. Không dùng nó để kiểm thử thống kê lượt bình thường.
- Tổng quan và biểu đồ hiện đọc `NhatKyNhanVien`: đạt/không đạt/lỗi, lịch sử gần nhất và số lần kiểm tra theo nhân viên. Dữ liệu `ViPham` cũ vẫn được giữ trong Firebase nhưng không trộn vào thống kê mới. Biểu đồ theo nhân viên hiển thị tối đa 10 nhân viên có nhiều lần kiểm tra nhất.
- Quyền truy cập Firebase hiện có được giữ nguyên, chưa bổ sung đăng nhập/phân quyền. Không đặt database public chỉ để bỏ lỗi Permission denied. Trước dùng dữ liệu nhân viên thật cần cấu hình tài khoản/quyền phù hợp; không đưa service-account JSON lên web.
- Không có thao tác triển khai đám mây hoặc tự tải hồ sơ thật lên Firebase trong quá trình sửa mã.

## Kiểm tra mã

```powershell
node --test "E:\Nam4\DATN\Alcohol Detection\test-employee-model.mjs"
cd E:\Nam4\DATN\LicensePlate_Test
python -m unittest -v test_employee_gate
```

Bản `Logistics_System` trước đó vẫn là mô phỏng độc lập; hướng tích hợp chính hiện tại là web + Python hiện có + Firebase + sketch gốc đã cập nhật.
