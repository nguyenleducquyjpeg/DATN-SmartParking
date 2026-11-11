# Trạm cấp thẻ nhân viên — ESP32 + RC522

Đây là sketch cho **ESP32 bổ sung tại bàn cấp thẻ**, không phải ESP32 điều khiển cổng. Trạm đọc UID, nhận yêu cầu từ web, ghi mã nhân viên và biển số vào thẻ, rồi đọc lại toàn bộ dữ liệu để xác nhận. Thẻ phải là **MIFARE Classic 1K hoặc 4K**, với khóa A mặc định `FF FF FF FF FF FF` cho sector 1 và 2.

## 1. Đấu dây

Bảng dưới dành cho ESP32 DevKit/WROOM dùng GPIO như cấu hình mặc định:

| RC522 | ESP32 cấp thẻ |
|---|---|
| 3.3V | 3V3 |
| GND | GND |
| SDA / SS | GPIO 5 |
| SCK | GPIO 18 |
| MOSI | GPIO 23 |
| MISO | GPIO 19 |
| RST | GPIO 27 |
| IRQ | Không nối |

Cấp RC522 bằng 3.3V; SDA trên module này là chân chọn SPI, không nối theo sơ đồ I2C. ESP32 nhận nguồn qua USB. Nếu dùng biến thể ESP32 khác, kiểm tra và chỉnh các chân trong cấu hình.

## 2. Cấu hình và nạp

1. Mở `card_writer/card_writer.ino` trong Arduino IDE.
2. Sao chép `station_config.example.h` thành `station_config.h` trong cùng thư mục. Điền `WIFI_SSID` và `WIFI_PASSWORD`. File riêng này đã được loại khỏi Git.
3. Giữ `STATION_ID = "CAP_THE_01"` để khớp web. URL Firebase đã trỏ tới database của dự án.
4. Cài **MFRC522** và **ArduinoJson 6.21.5**; chọn board **ESP32 Dev Module** và đúng cổng USB của ESP32 cấp thẻ.
5. Nạp chương trình, mở Serial Monitor 115200 nếu cần kiểm tra. Trạm cần Wi-Fi và đồng bộ thời gian NTP để kiểm tra chứng chỉ HTTPS và hạn yêu cầu.

Đã kèm `firebase_roots.h` chứa CA gốc công khai Google Trust Services. Firmware xác thực chứng chỉ HTTPS, không dùng `setInsecure()`.

`DATABASE_AUTH_TOKEN` để trống theo cấu hình mẫu. Nếu Firebase Rules yêu cầu xác thực, cần cấp token phù hợp với quyền của trạm. Mã này chưa có luồng tự đăng nhập/làm mới token; token hết hạn sẽ làm trạm mất quyền truy cập. Không nới database thành public để bỏ lỗi và không chép khóa service-account lên ESP32/web.

## 3. Cách sử dụng trên web

Mở `Alcohol Detection/dashboard.html` qua máy chủ HTTP như trước. Vào **Nhân viên & Theo dõi**, kéo tới **Cấp & ghi thẻ nhân viên**.

### Khi chưa có hồ sơ

1. Đặt thẻ lên RC522 của **trạm cấp thẻ**. Web hiển thị UID và loại thẻ.
2. Bấm **Dùng UID trạm cấp thẻ để đăng ký**; UID được điền vào biểu mẫu nhân viên phía trên.
3. Nhập mã nhân viên, tên, bộ phận, biển số rồi lưu hồ sơ.
4. Quay lại mục cấp thẻ, chọn nhân viên vừa lưu.
5. Giữ đúng thẻ trên RC522 và bấm **Ghi mã nhân viên & biển số vào thẻ**.
6. Chỉ giao thẻ sau khi web báo **Đã ghi và kiểm tra thành công**.

### Khi đã có hồ sơ

Chọn nhân viên đã lưu, đặt đúng thẻ có UID đã đăng ký lên trạm, rồi bấm ghi. Dữ liệu nhập nhưng chưa lưu ở biểu mẫu không được dùng để ghi thẻ.

Một RC522 thực hiện cả ghi và đọc lại. Không cần thêm đầu đọc để kiểm tra. Trạm cấp thẻ gửi UID vào đường dữ liệu riêng; không tạo lần quét hoặc mở cổng vào/ra.

