#!/bin/bash
# =====================================================================
# AI Model Validation Platform - DOCKER ORCHESTRATION SCRIPT
# =====================================================================
# This script fixes all Docker orchestration issues identified in root cause analysis

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.final.yml"
ENV_FILE=".env.production.fixed"
NETWORK_NAME="vru_network"
PROJECT_NAME="ai-model-validation-platform"

# Functions
print_header() {
    echo -e "${BLUE}=============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=============================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "CHECKING PREREQUISITES"
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    print_success "Docker is available"
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    print_success "Docker Compose is available"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_error "Compose file $COMPOSE_FILE not found"
        exit 1
    fi
    print_success "Compose file found: $COMPOSE_FILE"
    
    if [ ! -f "$ENV_FILE" ]; then
        print_warning "Environment file $ENV_FILE not found, using defaults"
    else
        print_success "Environment file found: $ENV_FILE"
    fi
}

# Clean up old containers and networks
cleanup_old_resources() {
    print_header "CLEANING UP OLD RESOURCES"
    
    # Stop and remove old containers
    print_info "Stopping old containers..."
    docker-compose -f docker-compose.yml down --remove-orphans 2>/dev/null || true
    docker-compose -f docker-compose.unified.yml down --remove-orphans 2>/dev/null || true
    docker-compose -f docker-compose.production.yml down --remove-orphans 2>/dev/null || true
    
    # Remove old networks
    print_info "Removing old networks..."
    docker network rm ai_validation_network 2>/dev/null || true
    docker network rm vru_validation_network 2>/dev/null || true
    docker network rm ai-model-validation-platform_default 2>/dev/null || true
    
    # Clean up unused volumes (optional)
    print_info "Cleaning up unused Docker resources..."
    docker system prune -f --volumes 2>/dev/null || true
    
    print_success "Cleanup completed"
}

# Create required directories
create_directories() {
    print_header "CREATING REQUIRED DIRECTORIES"
    
    mkdir -p models uploads logs config/nginx
    print_success "Created application directories"
    
    # Create nginx config if it doesn't exist
    if [ ! -f "config/nginx/nginx.conf" ]; then
        cat > config/nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }
    
    upstream frontend {
        server frontend:3000;
    }
    
    server {
        listen 80;
        server_name 155.138.239.131;
        
        location /api/ {
            proxy_pass http://backend/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        location / {
            proxy_pass http://frontend/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
EOF
        print_success "Created nginx configuration"
    fi
}

# Build and start services
start_services() {
    print_header "BUILDING AND STARTING SERVICES"
    
    # Export environment file
    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
        print_success "Loaded environment variables from $ENV_FILE"
    fi
    
    # Build images
    print_info "Building Docker images..."
    docker-compose -f "$COMPOSE_FILE" build --parallel
    print_success "Images built successfully"
    
    # Start services
    print_info "Starting services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    print_success "Services started"
}

# Wait for services to be healthy
wait_for_services() {
    print_header "WAITING FOR SERVICES TO BE HEALTHY"
    
    services=("postgres" "redis" "backend" "frontend")
    
    for service in "${services[@]}"; do
        print_info "Waiting for $service to be healthy..."
        
        timeout=300  # 5 minutes
        elapsed=0
        interval=10
        
        while [ $elapsed -lt $timeout ]; do
            if docker-compose -f "$COMPOSE_FILE" ps "$service" | grep -q "Up (healthy)"; then
                print_success "$service is healthy"
                break
            fi
            
            if [ $elapsed -eq $timeout ]; then
                print_error "$service failed to become healthy within $timeout seconds"
                print_info "Service logs for $service:"
                docker-compose -f "$COMPOSE_FILE" logs --tail=50 "$service"
                exit 1
            fi
            
            sleep $interval
            elapsed=$((elapsed + interval))
            print_info "Still waiting for $service... (${elapsed}s/${timeout}s)"
        done
    done
    
    print_success "All services are healthy"
}

# Run health checks
run_health_checks() {
    print_header "RUNNING HEALTH CHECKS"
    
    # Backend health check
    print_info "Checking backend health..."
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        print_success "Backend health check passed"
    else
        print_error "Backend health check failed"
        print_info "Backend logs:"
        docker-compose -f "$COMPOSE_FILE" logs --tail=20 backend
    fi
    
    # Frontend health check
    print_info "Checking frontend health..."
    if curl -f http://localhost:3000/health >/dev/null 2>&1; then
        print_success "Frontend health check passed"
    else
        print_error "Frontend health check failed"
        print_info "Frontend logs:"
        docker-compose -f "$COMPOSE_FILE" logs --tail=20 frontend
    fi
    
    # Database connectivity check
    print_info "Checking database connectivity..."
    if docker-compose -f "$COMPOSE_FILE" exec -T backend python -c "import database; print('Database OK')" 2>/dev/null; then
        print_success "Database connectivity check passed"
    else
        print_error "Database connectivity check failed"
        print_info "Database logs:"
        docker-compose -f "$COMPOSE_FILE" logs --tail=20 postgres
    fi
}

# Display service status
show_status() {
    print_header "SERVICE STATUS"
    docker-compose -f "$COMPOSE_FILE" ps
    
    print_header "NETWORK INFORMATION"
    docker network ls | grep vru
    
    print_header "ACCESS INFORMATION"
    echo -e "${GREEN}Frontend: http://localhost:3000${NC}"
    echo -e "${GREEN}Backend API: http://localhost:8000${NC}"
    echo -e "${GREEN}Backend Docs: http://localhost:8000/docs${NC}"
    echo -e "${GREEN}External Access: http://155.138.239.131:3000${NC}"
}

# Main execution
main() {
    print_header "AI MODEL VALIDATION PLATFORM - DOCKER ORCHESTRATION"
    
    case "${1:-start}" in
        "start")
            check_prerequisites
            cleanup_old_resources
            create_directories
            start_services
            wait_for_services
            run_health_checks
            show_status
            ;;
        "stop")
            print_header "STOPPING SERVICES"
            docker-compose -f "$COMPOSE_FILE" down
            print_success "Services stopped"
            ;;
        "restart")
            print_header "RESTARTING SERVICES"
            docker-compose -f "$COMPOSE_FILE" down
            main start
            ;;
        "status")
            show_status
            ;;
        "logs")
            docker-compose -f "$COMPOSE_FILE" logs -f "${2:-}"
            ;;
        "health")
            run_health_checks
            ;;
        "clean")
            print_header "DEEP CLEANING"
            docker-compose -f "$COMPOSE_FILE" down -v --remove-orphans
            docker system prune -af --volumes
            print_success "Deep clean completed"
            ;;
        *)
            echo "Usage: $0 {start|stop|restart|status|logs|health|clean}"
            echo "  start   - Start all services (default)"
            echo "  stop    - Stop all services"
            echo "  restart - Restart all services"
            echo "  status  - Show service status"
            echo "  logs    - Show service logs (add service name for specific service)"
            echo "  health  - Run health checks"
            echo "  clean   - Deep clean (removes volumes and images)"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"