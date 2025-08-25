#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
ENV_FILE="${PROJECT_ROOT}/.env"

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_header() {
    echo -e "${PURPLE}🚀 $1${NC}"
}

# Function to check if Docker is running
check_docker() {
    log_info "Checking Docker status..."
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    log_success "Docker is running"
}

# Function to check if docker-compose is available
check_docker_compose() {
    log_info "Checking Docker Compose availability..."
    if command -v docker-compose > /dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    elif docker compose version > /dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    else
        log_error "Docker Compose is not available"
        exit 1
    fi
    log_success "Using: $COMPOSE_CMD"
}

# Function to create environment file if it doesn't exist
setup_environment() {
    log_info "Setting up environment..."
    
    if [ ! -f "$ENV_FILE" ]; then
        log_warning "Environment file not found. Creating default .env file..."
        cat > "$ENV_FILE" << EOF
# Database Configuration
POSTGRES_DB=vru_validation
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password_change_me

# Redis Configuration
REDIS_PASSWORD=secure_redis_password

# Application Configuration
AIVALIDATION_SECRET_KEY=GENERATE_SECURE_KEY_FOR_PRODUCTION
APP_ENV=development

# Host Configuration
DATABASE_HOST=127.0.0.1
REDIS_HOST=127.0.0.1
BACKEND_HOST=127.0.0.1
FRONTEND_HOST=127.0.0.1
CVAT_HOST=127.0.0.1

# Development Configuration
REACT_DEBUG=false
REACT_LOG_LEVEL=warning
NODE_ENV=development
GENERATE_SOURCEMAP=false
EOF
        log_success "Created default environment file"
    else
        log_success "Environment file exists"
    fi
}

# Function to stop and cleanup containers
cleanup_containers() {
    log_info "Cleaning up existing containers..."
    
    # Stop all services
    $COMPOSE_CMD -f "$COMPOSE_FILE" down --remove-orphans || true
    
    # Remove any dangling containers
    docker container prune -f || true
    
    log_success "Container cleanup completed"
}

# Function to build images
build_images() {
    log_info "Building Docker images..."
    
    $COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache --parallel
    
    log_success "Image build completed"
}

# Function to start services in proper order
start_services() {
    log_header "Starting VRU Validation Platform Services"
    
    # Start core infrastructure first
    log_info "Starting core infrastructure (PostgreSQL, Redis)..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d postgres redis
    
    # Wait for core services to be healthy
    log_info "Waiting for core services to be healthy..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec postgres pg_isready -h localhost -p 5432 -U postgres || {
        log_warning "Waiting for PostgreSQL to be ready..."
        sleep 10
        $COMPOSE_CMD -f "$COMPOSE_FILE" exec postgres pg_isready -h localhost -p 5432 -U postgres
    }
    
    log_success "Core infrastructure is ready"
    
    # Start application services
    log_info "Starting application services (Backend, Frontend)..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d backend
    
    # Wait for backend to be ready
    log_info "Waiting for backend to be ready..."
    sleep 30
    
    # Start frontend
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d frontend
    
    log_success "All services started successfully"
}

# Function to show service status
show_status() {
    log_header "Service Status"
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps
    
    echo ""
    log_header "Service Health Checks"
    
    # Check PostgreSQL
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec postgres pg_isready -h localhost -p 5432 -U postgres > /dev/null 2>&1; then
        log_success "PostgreSQL: Healthy"
    else
        log_error "PostgreSQL: Unhealthy"
    fi
    
    # Check Redis
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec redis redis-cli ping | grep -q PONG > /dev/null 2>&1; then
        log_success "Redis: Healthy"
    else
        log_error "Redis: Unhealthy"
    fi
    
    # Check Backend
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "Backend: Healthy"
    else
        log_warning "Backend: Starting or Unhealthy"
    fi
    
    # Check Frontend
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        log_success "Frontend: Healthy"
    else
        log_warning "Frontend: Starting or Unhealthy"
    fi
}

# Function to view logs
view_logs() {
    local service=${1:-}
    if [ -n "$service" ]; then
        log_info "Showing logs for service: $service"
        $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f "$service"
    else
        log_info "Showing logs for all services"
        $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f
    fi
}

# Function to restart services
restart_services() {
    local service=${1:-}
    if [ -n "$service" ]; then
        log_info "Restarting service: $service"
        $COMPOSE_CMD -f "$COMPOSE_FILE" restart "$service"
    else
        log_info "Restarting all services..."
        cleanup_containers
        start_services
    fi
}

# Function to show help
show_help() {
    echo "Docker Orchestrator for VRU Validation Platform"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start           Start all services in proper order"
    echo "  stop            Stop all services"
    echo "  restart [svc]   Restart all services or specific service"
    echo "  status          Show service status and health"
    echo "  logs [service]  View logs for all services or specific service"
    echo "  build           Build Docker images"
    echo "  clean           Stop services and clean up containers"
    echo "  setup           Setup environment and build images"
    echo "  help            Show this help message"
    echo ""
    echo "Services: postgres, redis, backend, frontend, cvat"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start all services"
    echo "  $0 logs backend       # View backend logs"
    echo "  $0 restart postgres   # Restart only PostgreSQL"
    echo "  $0 status             # Check service health"
}

# Main execution
case "${1:-start}" in
    "start")
        check_docker
        check_docker_compose
        setup_environment
        start_services
        show_status
        ;;
    "stop")
        check_docker
        check_docker_compose
        log_info "Stopping all services..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" down
        log_success "All services stopped"
        ;;
    "restart")
        check_docker
        check_docker_compose
        restart_services "$2"
        show_status
        ;;
    "status")
        check_docker
        check_docker_compose
        show_status
        ;;
    "logs")
        check_docker
        check_docker_compose
        view_logs "$2"
        ;;
    "build")
        check_docker
        check_docker_compose
        build_images
        ;;
    "clean")
        check_docker
        check_docker_compose
        cleanup_containers
        log_success "Cleanup completed"
        ;;
    "setup")
        check_docker
        check_docker_compose
        setup_environment
        build_images
        log_success "Setup completed"
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac