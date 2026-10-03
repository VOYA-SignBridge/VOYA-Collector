#!/bin/bash
# Luoi ba chieu: nguoi ky (n) x lan quay (r) x so lop (C).
#
# Phuong an B: C in {5, 10, 30}, n = 1..5, r in {4, 6, 8}, 3 tap lop cho moi
# muc C duoi 30 (C=30 la toan bo von tu vung nen chi co 1 tap).
#
# 7 pool x 162 o x 3 seed = 3.402 lan chay, uoc tinh ~24 gio tren BiGRU.
#
# DIEU KIEN TIEN QUYET da thoa (2026-08-04):
#   - manifest isds2026_v14, sha256 aab5169197c2...  (3.400 mau)
#   - o nho nhat = 10 mau  ->  r=8 dung duoc (r + 2 <= 10)
#   - gia dinh "doc theo n khong phu thuoc tinh/dong" da kiem: reports/motion_ctl_*
#
#   docker compose exec -d -w /workspace trainer bash reports/scaling_3d_run.sh
#
# Chay mot minh, KHONG noi chuoi. Resume duoc: dong da co trong log se bi bo qua.
cd /workspace || exit 1

DATASET_VERSION=${DATASET_VERSION:-isds2026_v14}
PROFILE=${PROFILE:-alphabet}
MODEL=${MODEL:-bigru_attention}
SEEDS=${SEEDS:-"42 43 44"}
EPOCHS=${EPOCHS:-80}
POOLS=${POOLS:-"C05_s1 C05_s2 C05_s3 C10_s1 C10_s2 C10_s3 C30_s1"}
MAX_CONSECUTIVE_FAILURES=${MAX_CONSECUTIVE_FAILURES:-5}
consecutive_failures=0

LOG=/workspace/reports/scaling_3d_v14_${MODEL}_raw.txt
ERRLOG=/workspace/reports/scaling_3d_v14_${MODEL}_failures.txt
OUT=/workspace/processed/train_utils/outputs/scaling_3d/v14

mkdir -p /workspace/reports "$OUT"
touch "$LOG"

LOCK=/tmp/scaling_3d_v14_${MODEL}.lock
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "[LOI] da co mot lan chay khac (PID $(cat "$LOCK")). Dung: kill \$(cat $LOCK)"
  exit 3
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

echo "=== luoi 3 chieu v14 : $(echo $POOLS | wc -w) pool x 162 o x $(echo $SEEDS | wc -w) seed | model=$MODEL ===" | tee -a "$LOG"

for pool in $POOLS; do
  VERSION="alphabet_scaling_v14_$pool"
  ROOT="processed/splits/versions/$VERSION"
  [ -d "$ROOT" ] || { echo "  bo qua $pool (khong co $ROOT)"; continue; }

  # C doc tu ten pool (C05 -> 5) de ghi thang vao log, khoi phai tra nguoc metadata luc phan tich
  C=$(echo "$pool" | sed 's/^C0*\([0-9]*\)_.*/\1/')

  for D in $(find "$ROOT" -mindepth 3 -maxdepth 3 -type d | sort); do
    rel=${D#"$ROOT/"}                       # test_S001/n2_r6/S002+S004
    held=$(echo "$rel" | cut -d/ -f1)
    nr=$(echo "$rel"  | cut -d/ -f2)
    combo=$(echo "$rel" | cut -d/ -f3)

    for s in $SEEDS; do
      tag="C=$C $pool $held $nr $combo seed=$s"
      grep -qF "$tag " "$LOG" && continue

      out=$(python -m processed.train_utils.train_tcn \
        --model_type="$MODEL" --seed="$s" \
        --run-purpose research \
        --recognition_profile "$PROFILE" \
        --features_root /dataset/features \
        --dataset_version "$DATASET_VERSION" \
        --split_version "$VERSION/$rel" \
        --train_csv="$D/train.csv" --val_csv="$D/val.csv" --test_csv="$D/test.csv" \
        --epochs="$EPOCHS" --batch_size=32 \
        --out_dir="$OUT" 2>&1)
      line=$(printf '%s\n' "$out" | grep -oP 'test loss \S+ acc \K[0-9.]+ f1 [0-9.]+')

      if [ -z "$line" ]; then
        echo "$tag FAILED" >> "$LOG"
        echo "  $tag -> FAILED"
        { echo "=== $tag ==="; printf '%s\n' "$out" | tail -25; echo; } >> "$ERRLOG"
        consecutive_failures=$((consecutive_failures + 1))
        if [ "$consecutive_failures" -ge "$MAX_CONSECUTIVE_FAILURES" ]; then
          echo "[DUNG] $consecutive_failures lan hong lien tiep — xem $ERRLOG."
          echo "[DUNG] $consecutive_failures lan hong lien tiep" >> "$LOG"
          exit 4
        fi
      else
        echo "$tag $line" >> "$LOG"
        echo "  $tag -> $line"
        consecutive_failures=0
      fi
    done
  done
done

echo "=== XONG luoi 3 chieu v14 ===" >> "$LOG"
echo "ket qua: $LOG"
