# Dashboard vận hành cổng nhân viên

## Chạy

Xem giao diện mà không kết nối Firebase, camera hoặc servo:

```powershell
python E:\Nam4\DATN\LicensePlate_Test\dashboard_parking.py --demo
```

Bấm **Nạp tình huống minh họa** để thấy hai nhân viên riêng: lối vào đã gửi lệnh mở, lối ra có lần đo không đạt. Đây là dữ liệu tạm trong bộ nhớ, không được lưu lên Firebase.

Chạy thật bằng môi trường Python của dự án:

```powershell
E:\Nam4\DATN\LicensePlate_Test\.venv\Scripts\python.exe E:\Nam4\DATN\LicensePlate_Test\dashboard_parking.py
```

Chọn đúng index camera vào/ra, mặc định 0 và 1. Không chọn cùng một camera cho hai làn. Lần mở đầu tiên cần thời gian tải YOLO/PaddleOCR; tác vụ chạy ở nền. Adapter hiện dùng CPU để không bắt buộc máy có CUDA. Trọng số và khóa Firebase được tìm theo thư mục tệp Python, không phụ thuộc thư mục đang mở terminal.

## Thay đổi giao diện

- Bỏ phí giữ xe và khung chủ xe chung.
- Hai khung riêng cho lối vào và lối ra: nhân viên, bộ phận, hiệu lực, UID, giờ quét, xe đăng ký, biển số đối chiếu và kết quả khớp.
- Lối ra hiển thị ADC, ngưỡng và kết quả đo. Không quy đổi thành mg/L.
- Trạng thái chờ camera, đang đo, đạt/không đạt/lỗi, từ chối, đã gửi lệnh mở/đóng được lấy từ ESP32.
- Luồng camera/nhận diện và luồng Firebase chạy nền; cập nhật Tk chỉ thực hiện trên luồng giao diện.
- Cột thông tin cuộn được trên màn hình thấp. Nhập biển số thủ công vẫn hỗ trợ và được ghi `nguon=MANUAL` trong yêu cầu đối chiếu.
- Ảnh camera ra lưu thành tệp riêng trong `parking_snapshots/exit`; ảnh vào tiếp tục lưu theo biển số để đối chiếu.

## Cần nạp lại firmware

Nạp lại `sketch_aug7a/sketch_aug7a.ino` cùng `logistics_firebase.h` đã cập nhật. Firmware mới ghi:

```text
TrangThaiCong/{IN|OUT}/
  scanId, rfid, huong, sequence, trangThai, lyDo,
  timestamp, requestId, adc, nguongADC
```

`scanId` trùng `SuKienRFID/{IN|OUT}/eventId`. Dashboard chỉ nhận trạng thái đúng lần quét, đúng UID và có sequence mới hơn. Quét lượt mới xóa kết quả cũ; phản hồi đến muộn không được hiển thị cho người tiếp theo. Giá trị đo được giữ cả trong trạng thái mở/đóng để không mất số đo khi dashboard bỏ lỡ trạng thái PASS ngắn.

Firmware cũ chưa có node này vẫn có thể gửi UID nhưng màn hình không thể biết chính xác tiến trình đo/mở. Sau 90 giây không có cập nhật cho một trạng thái đang xử lý, giao diện báo chưa nhận được trạng thái tiếp theo, không tự kết luận mở cổng thành công. Đây là cảnh báo trên màn hình, không phải lệnh hủy từ xa.

## Giới hạn và kiểm chứng

Màn hình hiển thị **lệnh ESP32 đã thực hiện**, chưa xác minh servo thực sự chuyển động hoặc xe thực sự đi qua. Trạng thái trong bãi vẫn theo cách cập nhật của firmware hiện tại. Chưa thêm nút xác nhận xe qua vì cần thay đổi đồng bộ quy trình cập nhật tại thiết bị; tránh ghi nhận hai lần hoặc hiển thị giả một bước đã hoàn tất.

Hai làn hiển thị độc lập, nhưng firmware hiện tại vẫn xử lý lần lượt trên một ESP32; trong lúc chờ camera/đo cồn, làn còn lại có thể phải chờ. Chưa tuyên bố phần cứng xử lý đồng thời.

Đã kiểm tra cú pháp Python, kiểm thử ghép trạng thái đúng phiên/UID/thứ tự, và chạy giao diện mô phỏng. Chưa biên dịch/nạp sketch hoặc thử trực tiếp camera–Firebase–cảm biến–servo trong lần thay đổi này.

```powershell
cd E:\Nam4\DATN\LicensePlate_Test
python -m unittest -v test_employee_gate test_gate_session
```
