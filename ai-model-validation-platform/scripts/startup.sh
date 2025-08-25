#!/bin/bash

# AI Model Validation Platform - Smart Startup Script
# Automatically detects environment and starts appropriate configuration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"; exit 1; }
info() { echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"; }

# Environment detection
detect_environment() {
    log "Detecting deployment environment..."
    
    # Check for Vultr server
    EXTERNAL_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "unknown")
    
    # Check if this is the Vultr server
    if [[ "$EXTERNAL_IP" == "155.138.239.131" ]]; then
        ENVIRONMENT="vultr"
        COMPOSE_FILE="docker-compose.vultr.yml"
        ENV_FILE=".env.vultr"
        info "Detected: Vultr production server (IP: $EXTERNAL_IP)"
    # Check for production environment variables
    elif [[ "${NODE_ENV:-}" == "production" ]] || [[ "${APP_ENV:-}" == "production" ]]; then
        ENVIRONMENT="production"
        COMPOSE_FILE="docker-compose.prod.yml"
        ENV_FILE=".env.production"
        info "Detected: Production environment"
    # Check for staging
    elif [[ "${NODE_ENV:-}" == "staging" ]] || [[ "${APP_ENV:-}" == "staging" ]]; then
        ENVIRONMENT="staging"
        COMPOSE_FILE="docker-compose.staging.yml"
        ENV_FILE=".env.staging"
        info "Detected: Staging environment"
    # Default to development
    else
        ENVIRONMENT="development"
        COMPOSE_FILE="docker-compose.yml"
        ENV_FILE=".env"
        info "Detected: Development environment"
    fi
    
    # Check if files exist
    if [[ ! -f "$PROJECT_ROOT/$COMPOSE_FILE" ]]; then
        error "Docker Compose file not found: $COMPOSE_FILE"
    fi
    
    if [[ ! -f "$PROJECT_ROOT/$ENV_FILE" ]]; then
        warn "Environment file not found: $ENV_FILE"
        if [[ -f "$PROJECT_ROOT/.env.example" ]]; then
            info "Copying from .env.example..."
            cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/$ENV_FILE"
        else
            error "No environment file available"
        fi
    fi
    
    export ENVIRONMENT COMPOSE_FILE ENV_FILE
    log "Environment: $ENVIRONMENT"
    log "Compose file: $COMPOSE_FILE"
    log "Environment file: $ENV_FILE"
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose is not installed"
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running"
    fi
    
    # Check disk space
    AVAILABLE_SPACE=$(df "$PROJECT_ROOT" | awk 'NR==2{print $4}')
    REQUIRED_SPACE=2097152  # 2GB in KB
    if [[ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]]; then
        warn "Low disk space: $(($AVAILABLE_SPACE/1024/1024))GB available"
    fi
    
    # Check memory
    AVAILABLE_MEMORY=$(free -m | awk 'NR==2{print $7}')
    REQUIRED_MEMORY=1024  # 1GB
    if [[ $AVAILABLE_MEMORY -lt $REQUIRED_MEMORY ]]; then
        warn "Low available memory: ${AVAILABLE_MEMORY}MB available"
    fi
    
    log "System requirements check passed"
}

# Validate environment configuration
validate_config() {
    log "Validating configuration..."
    
    cd "$PROJECT_ROOT"
    source "$ENV_FILE"
    
    # Check required variables based on environment
    if [[ "$ENVIRONMENT" == "vultr" || "$ENVIRONMENT" == "production" ]]; then
        REQUIRED_VARS=(
            "POSTGRES_PASSWORD"
            "REDIS_PASSWORD"
            "AIVALIDATION_SECRET_KEY"
        )
        
        for var in "${REQUIRED_VARS[@]}"; do
            if [[ -z "${!var:-}" ]] || [[ "${!var}" =~ (change_me|GENERATE|your-) ]]; then
                error "Please configure $var in $ENV_FILE"
            fi
        done
        
        # Check SSL configuration
        if [[ "${ENABLE_SSL:-}" == "true" ]] && [[ ! -f "/etc/nginx/ssl/cert.pem" ]]; then
            warn "SSL enabled but certificate not found. Run ssl-setup.sh first."
        fi
    fi
    
    log "Configuration validation passed"
}

# Prepare services
prepare_services() {
    log "Preparing services..."
    
    cd "$PROJECT_ROOT"
    
    # Create required directories
    mkdir -p logs/{nginx,postgres,redis,backend,frontend,cvat}
    mkdir -p uploads
    
    # Set permissions
    if [[ "$ENVIRONMENT" == "vultr" || "$ENVIRONMENT" == "production" ]]; then
        # Production permissions
        chmod 750 logs/
        chmod 755 uploads/
    else
        # Development permissions
        chmod 755 logs/ uploads/
    fi
    
    # Check for existing services
    if docker-compose -f "$COMPOSE_FILE" ps -q | grep -q .; then
        info "Services are already running"
        
        read -p "Restart services? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Stopping existing services..."
            docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
        else
            info "Keeping existing services running"
            return 0
        fi
    fi
    
    log "Services preparation completed"
}

