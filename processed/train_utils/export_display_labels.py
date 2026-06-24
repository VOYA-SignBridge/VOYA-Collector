"""
export_display_labels.py
------------------------
Tạo file <model_name>_display_labels.json bên cạnh file .tflite tương ứng.

Cách dùng:
  python processed/train_utils/export_display_labels.py
  python processed/train_utils/export_display_labels.py --model outputs/tcn_20260624_232642.tflite
  python processed/train_utils/export_display_labels.py --model outputs/tcn_20260624_232642.tflite --labels dataset/labels.csv

Kết quả:
  outputs/tcn_20260624_232642_display_labels.json
  Nội dung: { "0": "rang muối", "1": "tôm", ... }
"""

import argparse
import csv
import json
from pathlib import Path


def find_latest_tflite(outputs_dir: Path) -> Path:
    """Tìm file .tflite mới nhất trong thư mục outputs."""
    files = sorted(outputs_dir.glob("*.tflite"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"Không tìm thấy file .tflite nào trong: {outputs_dir}")
    return files[0]


def load_slug_to_original(labels_csv: Path) -> dict:
    """Đọc labels.csv và trả về dict {slug: label_original}."""
    mapping = {}
    with labels_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            slug = (row.get("slug") or "").strip()
            original = (row.get("label_original") or "").strip()
            if slug and original:
                mapping[slug] = original
    return mapping


def build_display_labels(tflite_path: Path, labels_csv: Path) -> dict:
    """
    Đọc label_map từ file .json cùng tên với .tflite,
    tra tên tiếng Việt từ labels.csv,
    trả về dict {index_str: display_name}.
    """
    json_path = tflite_path.with_suffix(".json")
    if not json_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file config: {json_path}")

    with json_path.open(encoding="utf-8") as f:
        meta = json.load(f)

    label_map = meta.get("label_map")
    if not label_map:
        raise ValueError(f"Không tìm thấy 'label_map' trong file: {json_path}")

    slug_to_original = load_slug_to_original(labels_csv)

    # Đảo ngược: index -> label_key -> slug -> tên tiếng Việt
    result = {}
    for label_key, idx in label_map.items():
        slug = label_key.split("/")[-1]  # "vn/hoa-de/rang-muoi" -> "rang-muoi"
        display = slug_to_original.get(slug, label_key)  # fallback là label_key
        result[str(idx)] = display

    # Sắp xếp theo index để dễ đọc
    result = dict(sorted(result.items(), key=lambda x: int(x[0])))
    return result


def main():
    repo_root = Path(__file__).resolve().parents[2]
    default_outputs = Path(__file__).resolve().parent / "outputs"
    default_labels = repo_root / "dataset" / "labels.csv"

    parser = argparse.ArgumentParser(
        description="Tạo file display_labels.json cho model TFLite."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Đường dẫn tới file .tflite. Mặc định: tự tìm file mới nhất trong outputs/",
    )
    parser.add_argument(
        "--labels",
        type=str,
        default=str(default_labels),
        help=f"Đường dẫn tới labels.csv. Mặc định: {default_labels}",
    )
    args = parser.parse_args()

    labels_csv = Path(args.labels)
    if not labels_csv.exists():
        raise FileNotFoundError(f"Không tìm thấy labels.csv tại: {labels_csv}")

    if args.model:
        tflite_path = Path(args.model)
    else:
        tflite_path = find_latest_tflite(default_outputs)

    if not tflite_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file .tflite: {tflite_path}")

    print(f"Model   : {tflite_path}")
    print(f"Labels  : {labels_csv}")
    import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None

    display_labels = build_display_labels(tflite_path, labels_csv)

    # Tên output: <tên_model>_display_labels.json, nằm cùng thư mục với .tflite
    out_path = tflite_path.parent / (tflite_path.stem + "_display_labels.json")
    out_path.write_text(json.dumps(display_labels, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nOutput  : {out_path}")
    print(f"Classes : {len(display_labels)}")
    print("\nSample (first 5):")
    for k, v in list(display_labels.items())[:5]:
        print(f"  {k}: {v.encode('utf-8').decode('utf-8')}", flush=True)


if __name__ == "__main__":
    main()
