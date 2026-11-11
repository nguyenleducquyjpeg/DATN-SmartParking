# Hệ thống kiểm soát xe nhân viên tại bưu cục logistics

Phạm vi: một bưu cục, xe máy cá nhân của nhân viên giao nhận, một xe và một thẻ đăng ký/nhân viên. Đọc [giải pháp đề tài](GIAI_PHAP_DE_TAI.md) để xem phạm vi, nghiệp vụ, dữ liệu và nội dung trình giáo viên.

## Chạy mô phỏng

Trong PowerShell:

```powershell
cd E:\Nam4\DATN\Logistics_System
python app.py --demo
```

Python có Tkinter và SQLite là đủ; không cần Firebase, camera hay ESP32 để chạy mô phỏng.

1. Tab **Nhân viên & xe**: nhập `NV001`, `Nguyễn Văn An`, `Giao nhận`, `59-X1 123.45`, UID `A1B2C3D4`, rồi lưu.
2. Tab **Kiểm soát vào / ra**: nhập UID trên, biển số trên; chọn `IN`; xác nhận đã đối chiếu nhân viên/xe; bấm bước 1, 3, 4.
3. Chọn `OUT`, nhập lại UID/biển số; xác nhận đối chiếu và bấm bước 1.
4. Xác nhận thiết bị/quy trình đo; ADC mô phỏng `250` với ngưỡng `200`; bấm bước 2. Kết quả không đạt; bước 3 bị từ chối; xe vẫn trong bãi.
5. Xác nhận đối chiếu và tạo phiên OUT mới bằng bước 1. Đặt ADC `100`, xác nhận quy trình, bấm bước 2, 3, 4. Xe ra thành công.
6. Xem nhật ký: một lần không đạt, một lần đạt, một lượt vào và một lượt ra. Lọc `NV001` hoặc ngày; xuất CSV.

Ngưỡng mặc định 200 chỉ dành cho thử luồng chương trình, không có đơn vị mg/L và không phải ngưỡng triển khai thực tế. Biển số minh họa không đại diện cho cá nhân cụ thể.

## Chạy với ESP32

```powershell
python -m pip install -r requirements-hardware.txt
python app.py
```

Nạp `firmware/logistics_gate/logistics_gate.ino` bằng Arduino IDE, chọn đúng board ESP32 và cổng USB. Cần thư viện MFRC522, ESP32Servo, ArduinoJson 6 hoặc 7. Tắt Serial Monitor trước khi kết nối từ ứng dụng. Sketch này dùng cùng các chân RFID/servo/cảm biến của sketch cũ, nhưng truyền dữ liệu qua USB thay cho Firebase; không nạp đồng thời hai sketch.

| Thiết bị | GPIO |
|---|---|
| RFID lối vào SS / RST | 14 / 26 |
| RFID lối ra SS / RST | 5 / 27 |
| SPI dùng chung | Theo SPI mặc định của board ESP32 được chọn |
| Servo vào / ra | 25 / 13 |
| ADC cảm biến / LED | 32 / 4 |

Chọn cổng COM, bấm kết nối, đợi ESP32 khởi động rồi quét thẻ. UID và hướng lấy từ đầu đọc; nhập tay hai trường này không thay được lần quét phần cứng. Nhập/đọc biển số, bảo vệ đối chiếu người cầm thẻ, rồi thực hiện theo các bước trên giao diện. Phiên OUT chỉ nhận số đo trả về từ ESP32; ô ADC mô phỏng không được dùng trong chế độ thiết bị.

Firmware tự đóng servo sau 4 giây. Phản hồi `OPENED` chỉ chứng minh firmware đã xử lý lệnh, không đo được vị trí vật lý. Bước xác nhận xe qua là thao tác của bảo vệ. Đây là firmware cho mô hình bàn, chưa đủ cơ chế an toàn cho barrier thực tế.

## Nhận diện biển số

Nút **Chụp & đọc biển số** dùng OpenCV, Ultralytics YOLO và PaddleOCR theo môi trường của dự án hiện có. Có thể chạy bằng Python trong môi trường đó:

```powershell
E:\Nam4\DATN\LicensePlate_Test\.venv\Scripts\python.exe E:\Nam4\DATN\Logistics_System\app.py --demo
```