# Start services
start_services() {
    log "Starting services..."
    
    cd "$PROJECT_ROOT"
    
    # Pull latest images
    if [[ "$ENVIRONMENT" == "vultr" || "$ENVIRONMENT" == "production" ]]; then
        info "Pulling latest images..."
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull
    fi
    
    # Build images if needed
    info "Building images..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
    
    # Start services in correct order
    info "Starting database services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d postgres redis
    
    # Wait for database services
    info "Waiting for database services to be ready..."
    sleep 15
    
    # Check database health
    for i in {1..12}; do
        if docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}" &>/dev/null; then
            log "✓ PostgreSQL is ready"
            break
        fi
        if [[ $i -eq 12 ]]; then
            error "PostgreSQL failed to start"
        fi
        info "Waiting for PostgreSQL... ($i/12)"
        sleep 5
    done
    
    for i in {1..6}; do
        if docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T redis redis-cli ping &>/dev/null; then
            log "✓ Redis is ready"
            break
        fi
        if [[ $i -eq 6 ]]; then
            error "Redis failed to start"
        fi
        info "Waiting for Redis... ($i/6)"
        sleep 5
    done
    
    # Start backend service
    info "Starting backend service..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d backend
    
    # Wait for backend
    info "Waiting for backend to be ready..."
    sleep 20
    
    for i in {1..12}; do
        if curl -f -s "http://localhost:8000/health" &>/dev/null; then
            log "✓ Backend is ready"
            break
        fi
        if [[ $i -eq 12 ]]; then
            error "Backend failed to start"
        fi
        info "Waiting for backend... ($i/12)"
        sleep 10
    done
    
    # Start frontend service
    info "Starting frontend service..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d frontend
    
    # Start remaining services based on environment
    if [[ "$ENVIRONMENT" == "vultr" || "$ENVIRONMENT" == "production" ]]; then
        info "Starting production services..."
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d nginx
        
        # Optional services
        if [[ "${ENABLE_MONITORING:-true}" == "true" ]]; then
            info "Starting monitoring services..."
            docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d prometheus grafana loki promtail
        fi
        
        if [[ "${ENABLE_CVAT:-true}" == "true" ]]; then
            info "Starting CVAT services..."
            docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d cvat_db cvat
        fi
    else
        # Development services
        info "Starting development services..."
        docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    fi
    
    log "All services started successfully"
}

# Run health checks
run_health_checks() {
    log "Running health checks..."
    
    cd "$PROJECT_ROOT"
    
    # Wait a bit for services to fully start
    sleep 10
    
    # Check service status
    info "Service status:"
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
    
    # Check health endpoints
    HEALTH_CHECKS=(
        "http://localhost:8000/health:Backend API"
        "http://localhost:3000:Frontend"
    )
    
    if [[ "$ENVIRONMENT" == "vultr" || "$ENVIRONMENT" == "production" ]]; then
        HEALTH_CHECKS+=(
            "http://localhost/health:Nginx Proxy"
            "https://localhost/health:HTTPS"
        )
    fi
    
    for check in "${HEALTH_CHECKS[@]}"; do
        URL="${check%:*}"
        NAME="${check#*:}"
        
        info "Checking $NAME ($URL)..."
        if curl -f -s --connect-timeout 10 "$URL" &>/dev/null; then
            log "✓ $NAME is healthy"
        else
            warn "✗ $NAME is not responding"
        fi
    done
    
    # External access check for production
    if [[ "$ENVIRONMENT" == "vultr" ]]; then
        info "Checking external access..."
        EXTERNAL_IP=$(curl -s ifconfig.me || echo "unknown")
        
        if curl -f -s --connect-timeout 10 "http://$EXTERNAL_IP/health" &>/dev/null; then
            log "✓ External HTTP access working"
        else
            warn "✗ External HTTP access failed"
        fi
        
        if [[ "${ENABLE_SSL:-}" == "true" ]]; then
            if curl -f -s -k --connect-timeout 10 "https://$EXTERNAL_IP/health" &>/dev/null; then
                log "✓ External HTTPS access working"
            else
                warn "✗ External HTTPS access failed"
            fi
        fi
    fi
    
    log "Health checks completed"
}