## 4. Dữ liệu ghi trên thẻ

- Dùng đúng sáu **block dữ liệu**: `4, 5, 6, 8, 9, 10`, tổng 96 byte.
- Không ghi block 0, UID, sector trailer 7/11 hoặc khóa truy cập.
- Định dạng `LGS1`: phiên bản, độ dài, mã nhân viên tối đa 40 ký tự ASCII, biển số chuẩn hóa tối đa 10 ký tự và CRC32.
- Không ghi họ tên, bộ phận hay kết quả kiểm tra cồn lên thẻ; các dữ liệu này vẫn ở Firebase.
- Trước khi ghi, kiểm tra vùng đó đang trống (byte 0/FF) hoặc có dấu định dạng `LGS1`/`LGP1` của hệ thống. Nếu thấy dữ liệu khác thì từ chối, không tự xóa.
- Ghi dấu `LGP1` trước, ghi các block còn lại, rồi ghi header `LGS1` cuối cùng. Nếu rút thẻ giữa chừng, có thể ghi lại bằng yêu cầu mới; chỉ kết quả đọc lại khớp đủ 96 byte mới được công nhận.
- CRC chỉ kiểm tra lỗi dữ liệu, không phải chữ ký chống giả mạo. Việc ghi thẻ không biến UID/thẻ Classic thành cơ chế chống sao chép.

Cổng hiện tại vẫn kiểm tra UID và hồ sơ Firebase. Nó **chưa đọc payload `LGS1`** làm điều kiện mở cổng. Chức năng mới bổ sung việc cấp/ghi thẻ; không tự đổi quy tắc ra/vào.

## 5. Firebase và xử lý lỗi

```text
TramCapThe/CAP_THE_01/
  heartbeat: { timestamp, bootId, firmware }
  scan: { rfid, cardType, timestamp }
  job: {
    id, status, maNhanVien, hoTen, rfid, bienSo, profileVersion,
    createdAt, expiresAt, bootId, updatedAt,
    error, verified, bytesVerified, format, completedAt
  }
  history/{jobId}: kết quả yêu cầu đã kết thúc
```

Trạng thái: `PENDING → WRITING → VERIFYING → SUCCESS`; lỗi kết thúc bằng `ERROR`, quá hạn chờ bằng `EXPIRED`.

- Web yêu cầu tín hiệu trạm trong 30 giây và UID quét trong 60 giây. Yêu cầu chờ thẻ hết hạn sau 120 giây.
- Web dùng transaction để chỉ có một yêu cầu đang hoạt động. Firmware nhận việc bằng ETag/If-Match, tránh nhận lại yêu cầu đã bị thay thế.
- Kiểm tra UID thực tế lần nữa ngay trước khi ghi. Sai thẻ, loại thẻ không hỗ trợ hoặc hồ sơ thay đổi thì từ chối.
- Kiểm tra hồ sơ trước và sau phép ghi. Nếu hồ sơ thay đổi/mất mạng ở cuối quá trình, thẻ có thể đã được ghi nhưng yêu cầu vẫn báo lỗi; phải kiểm tra/gửi yêu cầu mới, không coi là đã cấp thành công.
- Nếu mất mạng sau khi ghi, trạm giữ kết quả trong RAM và thử gửi lại, **không lặp lại thao tác ghi**. Nếu mất nguồn giữa phiên, khi khởi động lại trạm báo `STATION_RESTARTED` và cần yêu cầu mới.
- Sau khi nhận việc, chỉ trạm đó được cập nhật kết quả. Không xóa/sửa thủ công node job khi đang ghi.

Phần quyền Firebase hiện tại chưa được triển khai/chỉnh sửa tự động. Trạm cần đọc hồ sơ nhân viên và đọc/ghi đường `TramCapThe/CAP_THE_01`; web quản lý cần quyền tạo yêu cầu. Dữ liệu phát sinh sẽ chỉ được gửi khi bạn chạy thiết bị/web thật.

## 6. Kiểm tra đã thực hiện

