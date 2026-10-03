#!/bin/bash
# Matched performer-exposure experiment on all eight Hòa Đê performers.
#
# Replaces reports/matched_run.sh, which covered the four performers of the v6
# inventory. Protocol A holds the target performer out of training and
# validation; protocol B puts disjoint samples from that performer into both,
# against the same fixed test set. The gap between them is the paper's central
# result, and reporting it over four performers while the rest of the paper
# reports eight is the inconsistency this run removes.
#
#   docker compose exec -d -w /workspace -e MODELS="lstm hdgcn bigru_attention cnn" \
#       trainer bash reports/matched_v13_run.sh
#   then the same with MODELS="tcn"
#
# 8 folds x 2 protocols x 5 models x 3 seeds = 240 runs. On this profile TCN
# costs ~6.5 min against ~0.5 min for the others, so running the four cheap
# architectures first yields a usable 32-comparison table in about 1.5 hours and
# leaves TCN's 5 hours to finish afterwards.
cd /workspace || exit 1

VERSION=${VERSION:-hoa_de_matched_leak_v13}
DATASET_VERSION=${DATASET_VERSION:-isds2026_v13}
PROFILE=${PROFILE:-hoa_de}
MODELS=${MODELS:-"tcn lstm hdgcn bigru_attention cnn"}
SEEDS=${SEEDS:-"42 43 44"}
EPOCHS=${EPOCHS:-80}
MAX_CONSECUTIVE_FAILURES=${MAX_CONSECUTIVE_FAILURES:-5}
consecutive_failures=0

ROOT=processed/splits/versions/$VERSION
OUT=/workspace/processed/train_utils/outputs/matched/$VERSION
LOG=/workspace/reports/matched_${VERSION}_raw.txt
ERRLOG=/workspace/reports/matched_${VERSION}_failures.txt

mkdir -p /workspace/reports "$OUT"
touch "$LOG"

# One copy only: two training processes on this GPU wedged the docker engine
# badly enough that even `ps` stopped answering, and the image has no pkill.
LOCK=/tmp/matched_${VERSION}.lock
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "[LOI] da co mot lan chay khac (PID $(cat "$LOCK")). Dung: kill \$(cat $LOCK)"
  exit 3
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

folds=$(find "$ROOT" -maxdepth 1 -name 'test_*' -type d | sort)
nf=$(echo "$folds" | wc -l)
echo "=== $VERSION : $nf fold x 2 protocol x $(echo $MODELS | wc -w) model x $(echo $SEEDS | wc -w) seed ===" | tee -a "$LOG"

i=0
for D in $folds; do
  held=$(basename "$D")
  i=$((i + 1))
  for proto in A B; do
    P="$D/protocol_$proto"
    [ -d "$P" ] || { echo "  bo qua $held protocol_$proto (khong co)"; continue; }
    for m in $MODELS; do
      for s in $SEEDS; do
        tag="$held proto_$proto $m seed=$s"
        # Resumable. FAILED lines match this too, so strip them before a rerun.
        grep -qF "$tag " "$LOG" && continue

        out=$(python -m processed.train_utils.train_tcn \
          --model_type="$m" --seed="$s" \
          --run-purpose research \
          --recognition_profile "$PROFILE" \
          --features_root /dataset/features \
          --dataset_version "$DATASET_VERSION" \
          --split_version "$VERSION/$held/protocol_$proto" \
          --train_csv="$P/train.csv" --val_csv="$P/val.csv" --test_csv="$P/test.csv" \
          --epochs="$EPOCHS" --batch_size=32 \
          --out_dir="$OUT" 2>&1)
        line=$(printf '%s\n' "$out" | grep -oP 'test loss \S+ acc \K[0-9.]+ f1 [0-9.]+')

        if [ -z "$line" ]; then
          echo "$tag FAILED" >> "$LOG"
          echo "  [$i/$nf] $tag -> FAILED"
          { echo "=== $tag ==="; printf '%s\n' "$out" | tail -25; echo; } >> "$ERRLOG"
          consecutive_failures=$((consecutive_failures + 1))
          if [ "$consecutive_failures" -ge "$MAX_CONSECUTIVE_FAILURES" ]; then
            echo "[DUNG] $consecutive_failures lan hong lien tiep — xem $ERRLOG."
            echo "[DUNG] $consecutive_failures lan hong lien tiep" >> "$LOG"
            exit 4
          fi
        else
          echo "$tag $line" >> "$LOG"
          echo "  [$i/$nf] $tag -> $line"
          consecutive_failures=0
        fi
      done
    done
  done
done

echo "=== XONG $VERSION ===" >> "$LOG"
echo "ket qua: $LOG"
