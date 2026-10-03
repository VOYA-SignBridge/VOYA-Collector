#!/bin/bash
cd /workspace || exit 1
D=/workspace/processed/splits/versions/hoa_de_loso_v5/test_S001
for m in hdgcn cnn tcn; do
  echo "=== verify_determinism $m ===" >> /workspace/reports/determinism_summary.txt
  python scripts/verify_determinism.py \
    --train_csv $D/train.csv --val_csv $D/val.csv --test_csv $D/test.csv \
    --recognition_profile hoa_de --features_root /dataset/features \
    --dataset_version isds2026_v5 --split_version "hoa_de_loso_v5/test_S001" \
    --model_type $m --epochs 80 --seed 42 \
    --out-report /workspace/reports/determinism_${m}.json 2>&1 | tail -8 >> /workspace/reports/determinism_summary.txt
done
echo "=== XONG DETERMINISM ===" >> /workspace/reports/determinism_summary.txt
