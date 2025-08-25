#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"

# Determine compose command
if command -v docker-compose > /dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
elif docker compose version > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}❌ Docker Compose is not available${NC}"
    exit 1
fi

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
    echo -e "${PURPLE}🧪 $1${NC}"
}

# Function to test database connectivity
test_database() {
    log_header "Testing Database Connectivity"
    
    # Test PostgreSQL connection from host
    log_info "Testing PostgreSQL connection from host..."
    if pg_isready -h localhost -p 5432 -U postgres > /dev/null 2>&1; then
        log_success "PostgreSQL is reachable from host"
    else
        log_error "PostgreSQL is not reachable from host"
        return 1
    fi
    
    # Test PostgreSQL connection from backend container
    log_info "Testing PostgreSQL connection from backend container..."
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec backend pg_isready -h postgres -p 5432 -U postgres > /dev/null 2>&1; then
        log_success "PostgreSQL is reachable from backend container"
    else
        log_error "PostgreSQL is not reachable from backend container"
        return 1
    fi
    
    # Test actual database operations
    log_info "Testing database operations..."
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec postgres psql -U postgres -d vru_validation -c "SELECT 1;" > /dev/null 2>&1; then
        log_success "Database operations working"
    else
        log_error "Database operations failed"
        return 1
    fi
}

# Function to test Redis connectivity
test_redis() {
    log_header "Testing Redis Connectivity"
    
    # Test Redis from host
    log_info "Testing Redis connection from host..."
    if redis-cli -p 6379 ping | grep -q PONG > /dev/null 2>&1; then
        log_success "Redis is reachable from host"
    else
        log_warning "Redis is not reachable from host (may require password)"
    fi
    
    # Test Redis from backend container
    log_info "Testing Redis connection from backend container..."
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec backend redis-cli -h redis -p 6379 ping | grep -q PONG > /dev/null 2>&1; then
        log_success "Redis is reachable from backend container"
    else
        log_error "Redis is not reachable from backend container"
        return 1
    fi
}

