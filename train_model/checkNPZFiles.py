import numpy as np
import pandas as pd
import os
import json
import csv
from pathlib import Path
import hashlib

ROOT = r"E:\CTU_ProjectOutside\VOYA-Collector"

CSV_FILES = [
    (r"E:\CTU_ProjectOutside\VOYA-Collector\processed\splits\train.csv", "train"),
    (r"E:\CTU_ProjectOutside\VOYA-Collector\processed\splits\val.csv", "val"),
    (r"E:\CTU_ProjectOutside\VOYA-Collector\processed\splits\test.csv", "test"),
]

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def get_file_hash(file_path):
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()[:8]
    except Exception:
        return "ERROR"


def load_npz_meta(data):
    if "meta" not in data:
        return {}

    meta = data["meta"]

    if isinstance(meta, np.ndarray):
        if meta.dtype == object:
            if meta.size == 1:
                value = meta.item()
                if isinstance(value, dict):
                    return value
                return {"raw_meta": value}
            return {"raw_meta": meta.tolist()}

        if meta.shape == ():
            value = meta.item()
            if isinstance(value, dict):
                return value
            return {"raw_meta": value}

    if isinstance(meta, dict):
        return meta

    return {"raw_meta": str(meta)}


def analyze_npz_file(file_path):
    info = {
        "file": os.path.basename(file_path),
        "path": file_path,
        "exists": os.path.exists(file_path),
        "size_kb": os.path.getsize(file_path) / 1024 if os.path.exists(file_path) else 0,
        "file_hash": get_file_hash(file_path) if os.path.exists(file_path) else None,
        "error": None,
        "npz_keys": [],
        "meta": {},
        "source_type": "unknown",
        "swap_handedness": "unknown",
        "is_normalized": False,
        "processing_steps": [],
    }

    if not info["exists"]:
        info["error"] = "File not found"
        return info

    try:
        data = np.load(file_path, allow_pickle=True)
        info["npz_keys"] = list(data.keys())

        key = "sequence" if "sequence" in data else (
            "features" if "features" in data else list(data.keys())[0]
        )
        x = np.asarray(data[key], dtype=np.float32)

        info["shape"] = list(x.shape)
        info["n_frames"] = int(x.shape[0])
        info["n_features"] = int(x.shape[1]) if x.ndim > 1 else 1

        info["data_min"] = float(x.min())
        info["data_max"] = float(x.max())
        info["data_mean"] = float(x.mean())
        info["data_std"] = float(x.std())
        info["data_range"] = float(info["data_max"] - info["data_min"])

        info["meta"] = load_npz_meta(data)

        source_type = info["meta"].get("source_type") or info["meta"].get("source")
        info["source_type"] = source_type or "unknown"

        swap_flag = (
            info["meta"].get("swap_handedness")
            if "swap_handedness" in info["meta"]
            else info["meta"].get("swapped_hands")
        )
        if swap_flag is None:
            info["swap_handedness"] = "unknown"
        else:
            info["swap_handedness"] = bool(swap_flag)

        info["is_normalized"] = bool(
            info["data_min"] >= -0.01 and info["data_max"] <= 1.01
        )

        left_hand = x[:, :63].reshape(x.shape[0], 21, 3) if x.shape[1] >= 63 else None
        right_hand = x[:, 63:126].reshape(x.shape[0], 21, 3) if x.shape[1] >= 126 else None

        if left_hand is not None:
            left_activity = np.linalg.norm(left_hand, axis=(1, 2))
            info["left_hand_activity"] = {
                "mean": float(left_activity.mean()),
                "std": float(left_activity.std()),
                "max": float(left_activity.max()),
                "min": float(left_activity.min()),
                "n_active_frames": int((left_activity > 0.01).sum()),
            }

        if right_hand is not None:
            right_activity = np.linalg.norm(right_hand, axis=(1, 2))
            info["right_hand_activity"] = {
                "mean": float(right_activity.mean()),
                "std": float(right_activity.std()),
                "max": float(right_activity.max()),
                "min": float(right_activity.min()),
                "n_active_frames": int((right_activity > 0.01).sum()),
            }

        n_nan = int(np.isnan(x).sum())
        n_inf = int(np.isinf(x).sum())
        info["n_nan"] = n_nan
        info["n_inf"] = n_inf
        info["has_invalid"] = bool(n_nan > 0 or n_inf > 0)

        if x.shape[0] > 1:
            velocity = np.linalg.norm(x[1:] - x[:-1], axis=1)
            info["velocity_mean"] = float(velocity.mean())
            info["velocity_max"] = float(velocity.max())

        processing = []

        if info["source_type"] != "unknown":
            processing.append(f"Source: {info['source_type']}")

        if info["swap_handedness"] != "unknown":
            processing.append(f"Swap handedness: {info['swap_handedness']}")

        if "augment_id" in info["meta"]:
            processing.append(f"Augment ID: {info['meta'].get('augment_id')}")

        if "created_at" in info["meta"]:
            processing.append(f"Created at: {info['meta'].get('created_at')}")

        if "canonicalize_mirror" in info["meta"]:
            processing.append(f"Canonicalize mirror: {info['meta'].get('canonicalize_mirror')}")

        if info["is_normalized"]:
            processing.append("Normalization: [0, 1]")
        elif info["data_min"] < -1 or info["data_max"] > 1:
            processing.append("Normalization: raw coordinates")
        else:
            processing.append("Normalization: normalized")

        if info["n_nan"] == 0 and info["n_inf"] == 0:
            processing.append("Data Quality: No NaN/Inf values")
        else:
            processing.append(f"Data Quality: Found {n_nan} NaN + {n_inf} Inf")

        if "velocity_max" in info and info["velocity_max"] < 0.1:
            processing.append("Smoothing: Applied (low velocity)")
        elif "velocity_max" in info and info["velocity_max"] > 0.5:
            processing.append("Smoothing: Not applied (high velocity)")

        if left_hand is not None and right_hand is not None:
            left_present = (left_hand.reshape(x.shape[0], -1).std(axis=1) > 0.01).sum() > 30
            right_present = (right_hand.reshape(x.shape[0], -1).std(axis=1) > 0.01).sum() > 30

            if left_present and right_present:
                processing.append("Hands: Both present")
            elif left_present:
                processing.append("Hands: Only LEFT")
            elif right_present:
                processing.append("Hands: Only RIGHT")
            else:
                processing.append("Hands: Both missing")

        info["processing_steps"] = processing

    except Exception as e:
        info["error"] = str(e)

    return info


