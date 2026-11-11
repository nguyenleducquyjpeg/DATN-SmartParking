import cv2
from ultralytics import YOLO

# ==============================
# LOAD MODEL
# ==============================
model = YOLO("best.pt")

# ==============================
# OPEN CAMERA LAPTOP
# ==============================
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ KHONG MO DUOC CAMERA!")
    exit()

print("✅ CAMERA DA MO")
print("Nhan Q de thoat")

# ==============================
# CAMERA LOOP
# ==============================
while True:

    ret, frame = cap.read()

    if not ret:
        print("❌ KHONG DOC DUOC FRAME")
        break

    # YOLO detect
    results = model.predict(
        frame,
        conf=0.40,
        imgsz=640,
        verbose=False
    )

    # Vẽ bounding box
    result_frame = results[0].plot()

    # Hiển thị
    cv2.imshow(
        "TEST LICENSE PLATE",
        result_frame
    )

    # Nhấn Q để thoát
    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

# ==============================
# CLOSE
# ==============================
cap.release()
cv2.destroyAllWindows()

print("Da thoat.")