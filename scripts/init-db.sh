#!/bin/bash

# VOYA-Collector database initialization helper
# Usage: ./scripts/init-db.sh

set -e

echo "[INFO] Starting database initialization..."

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] Docker is not installed or not available in PATH"
  exit 1
fi

if ! docker compose ps backend 2>/dev/null | grep -q "Up"; then
  echo "[INFO] Starting backend dependencies..."
  docker compose up -d postgres redis backend
fi

echo "[INFO] Running backend init-db entrypoint..."
docker compose exec -T backend python -m app.cli.init_db

echo "[INFO] Database initialization finished"
