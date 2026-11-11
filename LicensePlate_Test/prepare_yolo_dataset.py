"""Chia anh da duyet thanh train/val/test va tao file plate.yaml."""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chia dataset YOLO sau khi da duyet nhan.")
    parser.add_argument("--dataset", default="dataset", help="Thu muc dataset")
    parser.add_argument("--source", default="reviewed", help="Ten tap anh da duyet")
    parser.add_argument("--seed", type=int, default=42, help="Seed de chia lap lai duoc")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.dataset).resolve()
    image_source = root / "images" / args.source
    label_source = root / "labels" / args.source
    pairs = [
        image for image in sorted(image_source.glob("*.jpg"))
        if (label_source / f"{image.stem}.txt").is_file()
    ]
    if len(pairs) < 30:
        raise RuntimeError("Can it nhat 30 anh da duyet truoc khi chia dataset.")

    random.Random(args.seed).shuffle(pairs)
    test_count = max(1, round(len(pairs) * 0.10))
    val_count = max(1, round(len(pairs) * 0.20))
    splits = {
        "test": pairs[:test_count],
        "val": pairs[test_count:test_count + val_count],
        "train": pairs[test_count + val_count:],
    }
    for split, images in splits.items():
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        for image_path in images:
            label_path = label_source / f"{image_path.stem}.txt"
            shutil.copy2(image_path, image_dir / image_path.name)
            shutil.copy2(label_path, label_dir / label_path.name)
        print(f"{split}: {len(images)} anh")

    yaml_path = root / "plate.yaml"
    yaml_path.write_text(
        f"path: {root.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n\n"
        "names:\n"
        "  0: license_plate\n",
        encoding="utf-8",
    )
    print(f"Da tao: {yaml_path}")


if __name__ == "__main__":
    main()
