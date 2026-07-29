#!/bin/bash
cd /workspace || exit 1
V=processed/splits/versions/alphabet_loso_v6
OUT=/workspace/processed/train_utils/outputs/alpha_v6_fast
LOG=/workspace/reports/alpha_v6_fast_raw.txt
mkdir -p /workspace/reports
: > "$LOG"
for fold in test_S001 test_S002; do
  D=/workspace/$V/$fold
  for m in tcn lstm hdgcn bigru_attention cnn; do
    for s in 42 43 44; do
      line=$(python -m processed.train_utils.train_tcn --model_type=$m --seed=$s \
        --determinism fast --run-purpose smoke_test --recognition_profile alphabet --features_root /dataset/features \
        --dataset_version isds2026_v6 --split_version "alphabet_loso_v6/$fold" \
        --train_csv=$D/train.csv --val_csv=$D/val.csv --test_csv=$D/test.csv \
        --epochs=80 --batch_size=32 --out_dir=$OUT 2>&1 | grep -oP 'test loss \S+ acc \K[0-9.]+ f1 [0-9.]+')
      echo "$fold $m seed=$s $line" >> "$LOG"
    done
  done
done
echo "=== XONG ===" >> "$LOG"
