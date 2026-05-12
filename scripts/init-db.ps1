# VOYA-Collector database initialization helper
# Usage: .\scripts\init-db.ps1

$ErrorActionPreference = "Stop"

Write-Host "[INFO] Starting database initialization..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Docker is not installed or not available in PATH" -ForegroundColor Red
    exit 1
}

$backendStatus = docker compose ps backend 2>$null
if ($backendStatus -notmatch "Up") {
    Write-Host "[INFO] Starting backend dependencies..."
    docker compose up -d postgres redis backend
}

Write-Host "[INFO] Running backend init-db entrypoint..."
docker compose exec -T backend python -m app.cli.init_db

Write-Host "[INFO] Database initialization finished"
