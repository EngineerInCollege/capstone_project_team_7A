#!/usr/bin/env python3
import os
import argparse
from pathlib import Path

import cv2
import numpy as np

# Supported image extensions
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMG_EXTS


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def find_duck_bbox(img_bgr, debug=False):
    """
    Try to find the duck region using HSV color thresholding
    for multiple duck colors.

    Returns (x, y, w, h) or None if no region found.
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    H_img, W_img = img_bgr.shape[:2]

    # ---- HSV ranges (OpenCV: H in [0,179], S,V in [0,255]) ----

    # Pink / magenta duck: make it a bit "brighter" / more saturated
    lower_pink = np.array([140, 50, 50], dtype=np.uint8)
    upper_pink = np.array([175, 255, 255], dtype=np.uint8)

    # Bright yellow ducks (body)
    lower_yellow = np.array([20, 120, 120], dtype=np.uint8)
    upper_yellow = np.array([35, 255, 255], dtype=np.uint8)

    # Green ducks
    lower_green = np.array([35, 120, 120], dtype=np.uint8)
    upper_green = np.array([85, 255, 255], dtype=np.uint8)

    # Orange (beaks / orange bodies) – slightly lower hue than yellow
    lower_orange = np.array([10,  180, 180], dtype=np.uint8)
    upper_orange = np.array([25, 255, 255], dtype=np.uint8)

    kernel = np.ones((5, 5), np.uint8)
    min_area = 0.001 * W_img * H_img   # ignore tiny specs
    max_area = 0.3   * W_img * H_img   # ignore huge blobs

    def best_bbox_from_mask(mask, color_name):
        """Find the best bbox from a single-color mask."""
        h, w = mask.shape
        border = int(0.1 * min(h, w))  # 10% border

        # restrict to central region (duck near middle)
        mask[:border, :] = 0
        mask[-border:, :] = 0
        mask[:, :border] = 0
        mask[:, -border:] = 0

        m = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
        m = cv2.morphologyEx(m,    cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        best = None
        best_area_local = 0

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = w * h
            if area < min_area or area > max_area:
                continue

            aspect = w / float(h)
            # Reject extremely skinny / long shapes
            if aspect < 0.3 or aspect > 3.0:
                continue

            if area > best_area_local:
                best_area_local = area
                best = (x, y, w, h)

        if debug:
            if best is None:
                print(f"[DEBUG] No valid {color_name} contour")
            else:
                x, y, w, h = best
                print(f"[DEBUG] Best {color_name} bbox: "
                      f"x={x}, y={y}, w={w}, h={h}, area={best_area_local}")

        return best

    # Build masks
    mask_pink    = cv2.inRange(hsv, lower_pink,   upper_pink)
    mask_yellow  = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask_green   = cv2.inRange(hsv, lower_green,  upper_green)
    mask_orange  = cv2.inRange(hsv, lower_orange, upper_orange)

    # Priority:
    color_masks = [
        ("pink",   mask_pink),
        ("green",  mask_green),
        ("yellow", mask_yellow),
        ("orange", mask_orange),
    ]

    for color_name, mask in color_masks:
        bbox = best_bbox_from_mask(mask, color_name)
        if bbox is not None:
            if debug:
                print(f"[DEBUG] Using {color_name} bbox")
            return bbox

    if debug:
        print("[DEBUG] No duck-like bbox found for any color")
    return None


def crop_with_padding(img_bgr, bbox, padding_factor=1.2):
    """
    Expand the bounding box by padding_factor (e.g., 1.2 means 20% padding)
    and crop, clamped to image boundaries.
    """
    H, W = img_bgr.shape[:2]
    x, y, w, h = bbox

    cx = x + w / 2.0
    cy = y + h / 2.0

    # New size with padding
    new_w = int(w * padding_factor)
    new_h = int(h * padding_factor)

    # Make it roughly square to avoid extreme distortions later
    side = max(new_w, new_h)
    new_w = new_h = side

    x1 = int(cx - new_w / 2.0)
    y1 = int(cy - new_h / 2.0)
    x2 = x1 + new_w
    y2 = y1 + new_h

    # Clamp to image bounds
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(W, x2)
    y2 = min(H, y2)

    return img_bgr[y1:y2, x1:x2]


def center_crop_square(img_bgr):
    """
    Fallback: take a central square crop.
    """
    H, W = img_bgr.shape[:2]
    side = min(H, W)
    x1 = (W - side) // 2
    y1 = (H - side) // 2
    x2 = x1 + side
    y2 = y1 + side
    return img_bgr[y1:y2, x1:x2]


def process_image(src_path: Path, dst_path: Path, resize_to=None, debug=False):
    """
    Load an image, attempt duck-aware crop, optionally resize,
    and save to dst_path.
    """
    img_bgr = cv2.imread(str(src_path))
    if img_bgr is None:
        print(f"[WARN] Could not read image: {src_path}")
        return

    bbox = find_duck_bbox(img_bgr, debug=debug)
    if bbox is not None:
        crop = crop_with_padding(img_bgr, bbox, padding_factor=1.2)
    else:
        # fallback to center crop
        if debug:
            print(f"[INFO] No duck bbox found, center cropping: {src_path}")
        crop = center_crop_square(img_bgr)

    if resize_to is not None:
        crop = cv2.resize(crop, (resize_to, resize_to), interpolation=cv2.INTER_AREA)

    ensure_dir(dst_path.parent)
    success = cv2.imwrite(str(dst_path), crop)
    if not success:
        print(f"[WARN] Failed to write image: {dst_path}")

    if bbox is not None and debug:
        x, y, w, h = bbox
        debug_img = img_bgr.copy()
        cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Resize preview window to something reasonable
        preview = debug_img.copy()
        h0, w0 = preview.shape[:2]
        scale = 640 / w0   # target width = 640 px
        preview = cv2.resize(preview, (640, int(h0 * scale)))

        cv2.imshow("debug", preview)
        cv2.waitKey(0)
        cv2.destroyAllWindows()




def copy_and_crop_dataset(src_root: Path, dst_root: Path,
                          resize_to=None, debug=False):
    """
    Walk src_root, process all images, and mirror the directory structure
    into dst_root with cropped images.
    """
    src_root = src_root.resolve()
    dst_root = dst_root.resolve()

    print(f"Source root: {src_root}")
    print(f"Dest   root: {dst_root}")
    if resize_to:
        print(f"Will resize crops to: {resize_to}x{resize_to}")
    print()

    for dirpath, _, filenames in os.walk(src_root):
        dirpath = Path(dirpath)
        rel_dir = dirpath.relative_to(src_root)
        for fname in filenames:
            src_path = dirpath / fname
            if not is_image_file(src_path):
                continue

            dst_path = dst_root / rel_dir / fname
            process_image(src_path, dst_path, resize_to=resize_to, debug=debug)


def main():
    parser = argparse.ArgumentParser(
        description="Crop duck images around duck and mirror dataset structure."
    )
    parser.add_argument(
        "--src_root",
        type=str,
        required=True,
        help="Path to original dataset root (contains train/val/test/... folders).",
    )
    parser.add_argument(
        "--dst_root",
        type=str,
        required=True,
        help="Where to write the cropped dataset.",
    )
    parser.add_argument(
        "--resize_to",
        type=int,
        default=None,
        help="If set, resize cropped images to this square size (e.g., 128).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print extra debug info.",
    )

    args = parser.parse_args()

    copy_and_crop_dataset(
        src_root=Path(args.src_root),
        dst_root=Path(args.dst_root),
        resize_to=args.resize_to,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
