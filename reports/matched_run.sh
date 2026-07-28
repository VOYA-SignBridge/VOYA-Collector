#!/bin/bash
cd /workspace || exit 1
V=processed/splits/versions/hoa_de_matched_leak_v6
OUT=/workspace/processed/train_utils/outputs/matched_leak
LOG=/workspace/reports/matched_leak_raw.txt
mkdir -p /workspace/reports; touch "$LOG"
for signer in S001 S002 S012 S013; do
  for proto in A B; do
    D=/workspace/$V/test_${signer}/protocol_${proto}
    for m in tcn lstm hdgcn bigru_attention cnn; do
      for s in 42 43 44; do
        tag="test_${signer} proto_${proto} ${m} seed=${s}"
        grep -qF "$tag " "$LOG" && continue   # resumable: bo qua neu da co
        line=$(python -m processed.train_utils.train_tcn --model_type=$m --seed=$s \
          --run-purpose research --recognition_profile hoa_de --features_root /dataset/features \
          --dataset_version isds2026_v6 --split_version "hoa_de_matched_leak_v6/test_${signer}/protocol_${proto}" \
          --train_csv=$D/train.csv --val_csv=$D/val.csv --test_csv=$D/test.csv \
          --epochs=80 --batch_size=32 --out_dir=$OUT 2>&1 | grep -oP 'test loss \S+ acc \K[0-9.]+ f1 [0-9.]+')
        echo "$tag $line" >> "$LOG"
      done
    done
  done
done
echo "=== XONG MATCHED ===" >> "$LOG"
