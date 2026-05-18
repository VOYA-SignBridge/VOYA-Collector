#!/usr/bin/env python
import torch
import json

ckpt_path = "realtime_service/config/checkpoints/tcn_dialect-hoa-de_20260515_131050.pt"
ckpt = torch.load(ckpt_path, map_location="cpu")

idx_to_label = ckpt.get("idx_to_label")
print(f"idx_to_label type: {type(idx_to_label).__name__}")
print(f"Length: {len(idx_to_label)}")
print()

print("=" * 80)
print("FIRST 10 ENTRIES:")
print("=" * 80)

if isinstance(idx_to_label, dict):
    count = 0
    for key, value in idx_to_label.items():
        if count >= 10:
            break
        print(f"\n[Key: {key}]:")
        print(json.dumps(value, ensure_ascii=False, indent=2))
        count += 1

    print("\n" + "=" * 80)
    print("FIELD ANALYSIS:")
    print("=" * 80)
    first_value = next(iter(idx_to_label.values())) if idx_to_label else None
    if isinstance(first_value, dict):
        print(f"Value type: dict")
        print(f"Sample fields: {list(first_value.keys())}")
        print(f"  - Has 'label_original': {'label_original' in first_value}")
        print(f"  - Has 'label_key': {'label_key' in first_value}")
        for k, v in first_value.items():
            print(f"    - {k}: {repr(v)}")
    elif isinstance(first_value, str):
        print(f"Value type: string")
        print(f"Sample: {first_value}")

elif isinstance(idx_to_label, list):
    for i in range(min(10, len(idx_to_label))):
        entry = idx_to_label[i]
        print(f"\n[{i}]: {json.dumps(entry, ensure_ascii=False, indent=2)}")

print("\n" + "=" * 80)
print("TOTAL CLASSES: ", len(idx_to_label))
print("=" * 80)
