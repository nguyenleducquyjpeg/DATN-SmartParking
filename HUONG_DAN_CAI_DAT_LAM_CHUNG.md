# Hướng dẫn cài đặt và làm chung dự án DATN

Dành cho bạn cùng nhóm dùng Windows 10/11 64-bit. Thực hiện các lệnh PowerShell trong thư mục repo, trừ khi có ghi khác. Bắt đầu bằng mô phỏng; không cần tài khoản Firebase hay phần cứng để sửa giao diện và kiểm thử logic.

## 1. Cài công cụ

- Git: https://git-scm.com/install/windows
- Python 3.11 64-bit, có pip và Tcl/Tk. Nhánh Python 3.11 là môi trường dự án hiện dùng. Tài liệu cài: https://docs.python.org/3.11/using/windows.html
- VS Code hoặc trình soạn thảo bạn quen dùng.
- Node.js 22.11 trở lên nếu chạy kiểm thử JavaScript hoặc làm ứng dụng di động: https://nodejs.org/en/download
- Arduino IDE chỉ cần khi sửa/nạp ESP32: https://www.arduino.cc/en/software

Mở PowerShell mới sau khi cài và kiểm tra:

```powershell
git --version
py -3.11 --version
py -3.11 -m tkinter
node --version
```

Lệnh tkinter phải hiện cửa sổ nhỏ; đóng cửa sổ để tiếp tục. Nếu chưa cài Node và chỉ chạy demo thì bỏ qua lệnh node.

## 2. Tải dự án một lần

Mở terminal tại thư mục bạn muốn lưu dự án:

```powershell
git clone https://github.com/nguyenleducquyjpeg/DATN-SmartParking.git
cd DATN-SmartParking
git status
```

Repo có bộ dữ liệu, mô hình và tài liệu nên tải lâu hơn một repo chỉ có code. Không sao chép đường dẫn `E:\Nam4\DATN` của máy tác giả sang máy bạn. Các lệnh dưới đây dùng đường dẫn tương đối từ thư mục vừa clone.

## 3. Chạy web mô phỏng trước

```powershell
py -3.11 -m http.server 8765 --bind 127.0.0.1 --directory "Alcohol Detection"
```

Giữ terminal này mở, truy cập:

http://127.0.0.1:8765/dashboard.html?simulate=1

Thử: quét thẻ giả → lấy UID vào form → nhập mã, họ tên, bộ phận, biển số → lưu hồ sơ → chọn hồ sơ → ghi thẻ → thu hồi tại dòng nhân viên → xóa dữ liệu thẻ → đăng ký UID đó cho người mới.

Kết quả mong đợi: thao tác ghi/xóa báo thành công; nhân viên cũ ngừng hiệu lực và không còn UID. Dữ liệu mô phỏng nằm trong bộ nhớ của trang, tải lại sẽ mất. Không gửi Firebase hoặc mở cổng thật. Web vẫn cần Internet để tải các tài nguyên ngoài như Firebase SDK/CSS.

Không mở bằng cách bấm đúp file HTML. Dùng URL HTTP phía trên để các module JavaScript hoạt động đúng. Nhấn Ctrl+C trong terminal để dừng server.

## 4. Chạy màn hình cổng Python ở chế độ demo

Mở terminal thứ hai tại thư mục repo:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe LicensePlate_Test\dashboard_parking.py --demo
```

Bấm **Nạp tình huống minh họa** để xem trạng thái hai làn và kết quả đo mẫu. Chế độ này dùng thư viện chuẩn Python, không cần cài YOLO, PaddleOCR, Firebase, không mở camera và không điều khiển thiết bị.

Không cần kích hoạt venv: gọi trực tiếp `.venv\Scripts\python.exe` như trên để tránh lỗi PowerShell chặn Activate.ps1.

Web mô phỏng và Python demo là hai mô phỏng độc lập, không đồng bộ dữ liệu với nhau. Chưa phải mô phỏng xuyên suốt toàn hệ thống.

## 5. Chạy kiểm thử trước khi gửi code

Tại thư mục repo:

```powershell
node --test "Alcohol Detection/test-employee-model.mjs" "Alcohol Detection/test-card-writer.mjs" "Alcohol Detection/test-card-simulator.mjs" "Alcohol Detection/test-card-revoke.mjs"
.\.venv\Scripts\python.exe -m unittest discover -s LicensePlate_Test -p test_employee_gate.py -v
.\.venv\Scripts\python.exe -m unittest discover -s LicensePlate_Test -p test_gate_session.py -v
```

Không chạy toàn bộ `test_*.py` một cách mặc định: `test_camera.py` là chương trình thử camera, không phải bộ kiểm thử logic độc lập.

## 6. Chỉ cài nhận diện khi cần làm camera thật

Trong venv đã tạo:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r LicensePlate_Test\requirements-runtime.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import cv2, PIL, firebase_admin, ultralytics, paddleocr, paddle; print('Import OK')"
```

