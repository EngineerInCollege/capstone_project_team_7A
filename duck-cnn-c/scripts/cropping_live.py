#!/usr/bin/env python3
import os
import argparse
from pathlib import Path

import cv2
import numpy as np
import json

# Supported image extensions
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
ROI_CACHE = {}

def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMG_EXTS

def load_roi_for_camera(cam_name: str, roi_root: Path, debug: bool = False):
    """
    Load and cache ROI for a given camera from a global roi_root directory.

    Expected files:
        roi_root / f"roi_{cam_name}.json"
    """
    # Return cached ROI if already loaded
    if cam_name in ROI_CACHE:
        if debug:
            print(f"[DEBUG] (cache) Using ROI for camera '{cam_name}'")
        return ROI_CACHE[cam_name]

    roi_json = roi_root / f"roi_{cam_name}.json"

    if debug:
        print(f"[DEBUG] Camera detected: {cam_name}")
        print(f"[DEBUG] Looking for ROI file: {roi_json}")

    if not roi_json.exists():
        if debug:
            print(f"[DEBUG] ROI file NOT FOUND for '{cam_name}' → using full image.")
        ROI_CACHE[cam_name] = None
        return None

    try:
        with open(roi_json, "r") as f:
            data = json.load(f)

        pts = data.get("points", None)

        if not pts or len(pts) < 3:
            if debug:
                print(f"[DEBUG] ROI file exists but INVALID for '{cam_name}' → full image.")
            ROI_CACHE[cam_name] = None
            return None

        if debug:
            print(f"[DEBUG] Loaded ROI for '{cam_name}' from:")
            print(f"[DEBUG]   {roi_json}")
            print(f"[DEBUG] ROI points: {pts}")

        ROI_CACHE[cam_name] = pts
        return pts

    except Exception as e:
        print(f"[WARN] Failed to load ROI for {cam_name} from {roi_json}: {e}")
        ROI_CACHE[cam_name] = None
        return None


def load_roi_polygon(roi_json_path: Path):
    """
    Load ROI polygon from JSON file with structure:
    { "points": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]] }
    Returns np.ndarray of shape (N, 1, 2) or None if not found/invalid.
    """
    if not roi_json_path.exists():
        return None

    try:
        with open(roi_json_path, "r") as f:
            data = json.load(f)
        pts = data.get("points", None)
        if not pts or len(pts) < 3:
            return None
        pts = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
        return pts
    except Exception as e:
        print(f"[WARN] Failed to load ROI from {roi_json_path}: {e}")
        return None



