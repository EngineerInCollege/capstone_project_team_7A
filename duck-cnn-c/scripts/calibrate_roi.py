#!/usr/bin/env python3
import json
from pathlib import Path

import cv2
import numpy as np

points = []
img = None
clone = None

def mouse_callback(event, x, y, flags, param):
    global points, img
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        # draw a small circle where user clicked
        cv2.circle(img, (x, y), 4, (0, 255, 0), -1)
        cv2.imshow("Calibrate ROI", img)

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Click 4 points to define ROI around the scale."
    )
    parser.add_argument("--image", required=True,
                        help="Path to a sample image from this camera.")
    parser.add_argument("--out", required=True,
                        help="Path to save ROI JSON (e.g. roi_cam1.json).")
    args = parser.parse_args()

    global img, clone, points
    img_path = Path(args.image)
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"ERROR: could not read image {img_path}")
        return

    clone = img.copy()
    points = []

    cv2.namedWindow("Calibrate ROI")
    cv2.setMouseCallback("Calibrate ROI", mouse_callback)

    print("Instructions:")
    print(" - Click 4 points around the SCALE area in order (rough rectangle).")
    print(" - Press 'r' to reset if you mess up.")
    print(" - Press 'q' or ESC to quit/save once 4 points are chosen.")

    while True:
        cv2.imshow("Calibrate ROI", img)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('r'):
            # reset points
            points = []
            img = clone.copy()
            print("Reset points.")
        elif key in (27, ord('q')):  # ESC or 'q'
            break

        # optionally draw polygon once 4 points are selected
        if len(points) == 4:
            img = clone.copy()
            pts = np.array(points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(img, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
            cv2.imshow("Calibrate ROI", img)

    cv2.destroyAllWindows()

    if len(points) != 4:
        print("Not enough points selected; ROI not saved.")
        return

    roi_data = {"points": points}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(roi_data, f, indent=2)

    print(f"Saved ROI with 4 points to {out_path}")

if __name__ == "__main__":
    main()
