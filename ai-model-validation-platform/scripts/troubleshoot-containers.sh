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
    echo -e "${PURPLE}🔧 $1${NC}"
}

# Function to diagnose container issues
diagnose_containers() {
    log_header "Container Diagnostics"
    
    echo ""
    echo "📋 Container Status:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" ps
    
    echo ""
    echo "🔍 Container Health Status:"
    for container in vru_postgres vru_redis vru_backend vru_frontend; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-healthcheck")
            status=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
            echo "   $container: Status=$status, Health=$health"
        else
            echo "   $container: Not running"
        fi
    done
    
    echo ""
    echo "🌐 Network Configuration:"
    docker network ls | grep vru || echo "No VRU networks found"
    
    echo ""
    echo "💾 Volume Usage:"
    docker volume ls | grep vru || echo "No VRU volumes found"
}

# Function to check resource usage
check_resources() {
    log_header "Resource Usage Analysis"
    
    echo ""
    echo "💻 System Resources:"
    echo "   Memory Usage:"
    free -h
    echo ""
    echo "   Disk Usage:"
    df -h
    echo ""
    echo "   Docker System Usage:"
    docker system df
    
    echo ""
    echo "🐳 Container Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}" $(docker ps --format "{{.Names}}" | grep vru) 2>/dev/null || echo "No VRU containers running"
}

# Function to analyze logs for common issues
analyze_logs() {
    local service=$1
    log_header "Log Analysis for $service"
    
    echo ""
    echo "📝 Recent Logs (last 50 lines):"
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs --tail=50 "$service"
    
    echo ""
    echo "🔍 Error Pattern Analysis:"
    
    # Common error patterns
    local error_patterns=(
        "ERROR"
        "FATAL"
        "Connection refused"
        "Connection timed out"
        "No route to host"
        "Name resolution failed"
        "Permission denied"
        "Out of memory"
        "Disk full"
        "Cannot connect to database"
        "Redis connection failed"
    )
    
    for pattern in "${error_patterns[@]}"; do
        local count=$($COMPOSE_CMD -f "$COMPOSE_FILE" logs "$service" 2>/dev/null | grep -i "$pattern" | wc -l)
        if [ "$count" -gt 0 ]; then
            log_warning "Found $count instances of: $pattern"
        fi
    done
}

# Function to test connectivity between services
test_connectivity() {
    log_header "Inter-Service Connectivity Tests"
    
    # Test from backend to postgres
    echo ""
    log_info "Testing backend to PostgreSQL..."
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec backend pg_isready -h postgres -p 5432 -U postgres > /dev/null 2>&1; then
        log_success "Backend can reach PostgreSQL"
    else
        log_error "Backend cannot reach PostgreSQL"
        echo "   Troubleshooting steps:"
        echo "   1. Check if PostgreSQL container is running"
        echo "   2. Verify network connectivity"
        echo "   3. Check PostgreSQL logs"
    fi
    
    # Test from backend to redis
    log_info "Testing backend to Redis..."
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec backend redis-cli -h redis -p 6379 ping > /dev/null 2>&1; then
        log_success "Backend can reach Redis"
    else
        log_error "Backend cannot reach Redis"
        echo "   Troubleshooting steps:"
        echo "   1. Check if Redis container is running"
        echo "   2. Verify Redis password configuration"
        echo "   3. Check Redis logs"
    fi
    
    # Test frontend to backend
    log_info "Testing frontend to backend API..."
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "Frontend can reach backend API"
    else
        log_error "Frontend cannot reach backend API"
        echo "   Troubleshooting steps:"
        echo "   1. Check if backend container is running"
        echo "   2. Verify port mapping (8000)"
        echo "   3. Check backend health endpoint"
    fi
}

# Function to check environment configuration
check_environment() {
    log_header "Environment Configuration Check"
    
    echo ""
    echo "🔧 Environment File Status:"
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        log_success ".env file exists"
        echo "   Required variables check:"
        
        local required_vars=(
            "POSTGRES_PASSWORD"
            "REDIS_PASSWORD"
            "AIVALIDATION_SECRET_KEY"
        )
        
        for var in "${required_vars[@]}"; do
            if grep -q "^${var}=" "${PROJECT_ROOT}/.env"; then
                log_success "$var is set"
            else
                log_error "$var is missing or not set"
            fi
        done
    else
        log_error ".env file not found"
        echo "   Run: cp .env.example .env"
    fi
    
    echo ""
    echo "🐳 Docker Environment Variables:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" config | grep -A 5 -B 5 environment: || echo "No environment variables found in config"
}

