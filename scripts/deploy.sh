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

# ---------------------------------------------------------------------------
# Pre-flight: catch the machine-specific failures BEFORE a 15-minute build.
#
# Every check below is something that already fails today — just later, and with
# a message that points somewhere else. The app refuses to start with weak
# secrets when APP_ENV=production, but only after the image is rebuilt and the
# container is up; `env_file: .env` fails with a compose error that reads like a
# YAML problem. Two seconds here beats a quarter of an hour there.
# ---------------------------------------------------------------------------
preflight_fail=0
note() { echo "    $*"; }
fail() { echo "    [FAIL] $*" >&2; preflight_fail=1; }

echo "==> Pre-flight…"

if [ ! -f .env ]; then
  fail ".env is missing. Copy .env.example and fill it in:  cp .env.example .env"
else
  # Read without sourcing: .env is not a shell script and may hold values with
  # spaces, '#', or quotes that would execute or truncate under `source`.
  env_get() { sed -n "s/^$1=//p" .env | tail -1 | tr -d '\r'; }

  app_env=$(env_get APP_ENV)
  for key in SECRET_KEY AUTH_TOKEN_SECRET_KEY; do
    value=$(env_get "$key")
    if [ -z "$value" ]; then
      fail "$key is not set in .env"
    elif [ "${#value}" -lt 32 ]; then
      if [ "$app_env" = "production" ]; then
        fail "$key is only ${#value} chars and APP_ENV=production — the backend "\
"will refuse to start. Generate one:  openssl rand -hex 32"
      else
        note "[warn] $key is only ${#value} chars (tolerated: APP_ENV=${app_env:-unset})"
      fi
    fi
  done

  for key in POSTGRES_PASSWORD VOYA_APP_DB_PASSWORD; do
    [ -n "$(env_get "$key")" ] || fail "$key is not set in .env"
  done

  # FRONTEND_BASE_URL must match the URL people actually open, or password-reset
  # and invitation links point at the wrong host on this machine.
  base_url=$(env_get FRONTEND_BASE_URL)
  [ -n "$base_url" ] || note "[warn] FRONTEND_BASE_URL is empty — mail links will be relative"
fi

docker info >/dev/null 2>&1 || fail "cannot talk to the Docker daemon — is Docker Desktop running?"

if [ "$preflight_fail" -ne 0 ]; then
  echo
  echo "Pre-flight failed. Nothing was built or started." >&2
  exit 3
fi
note "ok"

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

# ---------------------------------------------------------------------------
# Persist the file list into .env as COMPOSE_FILE.
#
# THIS is why the GPU kept disappearing. The probe above is correct and the
# deploy that follows it is correct — but the overlay only lives in this
# script's argv. Anything else that touches the stack loses it:
#
#     docker compose up -d              # bare, no -f  -> trainer without GPU
#     docker compose restart trainer    # ditto
#     the Restart button in Docker Desktop
#     a copy-pasted command from an older note
#
# and none of them fail. The trainer comes up perfectly healthy with
# DeviceRequests=null and quietly trains on CPU, which is why it took a
# screenshot of the monitoring page to notice.
#
# Compose reads COMPOSE_FILE from the .env file in the project directory, so
# writing it there makes the plain `docker compose` command in this folder mean
# the right thing for everyone — including tools that never heard of this
# script. COMPOSE_PATH_SEPARATOR is pinned because its default differs by
# platform (';' on Windows, ':' elsewhere) and this repo is deployed on both.
# ---------------------------------------------------------------------------
compose_file_value=""
for f in "${FILES[@]}"; do
  [ "$f" = "-f" ] && continue
  compose_file_value="${compose_file_value:+$compose_file_value:}$f"
done

upsert_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    # In-place with a temp file: `sed -i` differs between GNU and BSD.
    sed "s|^${key}=.*|${key}=${value}|" .env > .env.tmp && mv .env.tmp .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

upsert_env COMPOSE_PATH_SEPARATOR ":"
upsert_env COMPOSE_FILE "$compose_file_value"
echo "==> .env: COMPOSE_FILE=$compose_file_value"
echo "    (a bare \`docker compose up -d\` in this folder now keeps the same overlays)"

# ---------------------------------------------------------------------------
# Migration, as its own step, BEFORE the application comes up.
#
# Until 2026-08-12 this step did not exist: `ensure_tables()` ran the whole DDL
# — including dropping tables and copying data into new shapes — on every
# backend start. Every `docker compose up` was therefore an unannounced
# migration, and on 12/08 a harmless-looking verification command used that
# path to reshape the production schema.
#
# The backend now REFUSES to start when the schema version does not match the
# image, so this step is not optional politeness — skip it on a database that
# needs migrating and the stack will not come up. That is the intended failure:
# loud, immediate, and before anything writes.
#
# Order: build -> Postgres only -> migrate -> everything.
# ---------------------------------------------------------------------------

