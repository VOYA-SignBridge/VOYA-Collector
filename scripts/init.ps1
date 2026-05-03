# VOYA-Collector Windows Setup Script
# PowerShell initialization script for Docker setup
# Usage: .\scripts\init.ps1 [clean|rebuild]

param(
    [ValidateSet("clean", "rebuild", "help", $null)]
    [string]$Command
)

# Configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Color functions
function Write-Info { Write-Host "[INFO]  $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[✓]    $args" -ForegroundColor Green }
function Write-Warn { Write-Host "[WARN]  $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[✗]    $args" -ForegroundColor Red }

# Check prerequisites
function Check-Prerequisites {
    Write-Info "Checking prerequisites..."
    
    # Check Docker
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        Write-Error "Docker not found. Please install Docker Desktop for Windows."
        exit 1
    }
    Write-Success "Docker is installed"
    
    # Check Docker Compose
    $compose = Get-Command docker-compose -ErrorAction SilentlyContinue
    if (-not $compose) {
        Write-Error "Docker Compose not found."
        exit 1
    }
    Write-Success "Docker Compose is installed"
    
    # Check .env file
    if (-not (Test-Path ".env")) {
        Write-Warn ".env file not found"
        if (Test-Path ".env.example") {
            Write-Info "Copying .env.example to .env..."
            Copy-Item ".env.example" ".env"
            Write-Success ".env file created"
        } else {
            Write-Error "Neither .env nor .env.example found"
            exit 1
        }
    }
    Write-Success "Configuration file ready"
}

# Validate configuration
function Validate-Config {
    Write-Info "Validating configuration..."
    
    $envContent = Get-Content .env
    
    if (-not ($envContent | Select-String "POSTGRES_USER")) {
        Write-Error "POSTGRES_USER not set in .env"
        exit 1
    }
    
    if (-not ($envContent | Select-String "POSTGRES_PASSWORD")) {
        Write-Error "POSTGRES_PASSWORD not set in .env"
        exit 1
    }
    
    if (-not ($envContent | Select-String "POSTGRES_DB")) {
        Write-Error "POSTGRES_DB not set in .env"
        exit 1
    }
    
    Write-Success "Configuration validation passed"
}

# Cleanup old setup
function Cleanup-Old {
    Write-Info "Cleaning up old setup..."
    
    Write-Info "Stopping containers..."
    docker compose down --remove-orphans 2>&1 | Out-Null
    
    $response = Read-Host "Do you want to reset the database? (y/N)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Warn "Removing database volume..."
        docker volume rm voya_collector_postgres_data 2>&1 | Out-Null
        Write-Success "Database volume removed"
    }
    
    Write-Success "Cleanup complete"
}

# Build images
function Build-Images {
    param([bool]$Fresh = $false)
    
    Write-Info "Building Docker images..."
    
    if ($Fresh) {
        Write-Info "Building with --no-cache for fresh build..."
        docker compose build --no-cache
    } else {
        docker compose build
    }
    
    Write-Success "Images built successfully"
}

# Start services
function Start-Services {
    Write-Info "Starting services..."
    
    docker compose up -d
    
    Write-Success "Services started"
}

# Wait for services
function Wait-ForServices {
    Write-Info "Waiting for services to be healthy..."
    
    $maxAttempts = 60
    $attempt = 0
    
    while ($attempt -lt $maxAttempts) {
        $runningCount = (docker compose ps --services --filter "status=running" | Measure-Object -Line).Lines
        $totalCount = (docker compose config --services | Measure-Object -Line).Lines
        
        if ($runningCount -eq $totalCount) {
            Write-Success "All services are running"
            return
        }
        
        $attempt++
        Write-Progress -Activity "Waiting for services" -Status "Attempt $attempt/$maxAttempts" -PercentComplete ($attempt / $maxAttempts * 100)
        Start-Sleep -Seconds 1
    }
    
    Write-Error "Services did not start within timeout"
    exit 1
}

# Check database
function Check-Database {
    Write-Info "Checking database connectivity..."
    
    $maxAttempts = 30
    $attempt = 0
    
    $postgresUser = (Select-String "POSTGRES_USER" .env | ForEach-Object { $_.Line.Split("=")[1] })
    
    while ($attempt -lt $maxAttempts) {
        try {
            $result = docker compose exec -T postgres pg_isready -U $postgresUser 2>&1
            Write-Success "Database is ready"
            return
        } catch {
            $attempt++
            Write-Progress -Activity "Waiting for database" -Status "Attempt $attempt/$maxAttempts" -PercentComplete ($attempt / $maxAttempts * 100)
            Start-Sleep -Seconds 1
        }
    }
    
    Write-Error "Database connection timeout"
    exit 1
}

# Initialize database
function Initialize-Database {
    Write-Info "Initializing database tables..."
    
    try {
        docker compose exec -T backend python -m app.cli.init_db
        Write-Success "Database initialization complete"
    } catch {
        Write-Warn "Database initialization may have been skipped (tables may already exist)"
    }
}

# Health check
function Perform-HealthCheck {
    Write-Info "Running health checks..."
    
    $services = @("postgres", "redis", "minio", "backend", "frontend")
    
    foreach ($service in $services) {
        if ((docker compose ps $service 2>&1) -match "running") {
            Write-Success "$service is running"
        } else {
            Write-Error "$service is not running"
        }
    }
    
    # Test backend API
    Write-Info "Testing backend API..."
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "Backend API is responding"
        }
    } catch {
        Write-Warn "Backend API is not responding yet (may still be starting)"
    }
}

# Show summary
function Show-Summary {
    $nginxPort = (Select-String "NGINX_HTTP_PORT" .env | ForEach-Object { $_.Line.Split("=")[1] }).Trim()
    if (-not $nginxPort) { $nginxPort = "8080" }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "VOYA-Collector Setup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Services:"
    Write-Host "  - Frontend:       http://localhost:$nginxPort"
    Write-Host "  - Backend API:    http://localhost:8000"
    Write-Host "  - PgAdmin:        http://localhost:5050"
    Write-Host "  - MinIO:          http://localhost:9001"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "  - View logs:      docker compose logs -f"
    Write-Host "  - Stop services:  docker compose down"
    Write-Host "  - Access shell:   docker compose exec backend bash"
    Write-Host "  - Rebuild:        docker compose build --no-cache"
    Write-Host ""
}

# Help
function Show-Help {
    Write-Host "VOYA-Collector Docker Setup Script"
    Write-Host ""
    Write-Host "Usage: .\scripts\init.ps1 [COMMAND]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  (none)    - Normal setup with existing data"
    Write-Host "  clean     - Stop and remove containers, optionally reset database"
    Write-Host "  rebuild   - Fresh build from scratch"
    Write-Host "  help      - Show this help message"
}

# Main
function Main {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "VOYA-Collector Docker Setup" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    
    Check-Prerequisites
    Validate-Config
    
    if ($Command -eq "clean") {
        Cleanup-Old
    }
    
    if ($Command -eq "rebuild" -or $Command -eq "clean") {
        Build-Images -Fresh $true
    } else {
        Build-Images -Fresh $false
    }
    
    Start-Services
    Wait-ForServices
    Check-Database
    Initialize-Database
    Perform-HealthCheck
    Show-Summary
}

# Execute
if ($Command -eq "help") {
    Show-Help
} else {
    Main
}