Khi dùng chế độ thiết bị, cài `pyserial` vào đúng môi trường Python và bỏ `--demo`. Trọng số ưu tiên `LicensePlate_Test/runs/detect/runs/plate_v1/weights/best.pt`, dự phòng `LicensePlate_Test/best.pt`. Adapter yêu cầu PaddleOCR v3 tương tự mã đang có. Lần đầu khởi tạo OCR có thể cần tải model nếu chưa được cache.

Chỉ chốt khi nhận cùng biển số ba lần liên tiếp. Ảnh được lưu trong `data/snapshots`; đường dẫn gắn vào phiên. Ảnh chụp dùng được trong 60 giây và phải khớp nội dung ô biển số. Nhập/sửa thủ công được ghi là `MANUAL` khi không còn ảnh khớp còn hiệu lực. Trong chế độ mô phỏng, nguồn luôn ghi `DEMO`.

Ảnh là ảnh xe/biển số, không thay thế việc xác minh danh tính người cầm thẻ. Adapter không mở tài khoản Firebase/Supabase và không tải ảnh lên mạng.

## Dữ liệu và lịch sử

- `data/demo.sqlite3`: chỉ mô phỏng; không gửi lệnh tới servo.
- `data/logistics.sqlite3`: chế độ thiết bị; không tự sao chép hồ sơ từ demo.
- Đăng ký hồ sơ thực trong chế độ thiết bị trước khi kiểm tra. Không tự nhập các lượt gửi xe cũ thành hồ sơ nhân viên vì dữ liệu cũ chưa có định danh nhân viên đáng tin cậy.
- Khi đổi tên/xe/thẻ, lịch sử cũ giữ bản chụp hồ sơ tại thời điểm phát sinh.
- Danh sách nhật ký hiển thị 500 dòng gần nhất; tổng hợp và CSV dùng toàn bộ kết quả lọc.
- Thời gian hiển thị theo múi giờ máy tính. Đặt Windows ở UTC+07:00 cho bưu cục Việt Nam.
- Đóng ứng dụng trước khi sao lưu cả thư mục `data`. Không chạy hai phiên ứng dụng trên cùng cơ sở dữ liệu/thiết bị.

## Khác biệt với chương trình cũ

| Chương trình cũ | Bản logistics |
|---|---|
| Ghép UID với biển số lúc vào | Đăng ký nhân viên–UID–biển số trước; kiểm tra khớp |
| Dữ liệu xoay quanh lượt gửi xe | Hồ sơ nhân viên, phiên kiểm tra, nhật ký theo nhân viên |
| UID được ghi vào trường CCCD ở một số log | UID và mã nhân viên có trường riêng |
| Quy đổi ADC tuyến tính rồi hiển thị mg/L | ADC thô, ngưỡng thử nghiệm, chưa tuyên bố hiệu chuẩn |
| Cập nhật trong bãi theo thao tác mở | Chỉ cập nhật khi bảo vệ xác nhận xe qua |
| Firebase/Supabase + ứng dụng cũ | SQLite + USB, chạy độc lập tại một máy |

Các chương trình Python, web, di động và Firebase cũ chưa được chuyển sang schema này. Không chạy chúng để điều khiển cùng mô hình đồng thời. Muốn quản lý từ xa ở giai đoạn sau cần dịch vụ trung tâm có xác thực, phân quyền và đồng bộ giao dịch; không chỉ thêm vài node Firebase rồi coi như đã tích hợp.

## Kiểm thử

```powershell
python -m unittest -v test_core test_app
python -m py_compile core.py app.py camera.py
```

Các bài kiểm thử kiểm tra: trùng hồ sơ, thẻ không hợp lệ, biển số không khớp, trạng thái vào/ra, lần không đạt và đo lại, ADC lỗi, hết hạn/replay, tách mở cổng với xe qua, lưu bản chụp lịch sử, hủy phiên, xuất CSV có bộ lọc.

Đã chạy kiểm thử nghiệp vụ và kiểm tra cú pháp Python trên máy phát triển. Kiểm tra giao diện được thực hiện bằng Tkinter trong chế độ mô phỏng. Chưa xác nhận biên dịch/nạp sketch, chất lượng OCR trên camera, giá trị ADC hoặc hành vi servo trên bộ phần cứng thực tế. Máy hiện không có `arduino-cli` trong PATH.

Ứng dụng chưa có đăng nhập/phân quyền, phát hiện hơi thổi tự động, hiệu chuẩn mg/L, cảm biến xe qua hay đồng bộ đám mây. Đây là các giới hạn thực tế của bản mô hình, cần nêu đúng khi báo cáo.
