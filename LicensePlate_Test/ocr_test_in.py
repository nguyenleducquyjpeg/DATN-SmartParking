import cv2
import re
import time
from datetime import datetime

from ultralytics import YOLO
from paddleocr import PaddleOCR

import firebase_admin
from firebase_admin import credentials, db


# =========================================================
# CẤU HÌNH LỐI VÀO (IN)
# =========================================================

YOLO_MODEL = "best.pt"

YOLO_CONF = 0.55

YOLO_INTERVAL = 0.15

OCR_INTERVAL = 0.5

STABLE_COUNT = 3

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_INDEX = 0  # Đổi thành 1 nếu dùng camera thứ 2


# =========================================================
# FIREBASE
# =========================================================

print("Dang ket noi Firebase...")

if not firebase_admin._apps:

    cred = credentials.Certificate(
        "firebase_key.json"
    )

    firebase_admin.initialize_app(
        cred,
        {
            "databaseURL":
            "https://alcohol-detection-a3c5b-default-rtdb.asia-southeast1.firebasedatabase.app"
        }
    )

print("Firebase OK")


# =========================================================
# YOLO
# =========================================================

print("Dang khoi dong YOLO...")

model = YOLO(YOLO_MODEL)

print("YOLO OK")


# =========================================================
# PADDLE OCR
# =========================================================

print("Dang khoi dong PaddleOCR...")

ocr = PaddleOCR(
    lang="en",
    device="cpu",
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_mobile_rec",
)

print("PaddleOCR OK")


# =========================================================
# HÀM LÀM SẠCH
# =========================================================

def clean_plate(text):

    text = text.upper()

    return re.sub(
        r"[^A-Z0-9]",
        "",
        text
    )


# =========================================================
# OCR
# =========================================================

def read_plate(img):

    try:

        if img is None or img.size == 0:
            return ""

        img = cv2.resize(
            img,
            None,
            fx=2.5,
            fy=2.5,
            interpolation=cv2.INTER_CUBIC
        )

        results = ocr.predict(img)

        texts = []

        for result in results:

            data = result.json

            if "res" in data:
                data = data["res"]

            rec_texts = data.get("rec_texts", [])
            rec_scores = data.get("rec_scores", [])

            for text, score in zip(
                rec_texts,
                rec_scores
            ):

                if float(score) >= 0.3:

                    text = clean_plate(text)

                    if text:
                        texts.append(text)

        return "".join(texts)

    except Exception as e:

        print("OCR ERROR:", e)

        return ""


# =========================================================
# LƯU FIREBASE (CÓ KIỂM TRA TRÙNG LẶP TRONG BÃI)
# =========================================================

def process_vehicle_in(plate):

    try:
        plate = clean_plate(plate)
        if not plate:
            print("Bien so khong hop le!")
            return False

        ref = db.reference("BienSoXe")
        all_vehicles = ref.get()
        
        # Kiểm tra xem xe này có đang ở trong bãi không (trạng thái IN)
        is_already_inside = False
        if all_vehicles:
            for key, value in all_vehicles.items():
                if isinstance(value, dict):
                    if value.get("bienSo") == plate and value.get("trangThai") == "IN":
                        is_already_inside = True
                        break

        if is_already_inside:
            print("================================")
            print(f"CANH BAO: Xe bien so [{plate}] ĐÃ CÓ TRONG BÃI RỒI!")
            print("================================")
            return False

        # Lấy thời gian thực định dạng chuỗi dễ đọc
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data = {
            "bienSo": plate,
            "thoiGian": now_str,  # Lưu dưới dạng chuỗi ngày giờ
            "trangThai": "IN"
        }

        new_ref = ref.push(data)

        print("================================")
        print("XE VÀO HỢP LỆ - ĐÃ LƯU FIREBASE")
        print("BIEN SO :", plate)
        print("THOI GIAN:", now_str)
        print("FIREBASE ID:", new_ref.key)
        print("================================")
        return True

    except Exception as e:

        print("FIREBASE ERROR:", e)
        return False


# =========================================================
# CAMERA
# =========================================================

cap = cv2.VideoCapture(CAMERA_INDEX)

cap.set(
    cv2.CAP_PROP_FRAME_WIDTH,
    CAMERA_WIDTH
)

cap.set(
    cv2.CAP_PROP_FRAME_HEIGHT,
    CAMERA_HEIGHT
)

cap.set(
    cv2.CAP_PROP_BUFFERSIZE,
    1
)


# =========================================================
# BIẾN
# =========================================================

last_yolo = 0

last_ocr = 0

boxes = []

candidate = ""

stable = 0

current_plate = ""

saved_plate = ""

print("\n==================================================")
print(" HỆ THỐNG LỐI VÀO ĐÃ SẴN SÀNG")
print(" - Nhấn phím 'i' trên bàn phím để NHẬP BIỂN SỐ THỦ CÔNG")
print(" - Nhấn phím 'q' để thoát chương trình")
print("==================================================\n")


# =========================================================
# MAIN
# =========================================================

while True:

    ret, frame = cap.read()

    if not ret:
        continue

    now = time.time()

    display = frame.copy()


    # YOLO
    if now - last_yolo >= YOLO_INTERVAL:

        last_yolo = now

        results = model(
            frame,
            conf=YOLO_CONF,
            verbose=False
        )

        boxes = []

        for r in results:

            if r.boxes is None:
                continue

            for b in r.boxes:

                conf = float(b.conf[0])

                x1, y1, x2, y2 = map(
                    int,
                    b.xyxy[0]
                )

                boxes.append(
                    (x1, y1, x2, y2, conf)
                )


    if boxes:

        x1, y1, x2, y2, conf = max(
            boxes,
            key=lambda x: x[4]
        )

        cv2.rectangle(
            display,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )


        # OCR
        if now - last_ocr >= OCR_INTERVAL:

            last_ocr = now

            crop = frame[
                y1:y2,
                x1:x2
            ]

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

                        print(
                            f"BIEN SO VAO (CAM): {current_plate}"
                        )

                        # Lưu Firebase 1 lần
                        if saved_plate != current_plate:

                            success = process_vehicle_in(
                                current_plate
                            )
                            
                            if success:
                                saved_plate = current_plate


        label = (
            current_plate
            if current_plate
            else "OCR..."
        )

        cv2.putText(
            display,
            label,
            (x1, max(30, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )


    cv2.imshow(
        "ENTRY GATE - LICENSE PLATE + OCR + FIREBASE",
        display
    )

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break
    elif key == ord("i"):  # Nhấn phím 'i' để nhập thủ công cho lối vào
        while True:
            print("\n--- NHẬP BIỂN SỐ THỦ CÔNG CHO LỐI VÀO ---")
            manual_plate = input("Nhập biển số xe (hoặc gõ 'c' để hủy): ").strip()
            
            if manual_plate.lower() == 'c':
                print("Đã hủy nhập thủ công.")
                break
                
            if manual_plate:
                success = process_vehicle_in(manual_plate)
                if success:
                    break
                else:
                    choice = input("Bạn có muốn nhập lại không? (y/n): ").strip().lower()
                    if choice != 'y':
                        break
            else:
                print("Biển số không được để trống!")


cap.release()

cv2.destroyAllWindows()