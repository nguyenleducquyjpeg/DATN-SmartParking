"""Thu thap anh bien so webcam va tao nhan YOLO ban dau.

Nhan duoc sinh boi model chi la nhan goi y. Hay kiem tra/sua truoc khi train.

Vi du:
    python collect_plate_dataset.py --camera 0 --model best.pt
    python collect_plate_dataset.py --camera 0 --save-no-detection
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tu dong thu anh webcam va auto-label bien so theo dinh dang YOLO."
    )
    parser.add_argument("--camera", type=int, default=0, help="Chi so webcam (mac dinh: 0)")
    parser.add_argument("--model", default="best.pt", help="Duong dan model YOLO")
    parser.add_argument("--output", default="dataset", help="Thu muc dataset goc")
    parser.add_argument("--width", type=int, default=1280, help="Do rong webcam")
    parser.add_argument("--height", type=int, default=720, help="Do cao webcam")
    parser.add_argument("--imgsz", type=int, default=960, help="Kich thuoc input YOLO")
    parser.add_argument("--conf", type=float, default=0.20, help="Nguong tin cay de goi y nhan")
    parser.add_argument("--device", default="0", help="0 dung GPU NVIDIA thu nhat; cpu neu can")
    parser.add_argument("--capture-interval", type=float, default=1.0, help="Khoang cach toi thieu giua 2 anh luu")
    parser.add_argument("--infer-interval", type=float, default=0.20, help="Khoang cach toi thieu giua 2 lan YOLO")
    parser.add_argument(
        "--save-no-detection",
        action="store_true",
        help="Luu ca anh khong co bien de tao hard-negative (nhan rong)",
    )
    return parser.parse_args()


def make_yolo_labels(result, frame_width: int, frame_height: int) -> list[str]:
    """Chuyen cac box pixel sang dong label: class xc yc w h."""
    labels: list[str] = []
    if result.boxes is None:
        return labels

    for box in result.boxes:
        x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
        x1, x2 = max(0.0, x1), min(float(frame_width), x2)
        y1, y2 = max(0.0, y1), min(float(frame_height), y2)
        width, height = x2 - x1, y2 - y1
        if width <= 1 or height <= 1:
            continue

        xc = (x1 + x2) / 2 / frame_width
        yc = (y1 + y2) / 2 / frame_height
        labels.append(f"0 {xc:.6f} {yc:.6f} {width / frame_width:.6f} {height / frame_height:.6f}")
    return labels


def draw_preview(frame, result, labels: list[str], capture_count: int) -> None:
    if result.boxes is not None:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            score = float(box.conf[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"plate {score:.2f}",
                (x1, max(24, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2,
            )

    info = f"saved: {capture_count} | detections: {len(labels)} | SPACE: save | Q: quit"
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (0, 0, 0), -1)
    cv2.putText(frame, info, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)


def save_sample(image_dir: Path, label_dir: Path, frame, labels: list[str]) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = f"plate_{stamp}"
    image_path = image_dir / f"{stem}.jpg"
    label_path = label_dir / f"{stem}.txt"
    if not cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise RuntimeError(f"Khong the luu anh: {image_path}")
    label_path.write_text("\n".join(labels), encoding="utf-8")
    return stem


def main() -> None:
    args = parse_args()
    image_dir = Path(args.output) / "images" / "raw"
    label_dir = Path(args.output) / "labels" / "raw"
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.model)
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        raise RuntimeError(f"Khong mo duoc webcam index {args.camera}. Thu --camera 1 neu can.")

    last_infer = 0.0
    last_capture = 0.0
    latest_result = None
    latest_labels: list[str] = []
    saved = 0
    print("Da mo webcam. Nhan SPACE de luu frame hien tai, Q de ket thuc.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Khong doc duoc frame tu webcam.")

            now = time.monotonic()
            if now - last_infer >= args.infer_interval:
                last_infer = now
                latest_result = model(
                    frame,
                    conf=args.conf,
                    imgsz=args.imgsz,
                    device=args.device,
                    verbose=False,
                )[0]
                latest_labels = make_yolo_labels(latest_result, frame.shape[1], frame.shape[0])

            preview = frame.copy()
            if latest_result is not None:
                draw_preview(preview, latest_result, latest_labels, saved)
            cv2.imshow("Plate dataset collector", preview)

            key = cv2.waitKey(1) & 0xFF
            manual_save = key == ord(" ")
            should_auto_save = bool(latest_labels) and now - last_capture >= args.capture_interval
            should_save_negative = args.save_no_detection and now - last_capture >= args.capture_interval
            if manual_save or should_auto_save or should_save_negative:
                if latest_labels or args.save_no_detection or manual_save:
                    name = save_sample(image_dir, label_dir, frame, latest_labels)
                    saved += 1
                    last_capture = now
                    print(f"Saved {name}: {len(latest_labels)} box(es)")
            if key in (ord("q"), 27):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"Da luu {saved} anh vao: {image_dir.resolve()}")


if __name__ == "__main__":
    main()
