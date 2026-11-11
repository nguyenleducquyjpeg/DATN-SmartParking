"""Duyet nhanh auto-label truoc khi train YOLO.

Phim tat: A/Enter = giu anh, D = loai anh, Q/Esc = thoat.
Anh duoc giu se duoc copy sang dataset/images/reviewed va labels/reviewed.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Duyet nhanh label bien so YOLO.")
    parser.add_argument("--dataset", default="dataset", help="Thu muc dataset")
    parser.add_argument("--source", default="raw", help="Ten tap nguon (mac dinh: raw)")
    parser.add_argument("--output", default="reviewed", help="Ten tap anh duoc giu")
    parser.add_argument("--max-width", type=int, default=1280, help="Do rong cua so xem truoc")
    return parser.parse_args()


def read_boxes(label_path: Path, image_width: int, image_height: int):
    boxes = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        _, xc, yc, width, height = map(float, parts)
        x1 = int((xc - width / 2) * image_width)
        y1 = int((yc - height / 2) * image_height)
        x2 = int((xc + width / 2) * image_width)
        y2 = int((yc + height / 2) * image_height)
        boxes.append((x1, y1, x2, y2))
    return boxes


def preview(image, boxes, position: int, total: int):
    shown = image.copy()
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(shown, (x1, y1), (x2, y2), (0, 255, 0), 3)
    title = f"{position}/{total} | A/Enter: keep | D: discard | Q: quit"
    cv2.rectangle(shown, (0, 0), (shown.shape[1], 44), (0, 0, 0), -1)
    cv2.putText(shown, title, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
    return shown


def main() -> None:
    args = parse_args()
    dataset = Path(args.dataset)
    image_source = dataset / "images" / args.source
    label_source = dataset / "labels" / args.source
    image_output = dataset / "images" / args.output
    label_output = dataset / "labels" / args.output
    image_output.mkdir(parents=True, exist_ok=True)
    label_output.mkdir(parents=True, exist_ok=True)

    images = sorted(image_source.glob("*.jpg")) + sorted(image_source.glob("*.png"))
    candidates = [p for p in images if (label_source / f"{p.stem}.txt").is_file() and not (image_output / p.name).exists()]
    if not candidates:
        print("Khong co anh moi de duyet. Kiem tra thu muc nguon/output.")
        return

    kept = 0
    discarded = 0
    cv2.namedWindow("Review plate labels", cv2.WINDOW_NORMAL)
    for index, image_path in enumerate(candidates, start=1):
        label_path = label_source / f"{image_path.stem}.txt"
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"Bo qua anh khong doc duoc: {image_path.name}")
            continue
        boxes = read_boxes(label_path, image.shape[1], image.shape[0])
        shown = preview(image, boxes, index, len(candidates))
        if shown.shape[1] > args.max_width:
            ratio = args.max_width / shown.shape[1]
            shown = cv2.resize(shown, None, fx=ratio, fy=ratio)
        cv2.imshow("Review plate labels", shown)
        key = cv2.waitKey(0) & 0xFF
        if key in (ord("q"), 27):
            break
        if key in (ord("a"), 13):
            shutil.copy2(image_path, image_output / image_path.name)
            shutil.copy2(label_path, label_output / label_path.name)
            kept += 1
        elif key == ord("d"):
            discarded += 1

    cv2.destroyAllWindows()
    print(f"Da giu {kept} anh, loai {discarded} anh.")
    print(f"Anh da giu: {image_output.resolve()}")


if __name__ == "__main__":
    main()
