# Giải pháp đề tài theo phạm vi một bưu cục logistics

## 1. Tên đề tài đề xuất

**Thiết kế và xây dựng mô hình hệ thống quản lý xe máy cá nhân của nhân viên giao nhận tại bưu cục logistics kết hợp RFID, nhận diện biển số và kiểm tra nồng độ cồn khi lấy xe ra.**

Tên ngắn dùng trên giao diện: **Hệ thống kiểm soát xe nhân viên tại bưu cục logistics**.

Bối cảnh là một bưu cục giả định của doanh nghiệp chuyển phát, tham chiếu loại hình hoạt động như J&T Express. Chưa có khảo sát hoặc xác nhận từ doanh nghiệp, vì vậy không ghi rằng hệ thống đã triển khai tại J&T hoặc phản ánh quy trình nội bộ thực tế của J&T.

## 2. Phạm vi cụ thể

- Địa điểm: một bưu cục, có một làn vào và một làn ra; nhân viên bảo vệ trực tại máy quản lý.
- Đối tượng: nhân viên giao nhận và xe máy cá nhân đã đăng ký phục vụ việc đi lại, giao nhận.
- Mỗi nhân viên có đúng một biển số và một UID thẻ đang được đăng ký trong hồ sơ. Biển số và UID không được trùng với hồ sơ khác.
- Khi đổi xe hoặc mất thẻ, quản lý cập nhật hồ sơ hiện tại. Lịch sử giữ lại biển số, UID và tên tại thời điểm phát sinh sự kiện.
- Không đổi xe/thẻ khi xe còn trong bãi. Việc ngừng hiệu lực thẻ không tự xóa trạng thái xe trong bãi.
- Kiểm tra cồn thực hiện cho **mỗi lần lấy xe ra**, kể cả nhiều lần trong một ngày; kết quả trước không thay thế lần kiểm tra mới.
- Phạm vi không bao gồm xe khách, ô tô, xe dùng chung luân chuyển giữa nhiều tài xế, quản lý đơn hàng, tính phí gửi xe, theo dõi GPS hoặc quản lý toàn chuỗi bưu cục.

Giới hạn một xe/nhân viên là quy tắc của mô hình đề tài đã thống nhất, không phải khẳng định quy định của doanh nghiệp ngoài thực tế.

## 3. Mục tiêu và ý nghĩa

Hệ thống trả lời được: nhân viên nào đăng ký xe nào; ai đang có xe trong bãi; nhân viên lấy xe lúc nào; lần kiểm tra cồn tương ứng có kết quả ra sao; vì sao hệ thống từ chối mở cổng. Nhờ liên kết hồ sơ cố định, thống kê theo nhân viên và theo ngày có ý nghĩa quản lý hơn thống kê từng UID không có chủ thể.

Trọng tâm là kiểm soát điều kiện lấy xe ra ở cổng bưu cục. Kết quả “đạt” của mô hình là đạt ngưỡng thử nghiệm đã cấu hình, không phải chứng nhận đủ điều kiện sức khỏe hay kết luận pháp lý về khả năng lái xe.

## 4. Tác nhân và trách nhiệm

| Tác nhân nghiệp vụ | Công việc |
|---|---|
| Quản lý bưu cục | Đăng ký/sửa hồ sơ, đổi thẻ/xe khi phù hợp, ngừng hiệu lực, xem nhật ký và thống kê |
| Bảo vệ | Đối chiếu người cầm thẻ, biển số; giám sát thao tác thổi; xử lý nhận diện không rõ; xác nhận xe qua cổng |
| Nhân viên giao nhận | Sử dụng thẻ cá nhân, đúng xe đăng ký, thực hiện kiểm tra khi lấy xe ra |
| Hệ thống | Đối chiếu dữ liệu, gắn kết quả với phiên, quyết định cho phép mở, lưu sự kiện |

Bản phần mềm hiện tại phục vụ một máy vận hành tin cậy, chưa có đăng nhập và phân quyền theo tài khoản. Bảng trên là phân công nghiệp vụ; không mô tả một cơ chế phân quyền đã được lập trình.

