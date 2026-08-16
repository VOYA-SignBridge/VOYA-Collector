#!/usr/bin/env bash
# Controlled feature ablation on root_strict_v13, BiGRU + Attention.
#
# Three arms, identical in every respect except the feature version, so any
# difference is attributable to the features alone:
#
#   v1    stored `sequence` (current production behaviour) -- baseline
#   v1z   depth re-referenced against itself, geometry unchanged
#   v1g   v1z plus 28 per-hand descriptors (in-plane distances and angles,
#         fingertip depth order, palm orientation)
#
# All three read every row of the split, so the test set keeps its 30 classes
# and both held-out signers. Runs are sequential on purpose: one GPU, and two
# concurrent CUDA processes have wedged the Docker engine here before.
#
# Launch detached so it does not die with the shell that started it:
#   docker exec -d voya_trainer bash /workspace/scripts/run_feature_ablation.sh
# Then follow /workspace/reports/feature_ablation/run.log

set -u

SPLIT=/workspace/processed/splits/versions/root_strict_v13
OUT=/workspace/reports/feature_ablation
mkdir -p "$OUT"
LOG="$OUT/run.log"

cd /workspace/processed || exit 1

echo "=== feature ablation started $(date -u +%FT%TZ) ===" | tee -a "$LOG"

for VER in v1 v1z v1g; do
  echo "" | tee -a "$LOG"
  echo "--- arm $VER : $(date -u +%FT%TZ) ---" | tee -a "$LOG"

  VOYA_FEATURE_VERSION="$VER" python -m train_utils.train_tcn \
    --train_csv "$SPLIT/train.csv" \
    --val_csv   "$SPLIT/val.csv" \
    --test_csv  "$SPLIT/test.csv" \
    --features_root /workspace/dataset/features \
    --model_type bigru_attention \
    --recognition_profile alphabet \
    --epochs 80 \
    --batch_size 32 \
    --lr 1e-3 \
    --dropout 0.3 \
    --seed 42 \
    --device cuda \
    --num_workers 0 \
    --out_dir "$OUT/$VER" \
    >> "$LOG" 2>&1

  echo "--- arm $VER exit=$? : $(date -u +%FT%TZ) ---" | tee -a "$LOG"
done

echo "" | tee -a "$LOG"
echo "=== feature ablation finished $(date -u +%FT%TZ) ===" | tee -a "$LOG"
