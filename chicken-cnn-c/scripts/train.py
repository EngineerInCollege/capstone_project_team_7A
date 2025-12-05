# scripts/train.py
import argparse, os, random
import numpy as np
from pathlib import Path
from tqdm import tqdm
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import datasets, transforms

from model import TinyConvNet  # ensure model.forward returns logits (no sigmoid)

def seed_everything(seed=42):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)

def get_loaders(data_root, img_size=128, batch_size=32):
    train_tfms = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((img_size, img_size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.RandomAffine(degrees=5, translate=(0.02,0.02), scale=(0.95,1.05)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5])  # [-1,1]
    ])
    eval_tfms = transforms.Compose([
        transforms.Grayscale(num_output_channels=1),
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5], std=[0.5])
    ])

    train_dir = os.path.join(data_root, "train")
    val_dir   = os.path.join(data_root, "val")

    train_ds = datasets.ImageFolder(train_dir, transform=train_tfms)
    val_ds   = datasets.ImageFolder(val_dir,   transform=eval_tfms)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)
    return train_loader, val_loader, train_ds.classes

@torch.no_grad()
def evaluate(model, loader, device, threshold=0.5):
    model.eval()
    all_probs, all_targets = [], []
    for x, y in loader:
        x = x.to(device)
        logits = model(x)                # (B,)
        probs = torch.sigmoid(logits)    # convert for metrics
        all_probs.append(probs.cpu())
        all_targets.append(y.cpu())
    probs = torch.cat(all_probs).numpy()
    y = torch.cat(all_targets).numpy()
    preds = (probs >= threshold).astype(np.int64)

    acc = accuracy_score(y, preds)
    p, r, f1, _ = precision_recall_fscore_support(y, preds, average='binary', zero_division=0)
    cm = confusion_matrix(y, preds)
    return acc, p, r, f1, cm, probs, y

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_root", default=str(Path(__file__).resolve().parents[1] / "data"))
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch_size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight_decay", type=float, default=1e-4)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "weights"))
    args = ap.parse_args()

    seed_everything(42)
    os.makedirs(args.out, exist_ok=True)

    train_loader, val_loader, classes = get_loaders(args.data_root, img_size=128, batch_size=args.batch_size)
    assert set(classes) == {"healthy", "unhealthy"} or set(classes) == {"unhealthy","healthy"}, \
        f"Expected classes healthy/unhealthy, got {classes}"

    device = args.device
    model = TinyConvNet().to(device)     # forward returns logits

    # ---- Class weighting (works across torchvision versions) ----
    train_ds = train_loader.dataset
    targets = [lbl for _, lbl in train_ds.samples]     # [(path, label), ...]
    num_healthy   = sum(1 for t in targets if t == 0)
    num_unhealthy = sum(1 for t in targets if t == 1)
    pos_weight_val = num_healthy / max(num_unhealthy, 1)  # weight for class-1 (unhealthy)
    pos_weight = torch.tensor([pos_weight_val], dtype=torch.float32, device=device)
    print(f"Class weighting → pos_weight={pos_weight_val:.2f} (healthy={num_healthy}, unhealthy={num_unhealthy})")

    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best_f1, best_state = -1.0, None
    bad_epochs = 0

    for epoch in range(1, args.epochs+1):
        model.train()
        running = 0.0
        for x, y in tqdm(train_loader, desc=f"Epoch {epoch}/{args.epochs}"):
            x = x.to(device)
            y = y.float().to(device)         # targets {0,1} as float for BCEWithLogitsLoss
            opt.zero_grad()
            logits = model(x)                 # (B,)
            loss = criterion(logits, y)
            loss.backward()
            opt.step()
            running += loss.item() * x.size(0)

        train_loss = running / len(train_loader.dataset)

        acc, p, r, f1, cm, _, _ = evaluate(model, val_loader, device, threshold=0.5)
        print(f"[VAL] loss={train_loss:.4f} acc={acc:.3f} p={p:.3f} r={r:.3f} f1={f1:.3f}\nConfusion:\n{cm}")

        if f1 > best_f1:
            best_f1, best_state, bad_epochs = f1, model.state_dict(), 0
        else:
            bad_epochs += 1

        if bad_epochs >= args.patience:
            print("Early stopping.")
            break

    # Save best checkpoint
    ckpt_path = os.path.join(args.out, "tinyconvnet_best.pt")
    torch.save({"state_dict": best_state, "classes": classes}, ckpt_path)
    print(f"Saved best model → {ckpt_path}")

if __name__ == "__main__":
    main()
