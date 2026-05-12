import json
import time
from pathlib import Path
import torch
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "processed" / "train_utils" / "outputs"

# find newest json summary
jsons = sorted(OUT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
if not jsons:
    print("No summary json found in", OUT_DIR)
    sys.exit(1)
summary_path = jsons[0]
print("Using summary:", summary_path.name)
summary = json.loads(summary_path.read_text(encoding="utf-8"))
ckpt_path = Path(summary.get("checkpoint", ""))
if not ckpt_path.exists():
    # try relative
    ckpt_path = OUT_DIR / ckpt_path.name
if not ckpt_path.exists():
    print("Checkpoint not found:", ckpt_path)
    sys.exit(1)
print("Using checkpoint:", ckpt_path.name)

# load checkpoint
ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
# support different checkpoint layouts
in_dim = ckpt.get("in_dim") or summary.get("in_dim") or summary.get("config", {}).get("in_dim")
num_classes = ckpt.get("num_classes") or summary.get("num_classes") or summary.get("config", {}).get("num_classes")
cfg = summary.get("config", {})
if in_dim is None or num_classes is None:
    print("Missing in_dim or num_classes in checkpoint/summary")
    sys.exit(1)

# import model class
try:
    from train_model.train_utils.train_tcn import TCNClassifier
except Exception:
    sys.path.append(str(ROOT))
    from train_model.train_utils.train_tcn import TCNClassifier

model = TCNClassifier(
    in_dim=int(in_dim),
    num_classes=int(num_classes),
    channels=int(cfg.get("channels", 64)),
    levels=int(cfg.get("levels", 3)),
    kernel_size=int(cfg.get("kernel_size", 5)),
    dropout=float(cfg.get("dropout", 0.3)),
)
state = ckpt.get("model_state") or ckpt
model.load_state_dict(state)
model.eval()

device = torch.device("cpu")
model.to(device)

def measure(bs, seq_len=60, runs=200, warmup=10):
    X = torch.randn(bs, seq_len, int(in_dim), dtype=torch.float32, device=device)
    lengths = torch.full((bs,), seq_len, dtype=torch.long, device=device)
    # warmup
    with torch.no_grad():
        for _ in range(warmup):
            _ = model(X, lengths)
    # measure
    times = []
    with torch.no_grad():
        for _ in range(runs):
            t0 = time.perf_counter()
            _ = model(X, lengths)
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000.0)
    avg_ms = sum(times) / len(times)
    return avg_ms, avg_ms / bs

results = {}
for bs in (1, 32):
    runs = 500 if bs == 1 else 200
    avg_ms, per_seq = measure(bs, seq_len=60, runs=runs, warmup=20)
    results[f"batch_{bs}"] = {"avg_ms": avg_ms, "per_sequence_ms": per_seq}

import pprint
pprint.pprint(results)

# print a concise line
print(f"Latest checkpoint: {ckpt_path.name}")
for k, v in results.items():
    print(f"{k}: avg {v['avg_ms']:.3f} ms per forward, {v['per_sequence_ms']:.3f} ms/sequence")
