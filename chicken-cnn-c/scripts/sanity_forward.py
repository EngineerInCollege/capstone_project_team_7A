# scripts/sanity_forward.py
import argparse, os, numpy as np, torch
from PIL import Image
from torchvision import transforms
from model import TinyConvNet

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--ckpt", default=os.path.join(os.path.dirname(__file__), "..", "weights", "tinyconvnet_best.pt"))
    args = ap.parse_args()

    tfm = transforms.Compose([
        transforms.Grayscale(1),
        transforms.Resize((128,128)),
        transforms.ToTensor(),
        transforms.Normalize([0.5],[0.5])
    ])

    img = Image.open(args.img).convert("RGB")
    x = tfm(img).unsqueeze(0)  # (1,1,128,128)

    model = TinyConvNet()
    ckpt = torch.load(args.ckpt, map_location="cpu")["state_dict"]
    model.load_state_dict(ckpt)
    model.eval()

    with torch.no_grad():
        prob, logit = model(x)

    print(f"Python sanity forward → prob_unhealthy={prob.item():.6f}, logit={logit.item():.6f}")
    # Save the preprocessed tensor for C to ingest if useful:
    np.save(os.path.join(os.path.dirname(__file__), "..", "weights", "sanity_input.npy"), x.numpy())
    print("Saved preprocessed tensor to weights/sanity_input.npy")

if __name__ == "__main__":
    main()