def load_all_samples_from_csvs():
    samples = []
    for csv_path, split in CSV_FILES:
        if not os.path.exists(csv_path):
            continue

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rel_path = row.get("file_path", "").lstrip("/")
                full_path = os.path.join(ROOT, rel_path) if rel_path else ""
                row["split"] = split
                row["full_path"] = full_path
                samples.append(row)

    return samples


def export_data_info_csv(output_file="dataset_info_train_val_test.csv"):
    samples = load_all_samples_from_csvs()

    print(f"{Colors.OKBLUE}Loading samples from train/val/test...{Colors.ENDC}")
    print(f"{Colors.OKGREEN}Found {len(samples)} samples{Colors.ENDC}")

    all_info = []

    for idx, row in enumerate(samples):
        file_path = row["full_path"]
        sample_uid = row.get("sample_uid", "")

        print(f"  [{idx+1}/{len(samples)}] Analyzing: {sample_uid}...", end=" ")
        info = analyze_npz_file(str(file_path))

        info.update({
            "split": row.get("split", ""),
            "sample_uid": sample_uid,
            "label_slug": row.get("label_slug", ""),
            "language": row.get("language", ""),
            "dialect": row.get("dialect", ""),
            "augment_id_csv": row.get("augment_id", ""),
            "user_id": row.get("user_id", ""),
            "created_at_csv": row.get("created_at", ""),
            "source_type_csv": row.get("source_type", ""),
            "file_path_csv": row.get("file_path", ""),
        })

        all_info.append(info)
        print(f"{Colors.OKGREEN}{'✓' if not info.get('error') else '✗'}{Colors.ENDC}")

    df_info = pd.DataFrame(all_info)

    if not df_info.empty:
        df_info["processing_steps_str"] = df_info["processing_steps"].apply(
            lambda x: " | ".join(x) if isinstance(x, list) else ""
        )

    csv_columns = [
        "split",
        "sample_uid",
        "label_slug",
        "language",
        "dialect",
        "source_type",
        "swap_handedness",
        "augment_id_csv",
        "user_id",
        "created_at",
        "file",
        "size_kb",
        "file_hash",
        "shape",
        "n_frames",
        "n_features",
        "data_min",
        "data_max",
        "data_mean",
        "data_std",
        "is_normalized",
        "has_invalid",
        "processing_steps_str",
        "meta",
        "error",
    ]

    df_csv = df_info[[col for col in csv_columns if col in df_info.columns]]
    df_csv.to_csv(output_file, index=False, encoding="utf-8-sig")

    print(f"\n{Colors.OKGREEN}Exported to: {output_file}{Colors.ENDC}")
    print(f"  Rows: {len(df_csv)}")

    return df_info


