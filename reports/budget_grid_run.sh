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
    else
      echo "$tag $line" >> "$LOG"
      echo "  [$i/$total] $tag -> $line"
    fi
  done
done

echo "=== XONG $VERSION / $MODEL ===" >> "$LOG"
echo "ket qua: $LOG"