# Display status
display_status() {
    log "Deployment Status"
    echo "=================================="
    echo "Environment: $ENVIRONMENT"
    echo "Compose File: $COMPOSE_FILE"
    echo "Environment File: $ENV_FILE"
    echo ""
    
    # Service URLs
    if [[ "$ENVIRONMENT" == "vultr" ]]; then
        echo "Application URLs:"
        echo "- Frontend: https://155.138.239.131/"
        echo "- API: https://155.138.239.131/api/"
        echo "- CVAT: https://155.138.239.131/cvat/"
        echo "- Monitoring: https://155.138.239.131/grafana/"
    else
        echo "Application URLs:"
        echo "- Frontend: http://localhost:3000/"
        echo "- API: http://localhost:8000/"
        echo "- CVAT: http://localhost:8080/"
    fi
    
    echo ""
    echo "Running Services:"
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.State}}\t{{.Ports}}"
    
    echo ""
    echo "Logs:"
    echo "- View all: docker-compose -f $COMPOSE_FILE logs -f"
    echo "- Backend: docker-compose -f $COMPOSE_FILE logs -f backend"
    echo "- Frontend: docker-compose -f $COMPOSE_FILE logs -f frontend"
    
    echo ""
    echo "Management Commands:"
    echo "- Stop: docker-compose -f $COMPOSE_FILE down"
    echo "- Restart: $0 --restart"
    echo "- Status: docker-compose -f $COMPOSE_FILE ps"
    echo "- Logs: docker-compose -f $COMPOSE_FILE logs -f [service]"
    
    if [[ "$ENVIRONMENT" == "vultr" || "$ENVIRONMENT" == "production" ]]; then
        echo ""
        echo "Production Tools:"
        echo "- SSL Setup: sudo ./scripts/ssl/ssl-setup.sh"
        echo "- Backup: sudo /usr/local/bin/backup-ai-validation.sh"
        echo "- Monitoring: https://155.138.239.131/grafana/"
    fi
    
    echo "=================================="
}

# Cleanup function
cleanup() {
    log "Cleaning up unused resources..."
    docker system prune -f --volumes
    docker image prune -f
    log "Cleanup completed"
}

# Stop services
stop_services() {
    log "Stopping services..."
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    log "Services stopped"
}

# Restart services
restart_services() {
    log "Restarting services..."
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    start_services
    log "Services restarted"
}

# Show help
show_help() {
    echo "AI Model Validation Platform - Smart Startup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help       Show this help message"
    echo "  -e, --env ENV    Override environment detection (development|staging|production|vultr)"
    echo "  -f, --force      Force restart even if services are running"
    echo "  -c, --cleanup    Clean up unused Docker resources"
    echo "  -s, --stop       Stop all services"
    echo "  -r, --restart    Restart all services"
    echo "  -t, --status     Show status only"
    echo "  --health         Run health checks only"
    echo "  --no-pull        Skip pulling latest images (development only)"
    echo "  --no-build       Skip building images"
    echo ""
    echo "Examples:"
    echo "  $0                    # Auto-detect and start"
    echo "  $0 --env production   # Force production mode"
    echo "  $0 --restart          # Restart all services"
    echo "  $0 --cleanup          # Clean unused resources"
    echo "  $0 --status           # Show current status"
}

# Main function
main() {
    log "Starting AI Model Validation Platform..."
    
    detect_environment
    check_requirements
    validate_config
    prepare_services
    start_services
    run_health_checks
    display_status
    
    log "Platform started successfully!"
    
    if [[ "$ENVIRONMENT" == "vultr" ]]; then
        echo ""
        echo "🚀 Production deployment is ready!"
        echo "   Access your application at: https://155.138.239.131/"
        echo "   Don't forget to configure your domain and SSL certificates!"
    fi
}

# Parse command line arguments
FORCE_RESTART=false
NO_PULL=false
NO_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -e|--env)
            ENVIRONMENT="$2"
            case $ENVIRONMENT in
                development)
                    COMPOSE_FILE="docker-compose.yml"
                    ENV_FILE=".env"
                    ;;
                staging)
                    COMPOSE_FILE="docker-compose.staging.yml"
                    ENV_FILE=".env.staging"
                    ;;
                production)
                    COMPOSE_FILE="docker-compose.prod.yml"
                    ENV_FILE=".env.production"
                    ;;
                vultr)
                    COMPOSE_FILE="docker-compose.vultr.yml"
                    ENV_FILE=".env.vultr"
                    ;;
                *)
                    error "Invalid environment: $ENVIRONMENT"
                    ;;
            esac
            shift 2
            ;;
        -f|--force)
            FORCE_RESTART=true
            shift
            ;;
        -c|--cleanup)
            cleanup
            exit 0
            ;;
        -s|--stop)
            detect_environment
            stop_services
            exit 0
            ;;
        -r|--restart)
            detect_environment
            restart_services
            run_health_checks
            display_status
            exit 0
            ;;
        -t|--status)
            detect_environment
            display_status
            exit 0
            ;;
        --health)
            detect_environment
            run_health_checks
            exit 0
            ;;
        --no-pull)
            NO_PULL=true
            shift
            ;;
        --no-build)
            NO_BUILD=true
            shift
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Export flags
export FORCE_RESTART NO_PULL NO_BUILD

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi