import cv2
import re
import time
from datetime import datetime

from ultralytics import YOLO
from paddleocr import PaddleOCR

import firebase_admin
from firebase_admin import credentials, db


# =========================================================
# CẤU HÌNH LỐI RA (OUT)
# =========================================================

YOLO_MODEL = "best.pt"
YOLO_CONF = 0.55
YOLO_INTERVAL = 0.15
OCR_INTERVAL = 0.5
STABLE_COUNT = 3

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_INDEX = 0 # Đổi thành 1 nếu dùng camera thứ 2


# =========================================================
# FIREBASE
# =========================================================

print("Dang ket noi Firebase (Loi Ra)...")

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(
        cred,
        {
            "databaseURL": "https://alcohol-detection-a3c5b-default-rtdb.asia-southeast1.firebasedatabase.app"
        }
    )

print("Firebase OK")


# =========================================================
# YOLO & PADDLE OCR
# =========================================================

print("Dang khoi dong YOLO...")
model = YOLO(YOLO_MODEL)
print("YOLO OK")

print("Dang khoi dong PaddleOCR...")
ocr = PaddleOCR(
    lang="en",
    device="cpu",
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_mobile_rec",
)
print("PaddleOCR OK")


# =========================================================
# HÀM LÀM SẠCH & OCR
# =========================================================

def clean_plate(text):
    text = text.upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def read_plate(img):
    try:
        if img is None or img.size == 0:
            return ""

        img = cv2.resize(img, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
        results = ocr.predict(img)
        texts = []

        for result in results:
            data = result.json
            if "res" in data:
                data = data["res"]

            rec_texts = data.get("rec_texts", [])
            rec_scores = data.get("rec_scores", [])

            for text, score in zip(rec_texts, rec_scores):
                if float(score) >= 0.3:
                    text = clean_plate(text)
                    if text:
                        texts.append(text)

        return "".join(texts)
    except Exception as e:
        print("OCR ERROR:", e)
        return ""


# =========================================================
# XỬ LÝ CẬP NHẬT TRẠNG THÁI "OUT" (DÙNG CHUNG CHO CẢ CAM VÀ BÀN PHÍM)
# =========================================================

def update_vehicle_to_out(plate):
    try:
        plate = clean_plate(plate)
        if not plate:
            print("Bien so khong hop le!")
            return False

        ref = db.reference("BienSoXe")
        all_vehicles = ref.get()
        
        target_key = None
        has_already_out = False
        
        if all_vehicles:
            for key, value in all_vehicles.items():
                if isinstance(value, dict):
                    if value.get("bienSo") == plate:
                        if value.get("trangThai") == "IN":
                            target_key = key
                            break
                        elif value.get("trangThai") == "OUT":
                            has_already_out = True

        if not target_key and not has_already_out:
            print("================================")
            print(f"CANH BAO: Xe bien so [{plate}] KHONG CO TRONG BAI!")
            print("================================")
            return False

        if has_already_out and not target_key:
            print("================================")
            print(f"CANH BAO: Xe bien so [{plate}] DA ROI KHOI BAI TRUOC DO ROI!")
            print("================================")
            return False

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        ref.child(target_key).update({
            "thoiGianRa": now_str,
            "trangThai": "OUT"
        })

        print("================================")
        print("XE RA HOP LE (THỦ CÔNG/CAM) - DA CAP NHAT OUT")
        print("BIEN SO :", plate)
        print("THOI GIAN RA:", now_str)
        print("FIREBASE KEY:", target_key)
        print("================================")
        return True

    except Exception as e:
        print("FIREBASE ERROR:", e)
        return False


# =========================================================
# CAMERA LỐI RA & MAIN LOOP
# =========================================================

cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

last_yolo = 0
last_ocr = 0
boxes = []
candidate = ""
stable = 0
current_plate = ""
saved_plate = ""

print("\n==================================================")
print(" HỆ THỐNG LỐI RA ĐÃ SẴN SÀNG")
print(" - Nhấn phím 'o' trên bàn phím để NHẬP BIẾN SỐ THỦ CÔNG")
print(" - Nhấn phím 'q' để thoát chương trình")
print("==================================================\n")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    now = time.time()
    display = frame.copy()

    # YOLO nhận diện tự động
    if now - last_yolo >= YOLO_INTERVAL:
        last_yolo = now
        results = model(frame, conf=YOLO_CONF, verbose=False)
        boxes = []
        for r in results:
            if r.boxes is None:
                continue
            for b in r.boxes:
                conf = float(b.conf[0])
                x1, y1, x2, y2 = map(int, b.xyxy[0])
                boxes.append((x1, y1, x2, y2, conf))

    if boxes:
        x1, y1, x2, y2, conf = max(boxes, key=lambda x: x[4])
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 2)

        # OCR tự động
        if now - last_ocr >= OCR_INTERVAL:
            last_ocr = now
            crop = frame[y1:y2, x1:x2]
            text = read_plate(crop)

            if 5 <= len(text) <= 12:
                if text == candidate:
                    stable += 1
                else:
                    candidate = text
                    stable = 1

                if stable >= STABLE_COUNT:
                    if current_plate != candidate:
                        current_plate = candidate
                        print(f"BIEN SO RA (CAM): {current_plate}")

                        if saved_plate != current_plate:
                            success = update_vehicle_to_out(current_plate)
                            if success:
                                saved_plate = current_plate

        label = current_plate if current_plate else "OCR OUT..."
        cv2.putText(display, label, (x1, max(30, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    cv2.imshow("EXIT GATE - LICENSE PLATE + OCR", display)

    # Đọc phím bấm từ bàn phím (độ trễ 1ms)
    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):  # Nhấn 'q' để thoát
        break
    elif key == ord("o"):  # Nhấn 'o' để nhập biển số thủ công cho lối ra
        while True:
            print("\n--- NHẬP BIỂN SỐ THỦ CÔNG CHO LỐI RA ---")
            manual_plate = input("Nhập biển số xe (hoặc gõ 'c' để hủy): ").strip()
            
            if manual_plate.lower() == 'c':
                print("Đã hủy nhập thủ công.")
                break
                
            if manual_plate:
                success = update_vehicle_to_out(manual_plate)
                if success:
                    # Nếu nhập đúng và xử lý thành công thì thoát vòng lặp nhập
                    break
                else:
                    # Nếu nhập sai hoặc không có trong bãi, hỏi xem có muốn nhập lại không
                    choice = input("Bạn có muốn nhập lại không? (y/n): ").strip().lower()
                    if choice != 'y':
                        break
            else:
                print("Biển số không được để trống!")

cap.release()
cv2.destroyAllWindows()