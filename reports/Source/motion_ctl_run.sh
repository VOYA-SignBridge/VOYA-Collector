#!/bin/bash
# Doi chung tinh-vs-dong: do doc cua duong cong theo so nguoi ky (n) co phu thuoc
# vao loai chuyen dong cua lop hay khong.
#
# Bon tap con, CUNG C=8, cung nguoi ky, cung r=4 — chi khac motion type:
#   _dyn   8 chu dong (Â Ă Ê Ô Ơ R Ư Z)
#   _sta1  8 chu tinh
#   _sta2  8 chu tinh khac
#   _sta3  8 chu tinh khac nua
#
# Neu doc theo n giong nhau  -> phan bien "bang chu cai toan tinh nen khong
#                                khai quat duoc" da duoc tra loi bang so lieu.
# Neu doc khac nhau          -> phan bien dung, va ta DINH LUONG duoc no.
# Ca hai ket cuc deu dung duoc cho luan van.
#
#   docker compose exec -d -w /workspace trainer bash reports/motion_ctl_run.sh
#
# 4 tap con x 54 o x 3 seed = 648 lan chay. Dung BiGRU+Attn: no manh nhat tren
# bang chu cai, va re hon TCN nhieu lan duoi rang buoc tat dinh.
cd /workspace || exit 1

DATASET_VERSION=${DATASET_VERSION:-isds2026_v13}
PROFILE=${PROFILE:-alphabet}
MODEL=${MODEL:-bigru_attention}
SEEDS=${SEEDS:-"42 43 44"}
EPOCHS=${EPOCHS:-80}
SUBSETS=${SUBSETS:-"dyn sta1 sta2 sta3"}
MAX_CONSECUTIVE_FAILURES=${MAX_CONSECUTIVE_FAILURES:-5}
consecutive_failures=0

LOG=/workspace/reports/motion_ctl_v13_${MODEL}_raw.txt
ERRLOG=/workspace/reports/motion_ctl_v13_${MODEL}_failures.txt
OUT=/workspace/processed/train_utils/outputs/motion_ctl/v13

mkdir -p /workspace/reports "$OUT"
touch "$LOG"

LOCK=/tmp/motion_ctl_v13_${MODEL}.lock
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "[LOI] da co mot lan chay khac (PID $(cat "$LOCK")). Dung: kill \$(cat $LOCK)"
  exit 3
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

echo "=== doi chung tinh/dong : $(echo $SUBSETS | wc -w) tap con x 54 o x $(echo $SEEDS | wc -w) seed | model=$MODEL ===" | tee -a "$LOG"

for sub in $SUBSETS; do
  VERSION="alphabet_motion_grid_v13_$sub"
  ROOT="processed/splits/versions/$VERSION"
  [ -d "$ROOT" ] || { echo "  bo qua $sub (khong co $ROOT)"; continue; }

  for D in $(find "$ROOT" -mindepth 3 -maxdepth 3 -type d | sort); do
    rel=${D#"$ROOT/"}                      # test_S001/n2_r4/S002+S004
    held=$(echo "$rel" | cut -d/ -f1)
    nr=$(echo "$rel" | cut -d/ -f2)
    combo=$(echo "$rel" | cut -d/ -f3)

    for s in $SEEDS; do
      tag="$sub $held $nr $combo seed=$s"
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

echo "=== XONG doi chung tinh/dong ===" >> "$LOG"
echo "ket qua: $LOG"