File requirements là danh sách thư viện trực tiếp và phạm vi phiên bản, chưa phải lockfile đã kiểm chứng trên máy mới. PaddleOCR cần phiên bản 3.x vì code dùng API `predict`. YOLO và PaddleOCR trong `gate_camera.py` chạy CPU; chưa cần cấu hình CUDA. Lần đầu OCR có thể tải thêm mô hình qua Internet. Nếu pip check/import báo lỗi, gửi nguyên log cho nhóm trước khi chạy thật.

Mô hình dự phòng `LicensePlate_Test/best.pt` có trên GitHub. Code ưu tiên trọng số trong `runs/...` nếu có tại máy; `runs/` không được upload, nên nhóm muốn so sánh cùng kết quả phải thống nhất cùng file trọng số.

## 7. Firebase và phần cứng: thống nhất với chủ dự án trước

Không bỏ `--demo` hoặc `?simulate=1` để thử tùy ý: chế độ thật có thể ghi dữ liệu và gửi lệnh vào hệ thống đang kết nối.

Nên dùng Firebase thử nghiệm riêng của nhóm. Nếu cần dùng hệ thống thật của tác giả, thống nhất lịch thử và phạm vi thao tác; chủ dự án cấp quyền phù hợp. Không chia sẻ mật khẩu tài khoản Google.

Các vị trí cấu hình chính:

| Thành phần | File cần cấu hình |
|---|---|
| Web | `Alcohol Detection/dashboard.html`: firebaseConfig |
| Python cổng | `LicensePlate_Test/dashboard_parking.py`: databaseURL trong initialize_runtime |
| Khóa Firebase Admin của Python | `LicensePlate_Test/firebase_key.json`, tạo cho project thử nghiệm, không commit |
| ESP32 cổng | `sketch_aug7a/sketch_aug7a.ino`: địa chỉ Firebase; `wifi_config.h`: Wi-Fi |
| ESP32 cấp thẻ | `CardWriter_ESP32/card_writer/station_config.h` |
| Ứng dụng di động | `KhoaXeApp/firebaseConfig.js` |

Repo không chứa khóa quản trị, Wi-Fi thật hoặc Firebase Rules hoàn chỉnh để triển khai một hệ thống mới. Khóa Firebase Admin có quyền cao; chỉ cấp cho thành viên thực sự cần và không gửi trong issue/PR. Không mở Rules công khai để vượt lỗi permission denied. Firmware trạm cấp thẻ hiện dùng token cấu hình sẵn, chưa tự đăng nhập/làm mới token.

Sau khi cài thư viện, cấu hình project thử nghiệm và cung cấp khóa hợp lệ:

```powershell
.\.venv\Scripts\python.exe LicensePlate_Test\dashboard_parking.py
```

Chọn đúng camera vào/ra (thường 0 và 1, nhưng phụ thuộc máy), không chọn cùng camera cho hai làn. Thực hiện quy trình thử phần cứng với người phụ trách trước khi vận hành.

ESP32 cấp thẻ: xem [hướng dẫn đấu dây, thư viện và nạp](CardWriter_ESP32/README.md). ESP32 cổng dùng sketch riêng; các thư viện gồm MFRC522, Adafruit GFX, Adafruit SSD1306 và ESP32Servo. Không nạp sketch cấp thẻ vào ESP32 đang điều khiển cổng.

## 8. Hai người làm chung bằng Git