def export_data_info_json(output_file="dataset_info_train_val_test.json"):
    samples = load_all_samples_from_csvs()
    all_data = []

    for idx, row in enumerate(samples):
        file_path = row["full_path"]
        sample_uid = row.get("sample_uid", "")

        print(f"  [{idx+1}/{len(samples)}] Analyzing: {sample_uid}...", end=" ")
        info = analyze_npz_file(str(file_path))

        info.update({
            "split": row.get("split", ""),
            "sample_uid": sample_uid,
            "label_slug": row.get("label_slug", ""),
            "language": row.get("language", ""),
            "dialect": row.get("dialect", ""),
            "augment_id_csv": row.get("augment_id", ""),
            "user_id": row.get("user_id", ""),
            "created_at_csv": row.get("created_at", ""),
            "source_type_csv": row.get("source_type", ""),
            "file_path_csv": row.get("file_path", ""),
        })

        all_data.append(info)
        print(f"{Colors.OKGREEN}{'✓' if not info.get('error') else '✗'}{Colors.ENDC}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

    print(f"\n{Colors.OKGREEN}Exported to: {output_file}{Colors.ENDC}")
    print(f"  Total samples: {len(all_data)}")

    return all_data


def print_summary_stats(df_info):
    print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}DATASET SUMMARY STATISTICS{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}")

    if df_info.empty:
        print("No data to summarize")
        return

    df_valid = df_info[df_info["error"].isna()]

    print(f"\n{Colors.OKGREEN}Valid files: {len(df_valid)}/{len(df_info)}{Colors.ENDC}")
    print(f"  Total size: {df_valid['size_kb'].sum()/1024:.1f} MB")

    print(f"\n{Colors.OKBLUE}Data Range:{Colors.ENDC}")
    print(f"  Min values: {df_valid['data_min'].min():.4f} ~ {df_valid['data_min'].max():.4f}")
    print(f"  Max values: {df_valid['data_max'].min():.4f} ~ {df_valid['data_max'].max():.4f}")
    print(f"  Normalized: {(df_valid['is_normalized'] == True).sum()}/{len(df_valid)}")

    print(f"\n{Colors.WARNING}Data Quality:{Colors.ENDC}")
    invalid_count = (df_valid["has_invalid"] == True).sum()
    print(f"  Files with NaN/Inf: {invalid_count}/{len(df_valid)}")

    print(f"\n{Colors.OKCYAN}Augmentation:{Colors.ENDC}")
    if "augment_id_csv" in df_valid.columns:
        aug_dist = df_valid["augment_id_csv"].value_counts().sort_index()
        for aug_id, count in aug_dist.items():
            print(f"  Aug {aug_id}: {count} samples")

    print(f"\n{Colors.OKCYAN}By Label:{Colors.ENDC}")
    label_dist = df_valid["label_slug"].value_counts()
    for label, count in label_dist.head(10).items():
        print(f"  {label}: {count}")
    if len(label_dist) > 10:
        print(f"  ... and {len(label_dist)-10} more labels")

    print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def main():
    print(f"\n{Colors.BOLD}{Colors.HEADER}VOYA DATASET INFO EXPORTER{Colors.ENDC}")
    print(f"{Colors.BOLD}Analyzing train/val/test datasets...{Colors.ENDC}\n")

    df_info = export_data_info_csv("dataset_info_train_val_test.csv")
    print()
    export_data_info_json("dataset_info_train_val_test.json")

    print_summary_stats(df_info)


if __name__ == "__main__":
    main()