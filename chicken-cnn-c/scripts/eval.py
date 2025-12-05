# scripts/eval.py
import argparse, os
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix, roc_auc_score
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from model import TinyConvNet

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_root", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--ckpt", default=os.path.join(os.path.dirname(__file__), "..", "weights", "tinyconvnet_best.pt"))
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()

    ckpt = torch.load(args.ckpt, map_location="cpu")
    classes = ckpt["classes"]
    print("Class index mapping:", dict(enumerate(classes)))

    tfms = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((128,128)),
        transforms.ToTensor(),
        transforms.Normalize([0.5],[0.5])
    ])
    ds = datasets.ImageFolder(os.path.join(args.data_root, "test"), transform=tfms)
    loader = DataLoader(ds, batch_size=32, shuffle=False)

    model = TinyConvNet().to(args.device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    probs_all, y_all = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(args.device)
            logits = model(x)                     # forward returns raw logits
            probs = torch.sigmoid(logits)         # convert logits → probabilities
            probs_all.append(probs.cpu().numpy())
            y_all.append(y.numpy())

    probs = np.concatenate(probs_all)
    y = np.concatenate(y_all)

    preds = (probs >= 0.5).astype(np.int64)
    acc = accuracy_score(y, preds)
    p, r, f1, _ = precision_recall_fscore_support(y, preds, average='binary', zero_division=0)
    cm = confusion_matrix(y, preds)
    try:
        auc = roc_auc_score(y, probs)
    except Exception:
        auc = float("nan")
    print(f"[TEST] acc={acc:.3f} p={p:.3f} r={r:.3f} f1={f1:.3f} auc={auc:.3f}\nConfusion:\n{cm}")

if __name__ == "__main__":
    main()