def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def find_duck_bboxes(img_bgr, roi_poly=None, debug=False):
    """
    Find *all* duck-like bounding boxes for multiple colors.
    Optionally restrict search to an ROI polygon.
    Returns a list of (x, y, w, h, color_name).
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    H_img, W_img = img_bgr.shape[:2]

    # --- your tuned color ranges here (use what you have working now) ---
    lower_pink   = np.array([150, 10, 190], dtype=np.uint8)
    upper_pink   = np.array([179, 255, 255], dtype=np.uint8)

    lower_yellow = np.array([22, 40, 180], dtype=np.uint8)   # H>=44°, S>=40, V>=180
    upper_yellow = np.array([40, 255, 255], dtype=np.uint8)  # H<=80°

    lower_green  = np.array([35, 40, 40], dtype=np.uint8)
    upper_green  = np.array([90, 255, 255], dtype=np.uint8)

    lower_orange = np.array([6, 60, 170], dtype=np.uint8)
    upper_orange = np.array([18, 255, 255], dtype=np.uint8)

    kernel = np.ones((5, 5), np.uint8)
    min_area = 0.001 * W_img * H_img
    max_area = 0.3   * W_img * H_img

    # ----- ROI mask from polygon (if provided) -----
    roi_mask = None
    if roi_poly is not None:
        # roi_poly can be [[x,y], [x,y], ...] or already (N,1,2)
        pts = np.array(roi_poly, dtype=np.int32)
        if pts.ndim == 2:
            pts = pts.reshape((-1, 1, 2))
        roi_mask = np.zeros((H_img, W_img), dtype=np.uint8)
        cv2.fillPoly(roi_mask, [pts], 255)
        if debug:
            print("[DEBUG] Using ROI mask with", len(pts), "points")

    def bboxes_from_mask(mask, color_name):
        h, w = mask.shape
        border = int(0.1 * min(h, w))  # 10% border

        mask = mask.copy()
        mask[:border, :]  = 0
        mask[-border:, :] = 0
        mask[:, :border]  = 0
        mask[:, -border:] = 0

        m = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
        m = cv2.morphologyEx(m,    cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        results = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = w * h
            if area < min_area or area > max_area:
                if debug:
                    print(f"[DEBUG] {color_name}: reject area={area:.1f}")
                continue

            aspect = w / float(h)
            if aspect < 0.3 or aspect > 3.0:
                if debug:
                    print(f"[DEBUG] {color_name}: reject aspect={aspect:.2f}")
                continue

            if debug:
                print(f"[DEBUG] {color_name} bbox: x={x}, y={y}, w={w}, h={h}, area={area}")
            results.append((x, y, w, h, color_name))
        return results

    color_ranges = [
        ("pink",   lower_pink,   upper_pink),
        ("green",  lower_green,  upper_green),
        ("yellow", lower_yellow, upper_yellow),
        ("orange", lower_orange, upper_orange),
    ]

    all_bboxes = []
    for color_name, lo, hi in color_ranges:
        mask = cv2.inRange(hsv, lo, hi)
        # restrict to ROI if mask exists
        if roi_mask is not None:
            mask = cv2.bitwise_and(mask, roi_mask)
        all_bboxes.extend(bboxes_from_mask(mask, color_name))

    if debug:
        print(f"[DEBUG] Found {len(all_bboxes)} duck-like bbox(es) in ROI" if roi_mask is not None
              else f"[DEBUG] Found {len(all_bboxes)} duck-like bbox(es) in full image")

    return all_bboxes


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

def process_image(src_path: Path, dst_path: Path, resize_to=None, debug=False, roi_root: Path | None = None):
    """
    Load an image, find ALL duck bboxes in the (optional) ROI,
    crop each (with padding), optionally resize, and save multiple outputs.

    If no valid ducks found, fall back to single center-crop.
    If >4 ducks found, treat as faulty and fall back to center-crop.
    """
    img_bgr = cv2.imread(str(src_path))
    if img_bgr is None:
        print(f"[WARN] Could not read image: {src_path}")
        return

    # Camera name based on folder layout: .../timestamp/camX/live/image.jpg
    # src_path.parent.name      -> "live"
    # src_path.parents[1].name  -> "camX"  (camera folder)
    cam_name = src_path.parents[1].name

    # --- ROI selection + debug about which ROI is used ---
    if roi_root is not None:
        roi_json = roi_root / f"roi_{cam_name}.json"
        if debug:
            print(f"[DEBUG] Processing image: {src_path}")
            print(f"[DEBUG] Detected camera: '{cam_name}'")
            print(f"[DEBUG] Expected ROI file: {roi_json}")

        roi_poly = load_roi_for_camera(cam_name, roi_root, debug=debug)

        if debug:
            if roi_poly is None:
                print(f"[DEBUG] No valid ROI for camera '{cam_name}' → using FULL image.")
            else:
                print(f"[DEBUG] Using ROI for camera '{cam_name}' from: {roi_json}")
    else:
        roi_poly = None
        if debug:
            print(f"[DEBUG] No roi_root provided; using FULL image for camera '{cam_name}'.")

    # --- Find duck bounding boxes inside ROI (if any) ---
    bboxes = find_duck_bboxes(img_bgr, roi_poly=roi_poly, debug=debug)

    # Discard if too many detections (treat as faulty)
    if len(bboxes) > 4:
        if debug:
            print(f"[WARN] {len(bboxes)} bboxes detected (>4). Discarding reading and using center crop.")
        bboxes = []

    if not bboxes:
        # Fallback to center crop, single output
        if debug:
            print(f"[INFO] No valid duck bbox; center cropping: {src_path}")
        crop = center_crop_square(img_bgr)
        if resize_to is not None:
            crop = cv2.resize(crop, (resize_to, resize_to), interpolation=cv2.INTER_AREA)

        ensure_dir(dst_path.parent)
        success = cv2.imwrite(str(dst_path), crop)
        if not success:
            print(f"[WARN] Failed to write image: {dst_path}")
        return

    # If multiple bboxes (1–4), produce multiple files with suffixes
    stem = dst_path.stem
    ext  = dst_path.suffix

    for idx, (x, y, w, h, color_name) in enumerate(bboxes, start=1):
        crop = crop_with_padding(img_bgr, (x, y, w, h), padding_factor=1.2)
        if resize_to is not None:
            crop = cv2.resize(crop, (resize_to, resize_to), interpolation=cv2.INTER_AREA)

        out_name = f"{stem}_{idx}_{color_name}{ext}"
        out_path = dst_path.parent / out_name
        ensure_dir(out_path.parent)
        success = cv2.imwrite(str(out_path), crop)
        if not success:
            print(f"[WARN] Failed to write image: {out_path}")

    if debug:
        debug_img = img_bgr.copy()
        for (x, y, w, h, color_name) in bboxes:
            cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(debug_img, color_name, (x, y-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
        h0, w0 = debug_img.shape[:2]
        scale = 640 / float(w0)
        preview = cv2.resize(debug_img, (640, int(h0 * scale)))
        cv2.imshow("debug_multi_centered", preview)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def copy_and_crop_dataset(src_root: Path, dst_root: Path,
                          resize_to=None, debug=False, roi_root: Path | None = None):
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
            process_image(src_path, dst_path, resize_to=resize_to, debug=debug, roi_root=roi_root)


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

    parser.add_argument(
    "--roi_root",
    type=str,
    default=None,
    help="Directory containing ROI JSON files (roi_camX.json).",
    )

    args = parser.parse_args()

    roi_root_path = Path(args.roi_root).resolve() if args.roi_root else None

    copy_and_crop_dataset(
        src_root=Path(args.src_root),
        dst_root=Path(args.dst_root),
        resize_to=args.resize_to,
        debug=args.debug,
        roi_root=roi_root_path,
    )


if __name__ == "__main__":
    main()