# Function to provide specific troubleshooting for service
troubleshoot_service() {
    local service=$1
    
    case $service in
        postgres)
            log_header "PostgreSQL Troubleshooting"
            echo ""
            log_info "Checking PostgreSQL status..."
            
            if docker ps --format "{{.Names}}" | grep -q "vru_postgres"; then
                log_success "PostgreSQL container is running"
                
                # Check if accepting connections
                if $COMPOSE_CMD -f "$COMPOSE_FILE" exec postgres pg_isready -U postgres > /dev/null 2>&1; then
                    log_success "PostgreSQL is accepting connections"
                else
                    log_error "PostgreSQL is not accepting connections"
                    echo "   Common solutions:"
                    echo "   1. Wait for initialization to complete"
                    echo "   2. Check logs: docker-compose logs postgres"
                    echo "   3. Verify password configuration"
                fi
            else
                log_error "PostgreSQL container is not running"
                echo "   Common solutions:"
                echo "   1. Start container: docker-compose up -d postgres"
                echo "   2. Check for port conflicts on 5432"
                echo "   3. Review docker-compose.yml configuration"
            fi
            ;;
            
        redis)
            log_header "Redis Troubleshooting"
            echo ""
            log_info "Checking Redis status..."
            
            if docker ps --format "{{.Names}}" | grep -q "vru_redis"; then
                log_success "Redis container is running"
                
                # Check if accepting connections
                if $COMPOSE_CMD -f "$COMPOSE_FILE" exec redis redis-cli ping > /dev/null 2>&1; then
                    log_success "Redis is accepting connections"
                else
                    log_error "Redis is not accepting connections"
                    echo "   Common solutions:"
                    echo "   1. Check password configuration"
                    echo "   2. Verify Redis logs: docker-compose logs redis"
                    echo "   3. Test with: docker-compose exec redis redis-cli ping"
                fi
            else
                log_error "Redis container is not running"
                echo "   Common solutions:"
                echo "   1. Start container: docker-compose up -d redis"
                echo "   2. Check for port conflicts on 6379"
                echo "   3. Review docker-compose.yml configuration"
            fi
            ;;
            
        backend)
            log_header "Backend Troubleshooting"
            echo ""
            log_info "Checking backend status..."
            
            if docker ps --format "{{.Names}}" | grep -q "vru_backend"; then
                log_success "Backend container is running"
                
                # Check health endpoint
                if curl -f http://localhost:8000/health > /dev/null 2>&1; then
                    log_success "Backend health endpoint is responding"
                else
                    log_error "Backend health endpoint is not responding"
                    echo "   Common solutions:"
                    echo "   1. Wait for application startup"
                    echo "   2. Check backend logs: docker-compose logs backend"
                    echo "   3. Verify database connectivity"
                    echo "   4. Check wait-for-services.sh script"
                fi
            else
                log_error "Backend container is not running"
                echo "   Common solutions:"
                echo "   1. Check dependencies: postgres and redis must be healthy"
                echo "   2. Review backend logs: docker-compose logs backend"
                echo "   3. Verify environment variables"
            fi
            ;;
            
        frontend)
            log_header "Frontend Troubleshooting"
            echo ""
            log_info "Checking frontend status..."
            
            if docker ps --format "{{.Names}}" | grep -q "vru_frontend"; then
                log_success "Frontend container is running"
                
                # Check if accessible
                if curl -f http://localhost:3000 > /dev/null 2>&1; then
                    log_success "Frontend is accessible"
                else
                    log_error "Frontend is not accessible"
                    echo "   Common solutions:"
                    echo "   1. Wait for React build to complete"
                    echo "   2. Check frontend logs: docker-compose logs frontend"
                    echo "   3. Verify Node.js memory settings"
                    echo "   4. Check for JavaScript compilation errors"
                fi
            else
                log_error "Frontend container is not running"
                echo "   Common solutions:"
                echo "   1. Check backend dependency"
                echo "   2. Review frontend logs: docker-compose logs frontend"
                echo "   3. Verify Node.js version compatibility"
            fi
            ;;
            
        *)
            log_error "Unknown service: $service"
            echo "Available services: postgres, redis, backend, frontend"
            ;;
    esac
}

# Function to run complete diagnosis
run_complete_diagnosis() {
    log_header "Complete System Diagnosis"
    
    # Check Docker system
    log_info "Checking Docker daemon..."
    if docker info > /dev/null 2>&1; then
        log_success "Docker daemon is running"
    else
        log_error "Docker daemon is not running"
        echo "Please start Docker before continuing."
        exit 1
    fi
    
    # Run all diagnostic functions
    diagnose_containers
    echo ""
    check_resources
    echo ""
    check_environment
    echo ""
    test_connectivity
    
    # Analyze logs for each service
    local services=("postgres" "redis" "backend" "frontend")
    for service in "${services[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "vru_${service}"; then
            echo ""
            analyze_logs "$service"
        fi
    done
    
    echo ""
    log_header "Diagnosis Complete"
    echo ""
    echo "💡 Quick fixes to try:"
    echo "   1. Restart all services: ./scripts/docker-orchestrator.sh restart"
    echo "   2. Check logs: ./scripts/docker-orchestrator.sh logs"
    echo "   3. Validate connectivity: ./scripts/validate-connectivity.sh"
    echo "   4. Clean rebuild: ./scripts/docker-orchestrator.sh clean && ./scripts/docker-orchestrator.sh setup"
}

# Function to show help
show_help() {
    echo "Container Troubleshooting Tool for VRU Validation Platform"
    echo ""
    echo "Usage: $0 [COMMAND] [SERVICE]"
    echo ""
    echo "Commands:"
    echo "  diagnose     Run complete system diagnosis (default)"
    echo "  service      Troubleshoot specific service"
    echo "  logs         Analyze logs for service"
    echo "  resources    Check resource usage"
    echo "  connectivity Test inter-service connectivity"
    echo "  environment  Check environment configuration"
    echo "  help         Show this help message"
    echo ""
    echo "Services: postgres, redis, backend, frontend"
    echo ""
    echo "Examples:"
    echo "  $0                      # Complete diagnosis"
    echo "  $0 service postgres     # Troubleshoot PostgreSQL"
    echo "  $0 logs backend         # Analyze backend logs"
    echo "  $0 connectivity         # Test connectivity"
}

# Main execution
case "${1:-diagnose}" in
    "diagnose")
        run_complete_diagnosis
        ;;
    "service")
        if [ -z "$2" ]; then
            log_error "Please specify a service name"
            echo ""
            show_help
            exit 1
        fi
        troubleshoot_service "$2"
        ;;
    "logs")
        if [ -z "$2" ]; then
            log_error "Please specify a service name"
            echo ""
            show_help
            exit 1
        fi
        analyze_logs "$2"
        ;;
    "resources")
        check_resources
        ;;
    "connectivity")
        test_connectivity
        ;;
    "environment")
        check_environment
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