# Function to test backend API
test_backend() {
    log_header "Testing Backend API"
    
    # Test health endpoint
    log_info "Testing backend health endpoint..."
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "Backend health endpoint responding"
    else
        log_error "Backend health endpoint not responding"
        return 1
    fi
    
    # Test API documentation
    log_info "Testing API documentation endpoint..."
    if curl -f http://localhost:8000/docs > /dev/null 2>&1; then
        log_success "API documentation accessible"
    else
        log_warning "API documentation not accessible"
    fi
    
    # Test database connection from API
    log_info "Testing database connectivity through API..."
    response=$(curl -s http://localhost:8000/api/health/database 2>/dev/null || echo "failed")
    if echo "$response" | grep -q "healthy\|ok" > /dev/null 2>&1; then
        log_success "Database connection through API working"
    else
        log_warning "Database connection through API may have issues"
    fi
}

# Function to test frontend
test_frontend() {
    log_header "Testing Frontend"
    
    # Test frontend accessibility
    log_info "Testing frontend accessibility..."
    if curl -f http://localhost:3000 > /dev/null 2>&1; then
        log_success "Frontend is accessible"
    else
        log_error "Frontend is not accessible"
        return 1
    fi
    
    # Test static assets
    log_info "Testing frontend static assets..."
    if curl -f http://localhost:3000/static/js/bundle.js > /dev/null 2>&1; then
        log_success "Frontend static assets loading"
    else
        log_warning "Frontend static assets may not be fully loaded"
    fi
}

# Function to test inter-service communication
test_inter_service() {
    log_header "Testing Inter-Service Communication"
    
    # Test backend to database
    log_info "Testing backend to PostgreSQL communication..."
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec backend python -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(os.environ.get('DATABASE_URL', ''))
    cur = conn.cursor()
    cur.execute('SELECT 1')
    print('Database connection successful')
    conn.close()
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
" > /dev/null 2>&1; then
        log_success "Backend to PostgreSQL communication working"
    else
        log_error "Backend to PostgreSQL communication failed"
        return 1
    fi
    
    # Test backend to Redis
    log_info "Testing backend to Redis communication..."
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec backend python -c "
import redis
import os
try:
    redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379')
    r = redis.from_url(redis_url)
    r.ping()
    print('Redis connection successful')
except Exception as e:
    print(f'Redis connection failed: {e}')
    exit(1)
" > /dev/null 2>&1; then
        log_success "Backend to Redis communication working"
    else
        log_error "Backend to Redis communication failed"
        return 1
    fi
}

# Function to test network configuration
test_network() {
    log_header "Testing Network Configuration"
    
    # Check if custom network exists
    log_info "Checking custom network configuration..."
    if docker network ls | grep -q "vru_validation_network"; then
        log_success "Custom network 'vru_validation_network' exists"
    else
        log_warning "Custom network not found, using default"
    fi
    
    # Test DNS resolution between containers
    log_info "Testing DNS resolution between containers..."
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec backend nslookup postgres > /dev/null 2>&1; then
        log_success "DNS resolution working (backend can resolve postgres)"
    else
        log_error "DNS resolution failed"
        return 1
    fi
}

# Function to run comprehensive validation
run_full_validation() {
    log_header "Running Comprehensive Connectivity Validation"
    
    local failed_tests=0
    
    # Run all tests
    test_network || ((failed_tests++))
    test_database || ((failed_tests++))
    test_redis || ((failed_tests++))
    test_inter_service || ((failed_tests++))
    test_backend || ((failed_tests++))
    test_frontend || ((failed_tests++))
    
    # Summary
    echo ""
    log_header "Validation Summary"
    if [ $failed_tests -eq 0 ]; then
        log_success "All connectivity tests passed! 🎉"
        echo ""
        echo "🌐 Application URLs:"
        echo "   Frontend: http://localhost:3000"
        echo "   Backend API: http://localhost:8000"
        echo "   API Docs: http://localhost:8000/docs"
        echo ""
    else
        log_error "Failed tests: $failed_tests"
        echo ""
        echo "🔧 Troubleshooting suggestions:"
        echo "   1. Check container status: docker-compose ps"
        echo "   2. View logs: docker-compose logs [service]"
        echo "   3. Restart services: ./scripts/docker-orchestrator.sh restart"
        echo ""
        return 1
    fi
}

# Function to show detailed service information
show_service_info() {
    log_header "Service Information"
    
    echo ""
    echo "📊 Container Status:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps
    
    echo ""
    echo "🔗 Network Information:"
    docker network ls | grep vru
    
    echo ""
    echo "💾 Volume Information:"
    docker volume ls | grep vru
    
    echo ""
    echo "🔍 Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $(docker ps --format "{{.Names}}" | grep vru) 2>/dev/null || echo "No running containers found"
}

# Function to run quick health check
quick_health_check() {
    log_header "Quick Health Check"
    
    local services=("postgres" "redis" "backend" "frontend")
    
    for service in "${services[@]}"; do
        if $COMPOSE_CMD -f "$COMPOSE_FILE" ps $service | grep -q "Up"; then
            log_success "$service: Running"
        else
            log_error "$service: Not running"
        fi
    done
}

# Function to show help
show_help() {
    echo "Container Connectivity Validator for VRU Validation Platform"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  full        Run comprehensive connectivity validation (default)"
    echo "  quick       Run quick health check"
    echo "  database    Test database connectivity only"
    echo "  redis       Test Redis connectivity only"
    echo "  backend     Test backend API only"
    echo "  frontend    Test frontend only"
    echo "  network     Test network configuration only"
    echo "  info        Show detailed service information"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Run full validation"
    echo "  $0 quick        # Quick health check"
    echo "  $0 database     # Test database only"
    echo "  $0 info         # Show service information"
}

# Main execution
case "${1:-full}" in
    "full")
        run_full_validation
        ;;
    "quick")
        quick_health_check
        ;;
    "database")
        test_database
        ;;
    "redis")
        test_redis
        ;;
    "backend")
        test_backend
        ;;
    "frontend")
        test_frontend
        ;;
    "network")
        test_network
        ;;
    "info")
        show_service_info
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