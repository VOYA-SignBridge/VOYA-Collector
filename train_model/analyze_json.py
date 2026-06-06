import json
from collections import defaultdict

with open('dataset_info_train_val_test.json', 'r', encoding='utf-8', errors='ignore') as f:
    samples = json.load(f)

print(f"Total entries in JSON: {len(samples)}")

if len(samples) > 0:
    print("Sample format:", list(samples[0].keys()))

split_counts = defaultdict(lambda: defaultdict(int))
for s in samples:
    label = s.get('label_slug') or s.get('label') or s.get('class_name') or s.get('folder_name', 'unknown')
    split = s.get('split', 'unknown')
    split_counts[label][split] += 1

with open('json_output.txt', 'w', encoding='utf-8') as out:
    out.write("--- Phân Tích Dataset (JSON) ---\n")
    out.write(f"{'Nhãn (Label)':<25} | {'Train':<7} | {'Val':<7} | {'Test':<7} | {'Tổng':<6}\n")
    out.write("-" * 65 + "\n")

    all_labels = sorted(split_counts.keys())
    total_tr, total_va, total_te = 0, 0, 0
    for label in all_labels:
        tr = split_counts[label].get('train', 0)
        va = split_counts[label].get('val', 0)
        te = split_counts[label].get('test', 0)
        total = tr + va + te
        
        total_tr += tr
        total_va += va
        total_te += te
        
        out.write(f"{label:<25} | {tr:<7} | {va:<7} | {te:<7} | {total:<6}\n")

    out.write("-" * 65 + "\n")
    out.write(f"{'TỔNG CỘNG':<25} | {total_tr:<7} | {total_va:<7} | {total_te:<7} | {total_tr+total_va+total_te:<6}\n")
