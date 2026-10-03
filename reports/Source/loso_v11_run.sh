#!/bin/bash
# Five-architecture comparison under leave-one-signer-out, on the 8-signer
# hoa_de set (manifest isds2026_v11).
#
# Replaces reports/final_hoade_raw.txt, which covered only 4 signers: with four
# folds the 95% interval on a model's mean spans roughly [0.40, 0.99], which is
# too wide to rank anything. Eight folds is what makes the ranking mean
# something.
#
#   docker compose exec -w /workspace trainer bash reports/loso_v11_run.sh
#
# 8 folds x 5 models x 3 seeds = 120 runs. Each trains on ~550 samples, so this
# is hours, not the overnight job the budget grid was.
cd /workspace || exit 1

VERSION=${VERSION:-hoa_de_loso_v11}
DATASET_VERSION=${DATASET_VERSION:-isds2026_v11}
PROFILE=${PROFILE:-hoa_de}
MODELS=${MODELS:-"tcn lstm hdgcn bigru_attention cnn"}
SEEDS=${SEEDS:-"42 43 44"}
EPOCHS=${EPOCHS:-80}
MAX_CONSECUTIVE_FAILURES=${MAX_CONSECUTIVE_FAILURES:-5}
consecutive_failures=0

ROOT=processed/splits/versions/$VERSION
OUT=/workspace/processed/train_utils/outputs/loso/$VERSION
LOG=/workspace/reports/loso_${VERSION}_raw.txt
# Keep the crash text. The budget grid lost 482 cells and the cause had to be
# guessed afterwards, because the output went straight into a grep and nothing
# survived the failure.
ERRLOG=/workspace/reports/loso_${VERSION}_failures.txt

mkdir -p /workspace/reports "$OUT"
touch "$LOG"

# Refuse to start a second copy: two training processes competing for the same
# GPU and RAM wedged the docker engine badly enough that even `ps` stopped
# answering, and this image has no pkill to recover with.
LOCK=/tmp/loso_${VERSION}.lock
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "[LOI] da co mot lan chay khac (PID $(cat "$LOCK")). Dung: kill \$(cat $LOCK)"
  exit 3
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

folds=$(find "$ROOT" -maxdepth 1 -name 'test_*' -type d | sort)
total=$(echo "$folds" | wc -l)
echo "=== $VERSION : $total fold x $(echo $MODELS | wc -w) model x $(echo $SEEDS | wc -w) seed ===" | tee -a "$LOG"

i=0
for D in $folds; do
  held=$(basename "$D")
  i=$((i + 1))
  for m in $MODELS; do
    for s in $SEEDS; do
      tag="$held $m seed=$s"
      # Resumable: a tag already in the log is skipped. FAILED lines match this
      # too, so strip them before rerunning or the failures are treated as done.
      grep -qF "$tag " "$LOG" && continue

      out=$(python -m processed.train_utils.train_tcn \
        --model_type="$m" --seed="$s" \
        --run-purpose research \
        --recognition_profile "$PROFILE" \
        --features_root /dataset/features \
        --dataset_version "$DATASET_VERSION" \
        --split_version "$VERSION/$held" \
        --train_csv="$D/train.csv" --val_csv="$D/val.csv" --test_csv="$D/test.csv" \
        --epochs="$EPOCHS" --batch_size=32 \
        --out_dir="$OUT" 2>&1)
      line=$(printf '%s\n' "$out" | grep -oP 'test loss \S+ acc \K[0-9.]+ f1 [0-9.]+')

      if [ -z "$line" ]; then
        echo "$tag FAILED" >> "$LOG"
        echo "  [$i/$total] $tag -> FAILED"
        { echo "=== $tag ==="; printf '%s\n' "$out" | tail -25; echo; } >> "$ERRLOG"
        consecutive_failures=$((consecutive_failures + 1))
        # A CUDA fault or exhausted memory does not heal mid-run, so carrying on
        # only burns the rest of the queue.
        if [ "$consecutive_failures" -ge "$MAX_CONSECUTIVE_FAILURES" ]; then
          echo "[DUNG] $consecutive_failures lan hong lien tiep — xem $ERRLOG."
          echo "       Sua moi truong, xoa cac dong FAILED khoi $LOG, roi chay lai de tiep tuc."
          echo "[DUNG] $consecutive_failures lan hong lien tiep" >> "$LOG"
          exit 4
        fi
      else
        echo "$tag $line" >> "$LOG"
        echo "  [$i/$total] $tag -> $line"
        consecutive_failures=0
      fi
    done
  done
done

echo "=== XONG $VERSION ===" >> "$LOG"
echo "ket qua: $LOG"