## 5. Thẻ RFID và định danh nhân viên

Thẻ cung cấp UID. Cơ sở dữ liệu ánh xạ **UID → mã nhân viên → hồ sơ và biển số đăng ký**. Giao diện hiển thị thông tin sau khi tra cứu. Không cần lưu trực tiếp họ tên và biển số vào vùng nhớ thẻ: việc thay đổi hồ sơ được thực hiện trong cơ sở dữ liệu.

UID thẻ không phải số CCCD. Thẻ và biển số chỉ kiểm tra được phương tiện có khớp hồ sơ của thẻ; chưa chứng minh người đang cầm thẻ là chủ hồ sơ. Vì vậy mô hình có bước bảo vệ đối chiếu trực tiếp, không tuyên bố đã nhận dạng sinh trắc học hoặc ngăn chặn hoàn toàn hành vi dùng thẻ hộ.

## 6. Quy trình nghiệp vụ

### Đăng ký

Quản lý nhập mã nhân viên, họ tên, bộ phận, UID và biển số xe máy. Hệ thống chuẩn hóa UID/biển số và kiểm tra tính duy nhất trước khi lưu. Hồ sơ mới chưa có xe trong bãi.

### Xe vào

1. Camera nhận diện biển số; trường hợp không rõ, bảo vệ nhập biển số và đối chiếu trực tiếp. Nguồn nhập được lưu.
2. Nhân viên quét thẻ tại đầu đọc lối vào.
3. Bảo vệ đối chiếu nhân viên và xe với hồ sơ.
4. Hệ thống kiểm tra thẻ đã đăng ký, hồ sơ còn hiệu lực, biển số khớp và xe chưa ở trong bãi.
5. Nếu hợp lệ, tạo phiên cho phép mở cổng; ESP32 nhận lệnh mở và phản hồi.
6. Bảo vệ xác nhận xe thực sự qua cổng; lúc này mới cập nhật trạng thái trong bãi và ghi lượt vào.

### Xe ra và kiểm tra cồn

1. Nhận diện/nhập biển số, quét thẻ lối ra và đối chiếu người cầm thẻ.
2. Kiểm tra hồ sơ còn hiệu lực, biển số đúng xe đăng ký, xe đang ở trong bãi.
3. Tạo phiên kiểm tra riêng gắn mã nhân viên, UID, biển số, hướng ra, thời điểm, nguồn biển số và ngưỡng áp dụng.
4. Bảo vệ xác nhận thiết bị sẵn sàng và giám sát nhân viên thực hiện phép đo. ESP32 lấy mẫu, trả kết quả kèm mã phiên.
5. Không đạt hoặc lỗi: lưu kết quả, không cho mở cổng, xe vẫn trong bãi. Bảo vệ xử lý theo quy trình bưu cục; không tự động xóa hồ sơ hoặc kết luận kỷ luật.
6. Đạt: lưu kết quả và cấp quyền mở ngắn hạn. Bảo vệ gửi lệnh mở, chờ thiết bị phản hồi, rồi xác nhận xe đã qua.
7. Lần kiểm tra lại phải tạo phiên mới; kết quả lần không đạt vẫn được giữ trong lịch sử.

### Tình huống bất thường

| Tình huống | Cách xử lý |
|---|---|
| Thẻ chưa đăng ký, bị ngừng hiệu lực | Từ chối, ghi nhật ký |
| Đúng thẻ nhưng sai biển số | Từ chối, ghi cả biển số đọc được trong lý do |
| Xe đang trong bãi nhưng yêu cầu vào lần nữa | Từ chối lượt vào trùng |
| Xe chưa vào nhưng yêu cầu ra | Từ chối |
| Hết hạn phiên, dùng lại kết quả cũ | Yêu cầu quét và kiểm tra lại |
| ADC lỗi, ngoài miền, thiết bị trả dữ liệu không hợp lệ | Lưu lỗi, không cho phép mở |
| Chưa có phản hồi mở cổng | Không cho ghi nhận xe qua |
| Cổng đã mở nhưng xe chưa đi qua | Không tự thay đổi trạng thái trong bãi |
| Ngắt kết nối máy tính | Không có lệnh mở mới; firmware tự đóng mô hình sau thời gian mở |
| Khởi động lại ứng dụng | Hủy các quyền đang chờ; giữ lịch sử và trạng thái xe đã xác nhận |

