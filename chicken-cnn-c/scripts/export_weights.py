# scripts/export_weights.py
import os, struct, argparse
import numpy as np
import torch

from model import TinyConvNet

def write_float32_bin(path, array_1d_float32):
    array_1d_float32 = np.asarray(array_1d_float32, dtype=np.float32).ravel(order="C")
    array_1d_float32.tofile(path)

def export(ckpt_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ckpt = torch.load(ckpt_path, map_location="cpu")
    sd = ckpt["state_dict"]

    # load into a model just to be sure shapes are correct (optional)
    m = TinyConvNet()
    m.load_state_dict(sd)

    # Conv layers
    for name in ["c1","c2","c3"]:
        W = sd[f"{name}.weight"].numpy()  # shape [outC, inC, kH, kW] (OIHW) -> C order
        b = sd[f"{name}.bias"].numpy()    # shape [outC]
        out_path = os.path.join(out_dir, f"{name}.bin")
        with open(out_path, "wb") as f:
            # weights first
            np.asarray(W, dtype=np.float32).ravel(order="C").tofile(f)
            # then biases
            np.asarray(b, dtype=np.float32).ravel(order="C").tofile(f)
        print(f"Wrote {out_path}: W {W.shape} + b {b.shape}")

    # FC layer (32 -> 1)
    W_fc = sd["fc.weight"].numpy()  # shape [1, 32]
    b_fc = sd["fc.bias"].numpy()    # shape [1]
    # Flatten to length 32
    W_fc_flat = W_fc.reshape(-1)    # [32]
    out_fc = os.path.join(out_dir, "fc.bin")
    with open(out_fc, "wb") as f:
        np.asarray(W_fc_flat, dtype=np.float32).tofile(f)
        np.asarray(b_fc, dtype=np.float32).tofile(f)  # one float32
    print(f"Wrote {out_fc}: W {W_fc_flat.shape} + b {(b_fc.shape,)}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=os.path.join(os.path.dirname(__file__), "..", "weights", "tinyconvnet_best.pt"))
    ap.add_argument("--out",  default=os.path.join(os.path.dirname(__file__), "..", "weights"))
    args = ap.parse_args()
    export(args.ckpt, args.out)