- 19 kiểm thử Node cho dữ liệu nhân viên và yêu cầu cấp thẻ: đúng UID, thời hạn, loại thẻ, phiên ghi đang bận, phiên hết hạn và hồ sơ ngừng hiệu lực.
- Biên dịch cho **esp32:esp32:esp32**, ESP32 core **2.0.17**, ArduinoJson **6.21.5**, thư viện MFRC522 có sẵn trên máy.
- Chưa nạp thiết bị hoặc ghi thẻ thật trong quá trình phát triển. Cần thử một thẻ trống trước khi cấp thẻ cho nhân viên.

Tài liệu API tham khảo: [ví dụ ReadAndWrite của MFRC522](https://github.com/miguelbalboa/rfid/blob/master/examples/ReadAndWrite/ReadAndWrite.ino). Chứng chỉ công khai: [Google Trust Services](https://pki.goog/repository/).

## Thử khi chưa có phần cứng

Mở `http://127.0.0.1:8765/dashboard.html?simulate=1` khi máy chủ web cục bộ đang chạy.
Bấm **Quét thẻ giả**, lấy UID vào form đăng ký, nhập và lưu hồ sơ, rồi chọn hồ sơ trong mục **Cấp & ghi thẻ** và bấm ghi.
Có thể rút thẻ giả giữa phiên hoặc bật lỗi đọc lại để thử thông báo lỗi.
Mô phỏng dùng bộ nhớ riêng của trang; tải lại sẽ xóa hồ sơ/thẻ thử. Không ghi Firebase hoặc gửi lệnh tới ESP32.
Đây là mô phỏng luồng phần mềm, không chạy firmware hay kiểm chứng giao tiếp điện/SPI, bộ nhớ vật lý và khóa của thẻ thật.

## Thu hồi, xóa và cấp lại thẻ

1. Trong danh sách nhân viên, chọn **Thu hồi thẻ** và xác nhận đúng nhân viên/UID. Hệ thống ngừng hiệu lực hồ sơ, gỡ liên kết UID, giữ hồ sơ, biển số và toàn bộ nhật ký. Xe còn tại bưu cục phải hoàn tất lượt ra trước khi thu hồi.
2. Đặt thẻ đã thu hồi lên trạm, chọn **Xóa dữ liệu trên thẻ đã thu hồi** và xác nhận. Không cần chọn nhân viên trong danh sách ghi thẻ. Chỉ chấp nhận thẻ đã thu hồi và chưa gán lại.
3. Chờ kết quả **Đã xóa và đọc lại xác nhận**. Trạm đặt 96 byte trong các block 4, 5, 6, 8, 9, 10 về 0 và đọc lại so sánh; không thay UID, khóa, sector trailer hoặc dữ liệu ngoài vùng của hệ thống.
4. Đăng ký hồ sơ nhân viên mới bằng UID này, rồi ghi mã nhân viên và biển số mới. Hồ sơ cũ vẫn còn để tra cứu.

Nếu mất thẻ, chỉ thu hồi trên hệ thống; không thể xóa dữ liệu vật lý từ xa. Sau khi thu hồi, lịch sử thu hồi được lưu trong `HoSoNhanVien/lichSuThuHoi`, trạng thái thẻ trong `HoSoNhanVien/theThuHoi`.

Phải nạp firmware **card-writer-2** để dùng xóa thẻ thật. Phiên xóa giữ khóa UID trong hồ sơ để chặn cấp lại giữa chừng; khóa được giải phóng khi có kết quả cuối. Nếu trình duyệt ngắt trước khi gửi lệnh, sau 150 giây hãy bấm xóa lại để phục hồi yêu cầu chưa gửi. Nếu trạm ngắt giữa phiên, kết nối/khởi động lại trạm để nhận kết quả lỗi trước khi thử lại. Lỗi sau khi ghi có thể để lại dữ liệu đã xóa một phần hoặc toàn bộ; chỉ xem thành công khi đọc lại đủ 96 byte.

Cả hai chức năng hỗ trợ chế độ mô phỏng. Đã chạy đạt 30 kiểm thử JavaScript và biên dịch ESP32 core 2.0.17. Chưa thử trên thẻ vật lý; kiểm tra toàn bộ giao diện qua trình duyệt tự động bị gián đoạn tại hộp thoại xác nhận, sau đó đã thay bằng hộp thoại HTML trong trang.