## 7. Kiến trúc bản đã triển khai

```text
Camera → YOLO + PaddleOCR → biển số + ảnh tại máy
                                      ↓
RFID vào/ra → ESP32 ← USB Serial → Ứng dụng Python/Tkinter
Cảm biến ADC → ESP32                    ↕
Servo mô hình ← ESP32                 SQLite
                                hồ sơ / phiên / sự kiện
```

Ứng dụng mới được tách thành `Logistics_System` để giữ nguyên chương trình và dữ liệu Firebase/Supabase cũ. Nó dùng SQLite cục bộ làm nguồn dữ liệu chính, truyền JSON qua USB giữa PC và ESP32. Đây là bản độc lập chạy được nghiệp vụ tại một bưu cục, không phải bản nâng cấp đã đồng bộ với ứng dụng di động cũ.

Tái sử dụng mô hình YOLO trong `LicensePlate_Test` và cách đọc PaddleOCR v3 từ chương trình hiện có. Không tự chạy chương trình cũ vì tệp đó khởi tạo Firebase/camera/mô hình ngay khi import.

## 8. Mô hình dữ liệu

| Bảng | Dữ liệu chính | Ý nghĩa |
|---|---|---|
| `employees` | id, name, department, plate UNIQUE, uid UNIQUE, active, inside | Hồ sơ hiện hành và trạng thái xe |
| `sessions` | id, employee_id, name, plate, uid, direction, state, created, expires, threshold, adc, source, evidence, gate_ack | Bản chụp hồ sơ và kết quả của một phiên đối chiếu/đo |
| `events` | at, employee_id, name, plate, uid, session_id, kind, detail | Nhật ký thay đổi hồ sơ, kết quả đo, từ chối và xe qua cổng |

Quan hệ: một nhân viên có nhiều phiên; một phiên có nhiều sự kiện. Một phiên ra nhận tối đa một kết quả đo. Phiên kiểm tra ban đầu có thời hạn 90 giây, quyền mở sau kết quả đạt có thời hạn 30 giây. Một làn chỉ có một phiên chờ đang hiệu lực; phiên mới hủy quyền cũ.

Các trạng thái: `WAIT_TEST`, `AUTHORIZED`, `FAIL`, `ERROR`, `EXPIRED`, `CANCELLED`, `COMPLETED`. Kết quả đo đạt/không đạt/lỗi lưu ở sự kiện `TEST_PASS`, `TEST_FAIL`, `TEST_ERROR`, nên vẫn truy xuất được sau khi trạng thái phiên đổi sang hoàn tất.

## 9. Thống kê phục vụ quản lý

- Tổng nhân viên đăng ký và số xe đang trong bãi.
- Lượt vào, lượt ra theo ngày và nhân viên.
- Số lần kiểm tra đạt, không đạt, lỗi; một lần đo lại được tính là một lần kiểm tra mới.
- Tra cứu mã nhân viên, tên hoặc biển số; lọc ngày; xuất CSV theo bộ lọc.
- Xem thời điểm, UID, mã phiên, ngưỡng và ADC trong dữ liệu nhật ký/phiên.
- Số lần không đạt khác với số nhân viên có kết quả không đạt; không dùng hai đại lượng này thay thế nhau.

Trong giao diện, lọc mã nhân viên để xem tổng hợp riêng nhân viên đó; lọc ngày để xem số liệu trong ngày. Danh sách hiển thị tối đa 500 sự kiện mới nhất, nhưng tổng hợp và CSV lấy toàn bộ dữ liệu phù hợp bộ lọc.

