#!/bin/bash
# Signer-count x repetitions grid: does a fixed sample budget buy more when spent
# on extra signers or on extra takes from the same ones?
#
# Reads every cell produced by processed/splits/make_budget_grid.py and trains
# one model per (cell, seed). Resumable: a tag already in the log is skipped, so
# an interrupted run continues instead of restarting.
#
#   docker compose exec -w /workspace trainer bash reports/budget_grid_run.sh
#
# ~112 cells x 3 seeds. Each is small (at most 3 signers x 7 classes x 12 = 252
# training samples), so the whole grid is an overnight job, not a week.
cd /workspace || exit 1

VERSION=${VERSION:-hoa_de_budget_v2}
MODEL=${MODEL:-tcn}
PROFILE=${PROFILE:-hoa_de}
SEEDS=${SEEDS:-"42 43 44"}
EPOCHS=${EPOCHS:-80}
# Stop after this many cells. Lets a smoke test end on its own rather than being
# killed with `timeout`, which cuts the docker client while the training process
# inside the container keeps running -- and this image has no ps or pkill to
# find it with afterwards.
MAX_CELLS=${MAX_CELLS:-0}
# Give up once this many runs fail back to back (see the failure handler below).
MAX_CONSECUTIVE_FAILURES=${MAX_CONSECUTIVE_FAILURES:-5}
consecutive_failures=0

ROOT=processed/splits/versions/$VERSION

# Read the dataset version out of the grid itself rather than defaulting to a
# hard-coded one. A stale default would stamp every checkpoint of a 900-run job
# with the wrong provenance -- the run would look valid and be uncitable.
if [ -z "$DATASET_VERSION" ]; then
  DATASET_VERSION=$(python - "$ROOT" <<'PY'
import json, re, sys
from pathlib import Path
meta = next(Path(sys.argv[1]).rglob("split_metadata.json"), None)
manifest = json.loads(meta.read_text(encoding="utf-8")).get("dataset_manifest", "") if meta else ""
# Matched by pattern, not by Path(): the field is written on Windows and carries
# backslashes, which a Linux Path treats as part of the filename.
m = re.search(r"dataset_manifest_([A-Za-z0-9_.-]+)\.csv", manifest)
print(m.group(1) if m else "")
PY
)
  if [ -z "$DATASET_VERSION" ]; then
    echo "[LOI] khong suy ra duoc dataset_version tu $ROOT — dat bien DATASET_VERSION va chay lai"
    exit 2
  fi
  echo "dataset_version suy ra tu split: $DATASET_VERSION"
fi
OUT=/workspace/processed/train_utils/outputs/budget_grid/$VERSION/$MODEL
LOG=/workspace/reports/budget_grid_${VERSION}_${MODEL}_raw.txt

mkdir -p /workspace/reports "$OUT"
touch "$LOG"

# Refuse to start a second copy. Two of these in one container means two training
# processes competing for the same GPU and RAM, which wedged the engine badly
# enough that even `ps` stopped answering. The image has no pkill, so a stray run
# cannot be stopped from inside either -- far better not to start it.
LOCK=/tmp/budget_grid_${VERSION}_${MODEL}.lock
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "[LOI] da co mot lan chay khac (PID $(cat "$LOCK")). Dung: kill \$(cat $LOCK)"
  exit 3
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

total=$(find "$ROOT" -name train.csv | wc -l)
echo "=== $VERSION / $MODEL : $total o x $(echo $SEEDS | wc -w) seed ===" | tee -a "$LOG"

i=0
for cell in $(find "$ROOT" -name train.csv | sort); do
  D=$(dirname "$cell")
  # .../test_S001/n2_r6/S002+S012
  combo=$(basename "$D")
  nr=$(basename "$(dirname "$D")")
  held=$(basename "$(dirname "$(dirname "$D")")")
  i=$((i + 1))
  if [ "$MAX_CELLS" -gt 0 ] && [ "$i" -gt "$MAX_CELLS" ]; then
    echo "dung som sau $MAX_CELLS o (MAX_CELLS)"
    break
  fi

  for s in $SEEDS; do
    tag="$held $nr $combo $MODEL seed=$s"
    grep -qF "$tag " "$LOG" && continue

    line=$(python -m processed.train_utils.train_tcn \
      --model_type="$MODEL" --seed="$s" \
      --run-purpose research \
      --recognition_profile "$PROFILE" \
      --features_root /dataset/features \
      --dataset_version "$DATASET_VERSION" \
      --split_version "$VERSION/$held/$nr/$combo" \
      --train_csv="$D/train.csv" --val_csv="$D/val.csv" --test_csv="$D/test.csv" \
      --epochs="$EPOCHS" --batch_size=32 \
      --out_dir="$OUT" 2>&1 | grep -oP 'test loss \S+ acc \K[0-9.]+ f1 [0-9.]+')

    if [ -z "$line" ]; then
      echo "$tag FAILED" >> "$LOG"
      echo "  [$i/$total] $tag -> FAILED"
      consecutive_failures=$((consecutive_failures + 1))
      # Once training starts failing it usually keeps failing -- a CUDA fault or
      # exhausted memory does not heal mid-run. Stopping early leaves a grid
      # that can be resumed; carrying on burned 482 of 936 cells before anyone
      # noticed, and every one of them had to be rerun anyway.
      if [ "$consecutive_failures" -ge "$MAX_CONSECUTIVE_FAILURES" ]; then
        echo "[DUNG] $consecutive_failures lan hong lien tiep — nhieu kha nang moi truong da hong."
        echo "       Kiem tra GPU/bo nho, xoa cac dong FAILED khoi $LOG, roi chay lai de tiep tuc."
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

echo "=== XONG $VERSION / $MODEL ===" >> "$LOG"
echo "ket qua: $LOG"