Chủ repo mời tài khoản GitHub của bạn vào Collaborators trong Settings của repository; bạn chấp nhận lời mời. Nếu không cấp quyền ghi, bạn có thể Fork rồi mở Pull Request từ fork. Các lệnh dưới áp dụng cho thành viên đã có quyền ghi repo gốc.

Cấu hình danh tính commit một lần trong repo (thay giá trị mẫu bằng thông tin của bạn):

```powershell
git config user.name "Ten cua ban"
git config user.email "Email GitHub cua ban"
```

Mỗi việc làm một nhánh riêng, đặt tên theo nội dung:

```powershell
git switch main
git pull --ff-only origin main
git switch -c codex/employee-profile
```

Sửa code, chạy kiểm thử ở mục 5 rồi kiểm tra và commit đúng file vừa sửa. Ví dụ chỉ sửa dashboard:

```powershell
git status
git diff
git add "Alcohol Detection/dashboard.html"
git diff --cached
git commit -m "Improve employee profile interface"
git push -u origin codex/employee-profile
```

Mở GitHub → tạo Pull Request từ nhánh đó vào `main` → ghi thay đổi và cách đã thử → nhờ người còn lại xem → merge. Sau merge, mỗi người cập nhật `main` bằng `git pull --ff-only origin main` khi cây làm việc sạch. Công việc tiếp theo dùng nhánh mới.

Không push thẳng main hoặc force push để giải quyết xung đột. Nếu pull báo có thay đổi chưa commit, lưu/commit công việc trên nhánh hiện tại trước. Nếu cùng sửa một file, trao đổi với nhau và xử lý từng đoạn xung đột, không chọn bỏ toàn bộ code của người kia.

Gợi ý phân công: một người làm web/quản lý tài xế; một người làm Python/camera hoặc ESP32. Khi thay schema Firebase, tên trạng thái, định dạng thẻ hay ngưỡng đo, thống nhất trước vì các thành phần dùng chung giao thức.

Không commit `.venv`, `node_modules`, file build, khóa JSON, `.env`, `wifi_config.h`, `station_config.h`, ảnh vận hành hoặc thông tin nhân viên thật. `.gitignore` đã loại phần lớn các file này, nhưng vẫn cần xem `git diff --cached` trước commit.

## 9. KhoaXeApp là phần tùy chọn

Nếu chỉ phụ web/Python/ESP32 thì chưa cần cài môi trường React Native. Nếu phụ mobile, đọc [README ứng dụng](KhoaXeApp/README.md); package.json yêu cầu Node >=22.11.0. Trong thư mục KhoaXeApp dùng `npm ci` theo package-lock, sau đó cấu hình Android SDK/JDK theo phiên bản React Native 0.86 của dự án trước khi chạy `npm run android`. Không cần tạo Git repo riêng bên trong thư mục này khi làm từ bản clone DATN.

## 10. Lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| Không tìm thấy `py`/`git` | Kiểm tra cài đặt và mở lại terminal |
| Không tìm thấy `tkinter` | Cài Python có thành phần Tcl/Tk |
| Cổng 8765 đã dùng | Dừng server cũ hoặc đổi cả lệnh và URL sang 8766 |
| Web không có nút mới | Ctrl+F5; kiểm tra đúng repo và URL đang chạy |
| Không thấy firebase_key.json | Demo không cần khóa; chạy thật cần khóa project thử nghiệm |
| ModuleNotFoundError | Cài bằng đúng `.venv\Scripts\python.exe -m pip`, không dùng pip của Python khác |
| Thư viện ML không cài được | Xác nhận Python 3.11 64-bit, chép log lỗi và phiên bản pip cho nhóm |
| Camera không mở | Kiểm tra index, quyền camera Windows và ứng dụng khác đang giữ camera |
| Push bị từ chối quyền | Chấp nhận lời mời Collaborator, đăng nhập đúng GitHub hoặc dùng Fork |

Hoàn tất cài ban đầu khi: web mô phỏng chạy, Python demo mở được và các kiểm thử logic đạt. Camera/Firebase/ESP32 được nghiệm thu riêng; không xem chạy demo là bằng chứng phần cứng đã hoạt động.
