#!/usr/bin/env bash
# Bring the stack up, using the GPU only when this host can actually run it.
#
# The GPU reservation lives in docker-compose.gpu.yml because `driver: nvidia`
# is resolved when the container is created: include it on a host without the
# NVIDIA Container Toolkit and the trainer dies with "could not select device
# driver", taking the deploy with it. Remembering to add or drop one -f flag per
# machine is exactly the kind of thing that gets forgotten, so probe instead.
#
#   ./scripts/deploy.sh              # up -d --build
#   ./scripts/deploy.sh --no-build   # up -d
#   ./scripts/deploy.sh --cpu        # force CPU even where a GPU exists
#
set -euo pipefail
cd "$(dirname "$0")/.."

FILES=(-f docker-compose.yml -f docker-compose.prod.yml)
BUILD=(--build)
FORCE_CPU=0

for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=() ;;
    --cpu)      FORCE_CPU=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

gpu_usable() {
  [ "$FORCE_CPU" -eq 1 ] && return 1
  # Not "is there a driver" but "can a container actually claim the GPU" —
  # the toolkit can be missing, or present and broken, and only the real
  # request tells them apart.
  docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 \
    nvidia-smi >/dev/null 2>&1
}

# Per-machine allowlist of public hostnames. It is gitignored (the tunnel name
# here is not the tunnel name there), so a fresh clone has none — and a missing
# file means an empty allowlist, which is safe but silent: reset-password mails
# quietly fall back to FRONTEND_BASE_URL and nobody notices until a user clicks
# a link pointing at the wrong host. Seed it from the example instead.
if [ ! -f deploy/public_hosts.txt ] && [ -f deploy/public_hosts.example.txt ]; then
  cp deploy/public_hosts.example.txt deploy/public_hosts.txt
  echo "==> Seeded deploy/public_hosts.txt from the example."
  echo "    Add this machine's public hostname to it — it is re-read per request,"
  echo "    so no restart is needed after an edit."
fi

echo "==> Probing for a usable GPU…"
if gpu_usable; then
  NAME=$(docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 \
           nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
  echo "    GPU available: ${NAME:-unknown} — adding docker-compose.gpu.yml"
  FILES+=(-f docker-compose.gpu.yml)
else
  if [ "$FORCE_CPU" -eq 1 ]; then
    echo "    --cpu given; skipping the GPU overlay."
  else
    echo "    No usable GPU (no card, or the NVIDIA Container Toolkit is missing)."
    echo "    Starting CPU-only — training still runs, just slower."
  fi
fi

echo "==> docker compose ${FILES[*]} up -d ${BUILD[*]}"
docker compose "${FILES[@]}" up -d "${BUILD[@]}"

echo "==> Waiting for health checks to settle…"
until [ "$(docker ps --filter health=starting --format '{{.Names}}' | wc -l)" -eq 0 ]; do
  sleep 5
done

docker compose "${FILES[@]}" ps -a --format "{{.Name}}\t{{.Status}}"

# The trainer picks the device itself (train_tcn.pick_device) and refuses a GPU
# whose compute capability this torch build has no kernels for, so this line is
# the ground truth for whether training will really use the card.
echo "==> Trainer device:"
docker exec "$(docker ps -qf name=_trainer | head -1)" python -c "
import sys; sys.path.insert(0,'/workspace')
from processed.train_utils.train_tcn import pick_device
import torch
print('   ', pick_device(), '|', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no CUDA device')
" 2>/dev/null || echo "    (trainer not up yet)"
