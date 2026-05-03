#!/bin/bash

# VOYA-Collector Container Setup & Initialization Script
# This script prepares and initializes all Docker containers for VOYA-Collector
# Supports: Linux, macOS, Windows (WSL, Git Bash, PowerShell)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker first."
        exit 1
    fi
    log_success "Docker is installed"
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose not found. Please install Docker Compose first."
        exit 1
    fi
    log_success "Docker Compose is installed"
    
    if [ ! -f ".env" ]; then
        log_warn ".env file not found"
        if [ -f ".env.example" ]; then
            log_info "Copying .env.example to .env..."
            cp .env.example .env
            log_success ".env file created from .env.example"
        else
            log_error "Neither .env nor .env.example found"
            exit 1
        fi
    fi
    log_success "Configuration file ready"
}

# Validate environment configuration
validate_config() {
    log_info "Validating configuration..."
    
    # Check critical variables
    if ! grep -q "POSTGRES_USER" .env; then
        log_error "POSTGRES_USER not set in .env"
        exit 1
    fi
    
    if ! grep -q "POSTGRES_PASSWORD" .env; then
        log_error "POSTGRES_PASSWORD not set in .env"
        exit 1
    fi
    
    if ! grep -q "POSTGRES_DB" .env; then
        log_error "POSTGRES_DB not set in .env"
        exit 1
    fi
    
    log_success "Configuration validation passed"
}

# Remove existing containers and data
cleanup_old_setup() {
    log_info "Cleaning up old setup..."
    
    log_info "Stopping all containers..."
    docker compose down --remove-orphans 2>/dev/null || true
    
    read -p "Do you want to reset the database? (y/N): " reset_db
    if [ "$reset_db" = "y" ] || [ "$reset_db" = "Y" ]; then
        log_warn "Removing database volume..."
        docker volume rm voya_collector_postgres_data 2>/dev/null || true
        log_success "Database volume removed"
    fi
    
    log_success "Cleanup complete"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."
    
    if [ "$1" = "fresh" ]; then
        log_info "Building with --no-cache for fresh build..."
        docker compose build --no-cache
    else
        docker compose build
    fi
    
    log_success "Images built successfully"
}

# Start services
start_services() {
    log_info "Starting services..."
    
    docker compose up -d
    
    log_success "Services started"
}

# Wait for services to be healthy
wait_for_services() {
    log_info "Waiting for services to be healthy..."
    
    local max_attempts=60
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        # Check if all containers are running
        local running_count=$(docker compose ps --services --filter "status=running" | wc -l)
        local total_count=$(docker compose config --services | wc -l)
        
        if [ "$running_count" -eq "$total_count" ]; then
            log_success "All services are running"
            break
        fi
        
        attempt=$((attempt + 1))
        echo -ne "Waiting for services... ($attempt/$max_attempts)\r"
        sleep 1
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "Services did not start within timeout"
        exit 1
    fi
}

# Check database connectivity
check_database() {
    log_info "Checking database connectivity..."
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker compose exec -T postgres pg_isready -U $(grep POSTGRES_USER .env | cut -d= -f2) >/dev/null 2>&1; then
            log_success "Database is ready"
            return 0
        fi
        
        attempt=$((attempt + 1))
        echo -ne "Waiting for database... ($attempt/$max_attempts)\r"
        sleep 1
    done
    
    log_error "Database connection timeout"
    exit 1
}

# Initialize database tables
init_database() {
    log_info "Initializing database tables..."
    
    if docker compose exec -T backend python -m app.cli.init_db; then
        log_success "Database initialization complete"
    else
        log_warn "Database initialization may have been skipped or failed; check backend logs"
    fi
    
}

# Health check
health_check() {
    log_info "Running health checks..."
    
    local services=("postgres" "redis" "minio" "backend" "frontend")
    
    for service in "${services[@]}"; do
        if docker compose ps $service | grep -q "running"; then
            log_success "$service is running"
        else
            log_error "$service is not running"
        fi
    done
    
    # Test backend API
    log_info "Testing backend API..."
    if curl -s http://localhost:8000/health >/dev/null; then
        log_success "Backend API is responding"
    else
        log_warn "Backend API is not responding yet (may still be starting)"
    fi
}

# Display summary and next steps
show_summary() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}VOYA-Collector Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Services:"
    echo "  - Frontend:   http://localhost:$(grep NGINX_HTTP_PORT .env | cut -d= -f2 || echo 8080)"
    echo "  - Backend API: http://localhost:8000"
    echo "  - PgAdmin:    http://localhost:5050"
    echo "  - MinIO:      http://localhost:9001"
    echo ""
    echo "Useful commands:"
    echo "  - View logs:          docker compose logs -f"
    echo "  - Stop services:      docker compose down"
    echo "  - Access bash shell:  docker compose exec backend bash"
    echo "  - Rebuild images:     docker compose build --no-cache"
    echo ""
}

# Main script
main() {
    echo ""
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}VOYA-Collector Docker Setup${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
    
    check_prerequisites
    validate_config
    
    # Parse command line arguments
    if [ "$1" = "clean" ]; then
        cleanup_old_setup
    fi
    
    if [ "$1" = "rebuild" ] || [ "$1" = "clean" ]; then
        build_images "fresh"
    else
        build_images
    fi
    
    start_services
    wait_for_services
    check_database
    init_database
    health_check
    show_summary
}

# Handle arguments
case "${1:-}" in
    help|-h|--help)
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  (no args)  - Normal setup with existing data"
        echo "  clean      - Stop and remove containers, optionally reset database"
        echo "  rebuild    - Fresh build from scratch"
        echo "  help       - Show this help message"
        ;;
    *)
        main "$@"
        ;;
esac
