#!/usr/bin/env python3
import argparse
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image

import torch
import torch.nn.functional as F
from torchvision import transforms

from model import TinyConvNet


# Same preprocessing as train/eval: RGB 128x128, normalized to mean=0.5, std=0.5
TFM = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),  # [0,1], shape [3,H,W]
    transforms.Normalize(mean=[0.5, 0.5, 0.5],
                         std=[0.5, 0.5, 0.5]),
])


def load_image_tensor(path: Path, device: torch.device):
    """Load a single image file → 1x3x128x128 tensor."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception as e:
        print(f"[ERROR] Failed to open image {path}: {e}")
        return None

    x = TFM(img).unsqueeze(0)  # [1,3,128,128]
    return x.to(device)


def run_single_image(model, img_path: Path, device, threshold: float):
    """Run inference on a single image path and print result."""
    x = load_image_tensor(img_path, device)
    if x is None:
        return 1

    model.eval()
    with torch.no_grad():
        t0 = time.time()
        logits = model(x).view(-1)       # (1,)
        p = torch.sigmoid(logits)[0].item()
        t1 = time.time()

    label = "UNHEALTHY" if p >= threshold else "HEALTHY"
    ms = (t1 - t0) * 1000.0

    print(f"[RESULT] {label:9s} | p_unhealthy={p:.3f} | {ms:.1f} ms | {img_path}")
    return 0


def run_folder(model, dir_path: Path, device, threshold: float):
    """Run inference on all .jpg/.jpeg images in a folder with summary."""
    if not dir_path.is_dir():
        print(f"[ERROR] Not a directory: {dir_path}")
        return 1

    # Collect .jpg / .jpeg
    exts = {".jpg", ".jpeg", ".JPG", ".JPEG"}
    files = sorted(
        [p for p in dir_path.iterdir() if p.suffix in exts and p.is_file()]
    )

    if not files:
        print(f"[INFO] no JPEGs found in {dir_path}")
        return 0

    print(f"[INFO] Found {len(files)} image(s) in {dir_path}")

    n_healthy = 0
    n_unhealthy = 0
    n_err = 0
    probs = []

    t0 = time.time()
    for img_path in files:
        x = load_image_tensor(img_path, device)
        if x is None:
            print(f"[ERROR] failed | file={img_path}")
            n_err += 1
            continue

        model.eval()
        with torch.no_grad():
            s0 = time.time()
            logits = model(x).view(-1)
            p = torch.sigmoid(logits)[0].item()
            s1 = time.time()

        unhealthy = (p >= threshold)
        if unhealthy:
            n_unhealthy += 1
        else:
            n_healthy += 1

        probs.append(p)
        ms = (s1 - s0) * 1000.0

        print(f"[RESULT] {('UNHEALTHY' if unhealthy else 'HEALTHY'):9s} | "
              f"p_unhealthy={p:.3f} | {ms:.1f} ms | {img_path}")

    t1 = time.time()
    total_ms = (t1 - t0) * 1000.0
    n_ok = len(files) - n_err
    avg_p = float(np.mean(probs)) if probs else 0.0
    min_p = float(np.min(probs)) if probs else 0.0
    max_p = float(np.max(probs)) if probs else 0.0
    fps = (n_ok * 1000.0 / total_ms) if total_ms > 0 and n_ok > 0 else 0.0

    print("\n--- SUMMARY ---")
    print(f"files: {len(files)}  (ok={n_ok}, errors={n_err})")
    print(f"predicted: UNHEALTHY={n_unhealthy}, HEALTHY={n_healthy} (threshold={threshold:.2f})")
    if n_ok > 0:
        print(f"p_unhealthy: avg={avg_p:.3f}  min={min_p:.3f}  max={max_p:.3f}")
    print(f"time: total={total_ms:.1f} ms  avg={(total_ms/n_ok if n_ok else 0.0):.1f} ms/frame  fps={fps:.2f}")

    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Run TinyConvNet on a single image or a folder of images (Python version of pi_infer)."
    )
    ap.add_argument("path", type=str,
                    help="Image file path OR directory of images (.jpg/.jpeg)")
    ap.add_argument("--ckpt", type=str,
                    default=os.path.join(os.path.dirname(__file__), "..", "weights", "tinyconvnet_best.pt"),
                    help="Path to tinyconvnet_best.pt checkpoint")
    ap.add_argument("--device", type=str,
                    default="cuda" if torch.cuda.is_available() else "cpu",
                    help="Device to run on: cuda or cpu")
    ap.add_argument("--threshold", type=float, default=0.30,
                    help="Threshold on p_unhealthy to call UNHEALTHY")
    args = ap.parse_args()

    device = torch.device(args.device)
    ckpt_path = Path(args.ckpt)

    if not ckpt_path.is_file():
        print(f"[ERROR] checkpoint not found: {ckpt_path}")
        return 1

    # Load model + weights
    ckpt = torch.load(ckpt_path, map_location=device)
    model = TinyConvNet().to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    target_path = Path(args.path)
    if target_path.is_dir():
        return run_folder(model, target_path, device, args.threshold)
    else:
        return run_single_image(model, target_path, device, args.threshold)


if __name__ == "__main__":
    raise SystemExit(main())
