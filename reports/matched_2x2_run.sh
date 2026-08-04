#!/bin/bash
# Hai o con thieu cua thiet ke phoi nhiem 2x2 tren tam Hoa De.
#
# protocol_A (train=No,val=No) va protocol_B (train=Yes,val=Yes) DA CHAY XONG
# trong reports/matched_hoa_de_matched_leak_v13_raw.txt (240 lan, xac minh
# tren dia 2026-08-01). Script nay chi chay hai o con lai:
#   protocol_TE (train=Yes,val=No)
#   protocol_VE (train=No,val=Yes)
#
#   docker compose exec -d -w /workspace trainer bash reports/matched_2x2_run.sh
#
# 8 fold x 2 protocol x 5 model x 3 seed = 240 lan chay.
cd /workspace || exit 1

VERSION=${VERSION:-hoa_de_matched_leak_v13}
DATASET_VERSION=${DATASET_VERSION:-isds2026_v13}
PROFILE=${PROFILE:-hoa_de}
MODELS=${MODELS:-"lstm hdgcn bigru_attention cnn tcn"}
SEEDS=${SEEDS:-"42 43 44"}
EPOCHS=${EPOCHS:-80}
MAX_CONSECUTIVE_FAILURES=${MAX_CONSECUTIVE_FAILURES:-5}
consecutive_failures=0

ROOT=processed/splits/versions/$VERSION
OUT=/workspace/processed/train_utils/outputs/matched_2x2/$VERSION
LOG=/workspace/reports/matched_2x2_${VERSION}_raw.txt
ERRLOG=/workspace/reports/matched_2x2_${VERSION}_failures.txt

mkdir -p /workspace/reports "$OUT"
touch "$LOG"

LOCK=/tmp/matched_2x2_${VERSION}.lock
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "[LOI] da co mot lan chay khac (PID $(cat "$LOCK")). Dung: kill \$(cat $LOCK)"
  exit 3
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

folds=$(find "$ROOT" -maxdepth 1 -name 'test_*' -type d | sort)
nf=$(echo "$folds" | wc -l)
echo "=== $VERSION (2x2 TE/VE) : $nf fold x 2 protocol x $(echo $MODELS | wc -w) model x $(echo $SEEDS | wc -w) seed ===" | tee -a "$LOG"

i=0
for D in $folds; do
  held=$(basename "$D")
  i=$((i + 1))
  for proto in TE VE; do
    P="$D/protocol_$proto"
    [ -d "$P" ] || { echo "  bo qua $held protocol_$proto (khong co)"; continue; }
    for m in $MODELS; do
      for s in $SEEDS; do
        tag="$held proto_$proto $m seed=$s"
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

echo "=== XONG $VERSION (2x2) ===" >> "$LOG"
echo "ket qua: $LOG"