## 10. Giới hạn phép đo và mô hình phần cứng

Trong chương trình cũ, giá trị `analogRead` được ánh xạ tuyến tính 0–4095 sang 0–1000 rồi gắn nhãn mg/L. Phép biến đổi số này chưa chứa mô hình hiệu chuẩn, nên bản mới giữ đơn vị **ADC thô**. Ngưỡng 200 chỉ là giá trị mặc định để thử luồng chương trình, không phải ngưỡng tiêu chuẩn hay giá trị hiệu chuẩn.

Phần firmware mới lấy mẫu trong 3 giây, tính trung bình, đánh dấu lỗi khi có mẫu chạm biên ADC hoặc không đủ mẫu. Kiểm tra này chưa phát hiện được mọi lỗi cảm biến, chưa xác nhận lưu lượng hơi thổi và chưa tự phát hiện hành vi không thổi. Bước giám sát của bảo vệ là bắt buộc trong mô hình hiện tại. Cần đặc tính cảm biến, điều kiện làm nóng, mạch đo và thiết bị tham chiếu để xây dựng/đánh giá hiệu chuẩn trước khi báo cáo kết quả theo mg/L.

Servo mở/đóng theo thời gian chỉ phục vụ mô hình bàn. Chưa có cảm biến xe qua, phản hồi vị trí, chống kẹt hoặc điều khiển barrier công nghiệp. Vì vậy lượt qua do bảo vệ xác nhận; không dùng mô hình này trực tiếp làm barrier ngoài thực tế.

## 11. Đánh giá và nghiệm thu đề tài

| Nhóm | Cách đánh giá |
|---|---|
| Nghiệp vụ hồ sơ | Thử trùng UID, trùng biển, ngừng thẻ, đổi xe khi đang trong bãi |
| Kiểm soát vào/ra | Thẻ đúng/sai, biển đúng/sai, lượt vào trùng, lượt ra khi xe không ở bãi |
| Kiểm tra cồn | Đạt, bằng ngưỡng, vượt ngưỡng, lỗi, hết hạn, đo lại |
| Nhất quán dữ liệu | Mở cổng chưa qua không đổi số xe; xác nhận lặp không tạo hai lượt |
| Nhận diện | Chuẩn bị tập ảnh xe máy của phạm vi thử nghiệm; báo cáo tỉ lệ đúng toàn bộ chuỗi biển số và thời gian xử lý |
| Cảm biến | Báo cáo độ lặp lại ADC, điều kiện đo và lỗi; chỉ đánh giá độ chính xác nồng độ khi có tham chiếu/hiệu chuẩn |
| Tích hợp | Chạy thử toàn bộ camera–RFID–đo–servo–ghi nhật ký với phần cứng |

Không đưa số liệu độ chính xác giả định vào báo cáo kết quả. Kiểm thử phần mềm đã chạy được ghi trong README; thử nghiệm thiết bị phải thực hiện trên bộ phần cứng thực tế.

## 12. Đoạn trình bày ngắn với giáo viên

“Em điều chỉnh phạm vi đề tài thành hệ thống quản lý xe máy cá nhân của nhân viên giao nhận tại một bưu cục logistics. Mỗi nhân viên được đăng ký một xe và một thẻ RFID đang hiệu lực trong cơ sở dữ liệu. Khi vào bãi, hệ thống kiểm tra thẻ và biển số với hồ sơ. Khi lấy xe ra, ngoài việc đối chiếu nhân viên và phương tiện, nhân viên phải thực hiện kiểm tra nồng độ cồn theo từng phiên; chỉ khi kết quả đạt điều kiện thử nghiệm hệ thống mới cho phép mở cổng. Các lần kiểm tra, trường hợp bị từ chối và lượt xe vào/ra được lưu để thống kê theo nhân viên và thời gian. Mô hình hiện tại dùng ADC để đánh giá luồng kiểm soát; phần quy đổi nồng độ cần được hiệu chuẩn và kiểm chứng riêng.”