# Build FIRST, as its own command.
#
# `up -d --build postgres redis` would not do it: with service names given,
# compose builds only those services, and postgres/redis are pulled images with
# no build context. The migration step below then runs `docker compose run
# backend` against the PREVIOUS image — which is the image whose schema
# expectations we are trying to move away from. That is the exact skew this
# whole step exists to prevent, so it must not be reintroduced by the step.
if [ ${#BUILD[@]} -gt 0 ]; then
  echo "==> docker compose ${FILES[*]} build"
  docker compose "${FILES[@]}" build
fi

echo "==> Starting Postgres…"
docker compose "${FILES[@]}" up -d postgres redis

echo "==> Waiting for Postgres…"
until [ "$(docker compose "${FILES[@]}" ps -q postgres | xargs -r docker inspect \
          -f '{{.State.Health.Status}}' 2>/dev/null)" = "healthy" ]; do
  sleep 2
done

# The target database name comes from the DSN, NOT from POSTGRES_DB.
#
# This is the incident in one line. The command that migrated production said
# `-e POSTGRES_DB=authz_v5` and believed that aimed it at a clone; the
# application resolves MIGRATION_DATABASE_URL/DATABASE_URL and ignored it. So
# the guard is fed from the same string the application actually connects with.
dsn=$(env_get MIGRATION_DATABASE_URL)
[ -n "$dsn" ] || dsn=$(env_get DATABASE_URL)
expected_db=$(printf '%s' "$dsn" | sed -n 's#.*/\([^/?]*\)\(?.*\)\?$#\1#p')

if [ -z "$expected_db" ]; then
  echo "    [FAIL] cannot read the database name out of MIGRATION_DATABASE_URL/DATABASE_URL." >&2
  echo "           Migration will not run blind. Fix the DSN in .env." >&2
  exit 3
fi

# Ask the IMAGE which schema version it writes, rather than hardcoding it here.
# A number in this script would drift from the code the moment someone bumps
# APP_SCHEMA_VERSION, and it would drift silently.
target_version=$(docker compose "${FILES[@]}" run --rm --no-deps -T backend \
  python -c "from app.storage.schema_version import APP_SCHEMA_VERSION; print(APP_SCHEMA_VERSION)" \
  2>/dev/null | tr -d '\r' | tail -1)

if ! printf '%s' "$target_version" | grep -qE '^[0-9]+$'; then
  echo "    [FAIL] could not read APP_SCHEMA_VERSION out of the backend image." >&2
  exit 3
fi

echo "==> Migration: $expected_db -> schema v$target_version"
if ! docker compose "${FILES[@]}" run --rm --no-deps -T \
     -e EXPECTED_DATABASE="$expected_db" backend \
     python -m app.cli.migrate --to "$target_version"; then
  echo >&2
  echo "    [FAIL] migration did not complete. NOTHING ELSE WAS STARTED." >&2
  echo "           The old containers are still running the old code; the" >&2
  echo "           deployment is not half-applied." >&2
  echo "           Diagnose with:  docker compose run --rm backend \\" >&2
  echo "                             python -m app.cli.migrate --status" >&2
  exit 4
fi

# No `--build` here: the build already happened above, before the migration.
# Passing it again re-exports every image layer for no benefit — measured at
# several minutes on this machine during the 12/08 deploy, all of it after the
# schema had already changed. `--no-build` still works: it empties BUILD, the
# build step above is skipped, and this line uses the existing images.
echo "==> docker compose ${FILES[*]} up -d"
docker compose "${FILES[@]}" up -d

echo "==> Waiting for health checks to settle…"
until [ "$(docker ps --filter health=starting --format '{{.Names}}' | wc -l)" -eq 0 ]; do
  sleep 5
done

docker compose "${FILES[@]}" ps -a --format "{{.Name}}\t{{.Status}}"

# The trainer picks the device itself (train_tcn.pick_device) and refuses a GPU
# whose compute capability this torch build has no kernels for, so this line is
# the ground truth for whether training will really use the card.
echo "==> Trainer device:"
TRAINER=$(docker ps -qf name=_trainer | head -1)
docker exec "$TRAINER" python -c "
import sys; sys.path.insert(0,'/workspace')
from processed.train_utils.train_tcn import pick_device
import torch
print('   ', pick_device(), '|', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no CUDA device')
" 2>/dev/null || echo "    (trainer not up yet)"

# The probe said this host has a GPU, so the container must have been given one.
# Without this check the two outcomes are indistinguishable from the outside: a
# GPU trainer and a CPU trainer are both "Up (healthy)", and the difference only
# shows up as a training run that takes ten times longer than it should.
if [ -n "$TRAINER" ] && printf '%s' "$compose_file_value" | grep -q "docker-compose.gpu.yml"; then
  if [ "$(docker inspect "$TRAINER" --format '{{len .HostConfig.DeviceRequests}}' 2>/dev/null)" = "0" ]; then
    echo
    echo "    [WARN] The GPU overlay is in COMPOSE_FILE but this trainer container has" >&2
    echo "           no device reservation — it predates the overlay and was not" >&2
    echo "           recreated. \`restart\` does not re-read compose; force it:" >&2
    echo "               docker compose up -d --force-recreate trainer" >&2
  fi
fi
