# scripts/resplit_stratified.py
import os, shutil, argparse, random
from pathlib import Path
from collections import defaultdict
from sklearn.model_selection import train_test_split

def list_images(root):
    root = Path(root)
    items = []
    for split in ["train","val","test"]:
        split_dir = root / split
        if not split_dir.exists(): 
            continue
        for cls in sorted([d for d in split_dir.iterdir() if d.is_dir()]):
            for p in cls.glob("*"):
                if p.suffix.lower() in [".jpg",".jpeg",".png",".bmp",".webp",".tif",".tiff"]:
                    items.append((str(p), cls.name))   # (path, class)
    return items

def write_split(items, out_root, mode="copy"):
    out_root = Path(out_root)
    for split, cls, src in items:
        dst_dir = out_root / split / cls
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / Path(src).name
        if mode == "move":
            shutil.move(src, dst)
        else:
            shutil.copy2(src, dst)

def count_per_class(items):
    c = defaultdict(int)
    for _, cls in items:
        c[cls]+=1
    return dict(c)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_root", default=str(Path(__file__).resolve().parents[1] / "data"))
    ap.add_argument("--out_root",  default=str(Path(__file__).resolve().parents[1] / "data_new"))
    ap.add_argument("--train", type=float, default=0.70)
    ap.add_argument("--val",   type=float, default=0.15)
    ap.add_argument("--test",  type=float, default=0.15)
    ap.add_argument("--seed",  type=int,   default=42)
    ap.add_argument("--mode",  choices=["copy","move"], default="copy",
                    help="copy keeps originals; move relocates files")
    ap.add_argument("--min_val_per_class", type=int, default=3)
    ap.add_argument("--min_test_per_class", type=int, default=3)
    args = ap.parse_args()

    assert abs(args.train + args.val + args.test - 1.0) < 1e-6, "splits must sum to 1.0"
    random.seed(args.seed)

    all_items = list_images(args.data_root)
    assert all_items, f"No images found under {args.data_root}"

    # Group by class
    by_class = defaultdict(list)
    for p, cls in all_items:
        by_class[cls].append(p)

    classes = sorted(by_class.keys())
    print("Classes:", classes)
    totals = {cls: len(by_class[cls]) for cls in classes}
    print("Total per class:", totals)

    # First split TRAIN vs (VAL+TEST) per class (stratified by design)
    train_items, holdout_items = [], []
    y_all, X_all = [], []
    # Flatten lists for stratify
    for cls in classes:
        for p in by_class[cls]:
            X_all.append((p, cls))
            y_all.append(cls)

    X_tr, X_hold, y_tr, y_hold = train_test_split(
        X_all, y_all, train_size=args.train, stratify=y_all, random_state=args.seed
    )

    # Now split holdout into VAL and TEST, stratified
    val_ratio_of_hold = args.val / (args.val + args.test + 1e-12)
    X_val, X_test, y_val, y_test = train_test_split(
        X_hold, y_hold, train_size=val_ratio_of_hold, stratify=y_hold, random_state=args.seed
    )

    # Check minimums; if too small, print advice and exit gracefully
    from collections import Counter
    def per_class_count(arr):
        return dict(Counter([cls for _, cls in arr]))

    val_counts = per_class_count(X_val)
    test_counts = per_class_count(X_test)
    print("VAL per class:", val_counts)
    print("TEST per class:", test_counts)

    ok = True
    for cls in classes:
        if val_counts.get(cls, 0) < args.min_val_per_class:
            print(f"[WARN] val has only {val_counts.get(cls,0)} of class '{cls}' "
                  f"(min {args.min_val_per_class}). Consider lowering test/val %, or growing data.")
            ok = False
        if test_counts.get(cls, 0) < args.min_test_per_class:
            print(f"[WARN] test has only {test_counts.get(cls,0)} of class '{cls}' "
                  f"(min {args.min_test_per_class}). Consider lowering test %, or growing data.")
            ok = False

    if not ok:
        print("Aborting write to avoid creating an unbalanced holdout. Adjust flags and retry.")
        return

    # Record the split
    out_root = Path(args.out_root)
    if out_root.exists():
        print(f"[NOTE] Output dir {out_root} already exists; new files will be added.")
    write_plan = []
    for p, cls in X_tr:   write_plan.append(("train", cls, p))
    for p, cls in X_val:  write_plan.append(("val",   cls, p))
    for p, cls in X_test: write_plan.append(("test",  cls, p))

    write_split(write_plan, out_root, mode=args.mode)
    print(f"Done. Wrote stratified split to: {out_root}")
    print("Counts:")
    from collections import Counter
    print("  train:", Counter([cls for _, cls, _ in write_plan if _ == "train"]))
    print("  val:  ", Counter([cls for _, cls, _ in write_plan if _ == "val"]))
    print("  test: ", Counter([cls for _, cls, _ in write_plan if _ == "test"]))

if __name__ == "__main__":
    main()
