#!/bin/bash

# AI Model Validation Platform - Production Deployment Script
# Target Server: 155.138.239.131
# Version: 1.0.0
# Created: 2025-08-27

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PRODUCTION_IP="155.138.239.131"
BACKEND_PORT="8000"
FRONTEND_PORT="3000"
DB_PORT="5432"
PROJECT_ROOT="/home/user/Testing/ai-model-validation-platform"
HEALTH_CHECK_TIMEOUT=30
MAX_RETRIES=5

# Log function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# Error handling
handle_error() {
    local line_number=$1
    error "Script failed at line $line_number"
    cleanup_on_failure
    exit 1
}

trap 'handle_error $LINENO' ERR

# Cleanup function
cleanup_on_failure() {
    log "Performing cleanup due to failure..."
    docker-compose -f docker-compose.unified.yml down --remove-orphans 2>/dev/null || true
}

# Check if script is run as root
check_privileges() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root for security reasons"
        exit 1
    fi
}

# Validate prerequisites
validate_prerequisites() {
    log "Validating prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check if project directory exists
    if [[ ! -d "$PROJECT_ROOT" ]]; then
        error "Project directory not found: $PROJECT_ROOT"
        exit 1
    fi
    
    # Check if unified docker-compose file exists
    if [[ ! -f "$PROJECT_ROOT/docker-compose.unified.yml" ]]; then
        error "Unified Docker Compose file not found"
        exit 1
    fi
    
    success "Prerequisites validated"
}

# Set up environment for production
setup_environment() {
    log "Setting up production environment..."
    
    cd "$PROJECT_ROOT"
    
    # Backup existing .env files
    for env_file in .env .env.production .env.unified; do
        if [[ -f "$env_file" ]]; then
            cp "$env_file" "${env_file}.backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
        fi
    done
    
    # Create production environment file
    cat > .env.production << EOF
# Production Environment Configuration
# Server: $PRODUCTION_IP
# Generated: $(date)

NODE_ENV=production
ENVIRONMENT=production

# Network Configuration
HOST=0.0.0.0
BACKEND_HOST=0.0.0.0
FRONTEND_HOST=0.0.0.0
PRODUCTION_IP=$PRODUCTION_IP

# Port Configuration
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT
DATABASE_PORT=$DB_PORT

# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@db:5432/ai_model_validation
DB_HOST=db
DB_PORT=5432
DB_NAME=ai_model_validation
DB_USER=postgres
DB_PASSWORD=postgres

# CORS Configuration
CORS_ORIGINS=http://$PRODUCTION_IP:$FRONTEND_PORT,http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_ALLOW_HEADERS=Content-Type,Authorization,X-Requested-With

# API Configuration
API_BASE_URL=http://$PRODUCTION_IP:$BACKEND_PORT
VITE_API_URL=http://$PRODUCTION_IP:$BACKEND_PORT

# Security
DEBUG=false
LOG_LEVEL=info

# Health Check Configuration
HEALTH_CHECK_INTERVAL=30
HEALTH_CHECK_TIMEOUT=10
HEALTH_CHECK_RETRIES=3

# Performance
MAX_WORKERS=4
WORKER_TIMEOUT=120
KEEP_ALIVE=2

# File Upload
MAX_FILE_SIZE=100MB
UPLOAD_TIMEOUT=300

EOF

    # Create symlink for unified env
    ln -sf .env.production .env.unified
    
    success "Production environment configured"
}

# Validate Docker Compose configuration
validate_docker_config() {
    log "Validating Docker Compose configuration..."
    
    cd "$PROJECT_ROOT"
    
    if ! docker-compose -f docker-compose.unified.yml config --quiet; then
        error "Invalid Docker Compose configuration"
        exit 1
    fi
    
    success "Docker Compose configuration is valid"
}

# Start services
start_services() {
    log "Starting production services..."
    
    cd "$PROJECT_ROOT"
    
    # Pull latest images
    log "Pulling Docker images..."
    docker-compose -f docker-compose.unified.yml pull --quiet
    
    # Build services
    log "Building services..."
    docker-compose -f docker-compose.unified.yml build --no-cache
    
    # Start services
    log "Starting containers..."
    docker-compose -f docker-compose.unified.yml up -d
    
    success "Services started successfully"
}

# Wait for service to be ready
wait_for_service() {
    local service_name=$1
    local url=$2
    local timeout=${3:-$HEALTH_CHECK_TIMEOUT}
    
    log "Waiting for $service_name to be ready..."
    
    local count=0
    while [[ $count -lt $timeout ]]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            success "$service_name is ready"
            return 0
        fi
        sleep 1
        ((count++))
    done
    
    error "$service_name failed to start within $timeout seconds"
    return 1
}

# Health checks
perform_health_checks() {
    log "Performing health checks..."
    
    # Wait for services to start
    sleep 10
    
    # Check database connectivity
    log "Checking database connectivity..."
    local retry_count=0
    while [[ $retry_count -lt $MAX_RETRIES ]]; do
        if docker-compose -f docker-compose.unified.yml exec -T db pg_isready -U postgres > /dev/null 2>&1; then
            success "Database is ready"
            break
        fi
        ((retry_count++))
        if [[ $retry_count -eq $MAX_RETRIES ]]; then
            error "Database health check failed after $MAX_RETRIES attempts"
            return 1
        fi
        sleep 5
    done
    
    # Check backend health
    wait_for_service "Backend" "http://$PRODUCTION_IP:$BACKEND_PORT/health"
    
    # Check frontend health
    wait_for_service "Frontend" "http://$PRODUCTION_IP:$FRONTEND_PORT"
    
    success "All health checks passed"
}

# Validate database connectivity and schema
validate_database() {
    log "Validating database connectivity and schema..."
    
    cd "$PROJECT_ROOT"
    
    # Test database connection
    if ! docker-compose -f docker-compose.unified.yml exec -T db psql -U postgres -d ai_model_validation -c "SELECT 1;" > /dev/null 2>&1; then
        error "Failed to connect to database"
        return 1
    fi
    
    # Check if tables exist
    local tables_exist=$(docker-compose -f docker-compose.unified.yml exec -T db psql -U postgres -d ai_model_validation -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' \n')
    
    if [[ "$tables_exist" -gt 0 ]]; then
        success "Database schema is present ($tables_exist tables found)"
    else
        warning "No tables found in database - schema may need initialization"
    fi
    
    success "Database validation completed"
}

# Test API endpoints
test_api_endpoints() {
    log "Testing API endpoints..."
    
    local base_url="http://$PRODUCTION_IP:$BACKEND_PORT"
    
    # Test health endpoint
    if ! curl -f -s "$base_url/health" > /dev/null; then
        error "Health endpoint test failed"
        return 1
    fi
    success "Health endpoint: OK"
    
    # Test API info endpoint
    if curl -f -s "$base_url/api/info" > /dev/null; then
        success "API info endpoint: OK"
    else
        warning "API info endpoint: Not available"
    fi
    
    # Test projects endpoint (GET should work without auth)
    if curl -f -s "$base_url/api/projects" > /dev/null; then
        success "Projects endpoint: OK"
    else
        warning "Projects endpoint: May require authentication"
    fi
    
    success "API endpoint tests completed"
}

# Test CORS configuration
test_cors_configuration() {
    log "Testing CORS configuration..."
    
    local base_url="http://$PRODUCTION_IP:$BACKEND_PORT"
    local frontend_origin="http://$PRODUCTION_IP:$FRONTEND_PORT"
    
    # Test preflight request
    local cors_response=$(curl -s -H "Origin: $frontend_origin" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type" \
        -X OPTIONS \
        "$base_url/api/projects" \
        -w "%{http_code}" -o /dev/null)
    
    if [[ "$cors_response" == "200" ]]; then
        success "CORS preflight: OK"
    else
        warning "CORS preflight returned status: $cors_response"
    fi
    
    success "CORS configuration test completed"
}

# Performance validation
validate_performance() {
    log "Running basic performance validation..."
    
    local base_url="http://$PRODUCTION_IP:$BACKEND_PORT"
    
    # Test response time
    local response_time=$(curl -w "%{time_total}" -s -o /dev/null "$base_url/health")
    
    if (( $(echo "$response_time < 2.0" | bc -l) )); then
        success "Response time: ${response_time}s (Good)"
    elif (( $(echo "$response_time < 5.0" | bc -l) )); then
        warning "Response time: ${response_time}s (Acceptable)"
    else
        warning "Response time: ${response_time}s (Slow)"
    fi
    
    success "Performance validation completed"
}

# Generate deployment report
generate_deployment_report() {
    log "Generating deployment report..."
    
    local report_file="deployment-report-$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
AI Model Validation Platform - Production Deployment Report
==========================================================

Deployment Date: $(date)
Target Server: $PRODUCTION_IP
Deployment Status: SUCCESS

Service Status:
$(docker-compose -f docker-compose.unified.yml ps)

Port Configuration:
- Backend: $PRODUCTION_IP:$BACKEND_PORT
- Frontend: $PRODUCTION_IP:$FRONTEND_PORT
- Database: Internal ($DB_PORT)

Health Check Results:
- Database: $(docker-compose -f docker-compose.unified.yml exec -T db pg_isready -U postgres 2>/dev/null && echo "OK" || echo "FAILED")
- Backend: $(curl -f -s "http://$PRODUCTION_IP:$BACKEND_PORT/health" >/dev/null 2>&1 && echo "OK" || echo "FAILED")
- Frontend: $(curl -f -s "http://$PRODUCTION_IP:$FRONTEND_PORT" >/dev/null 2>&1 && echo "OK" || echo "FAILED")

Access URLs:
- Frontend: http://$PRODUCTION_IP:$FRONTEND_PORT
- Backend API: http://$PRODUCTION_IP:$BACKEND_PORT
- Health Check: http://$PRODUCTION_IP:$BACKEND_PORT/health

Next Steps:
1. Monitor service logs: docker-compose -f docker-compose.unified.yml logs -f
2. Check service status: docker-compose -f docker-compose.unified.yml ps
3. Update DNS/Load Balancer to point to $PRODUCTION_IP
4. Set up monitoring and alerting
5. Configure backup procedures

EOF

    success "Deployment report generated: $report_file"
}

# Cleanup function for successful deployment
cleanup_on_success() {
    log "Cleaning up temporary files..."
    
    # Remove old backup files older than 7 days
    find . -name "*.backup.*" -type f -mtime +7 -delete 2>/dev/null || true
    
    success "Cleanup completed"
}

# Show service information
show_service_info() {
    log "Service Information:"
    echo ""
    echo "Frontend URL: http://$PRODUCTION_IP:$FRONTEND_PORT"
    echo "Backend API:  http://$PRODUCTION_IP:$BACKEND_PORT"
    echo "Health Check: http://$PRODUCTION_IP:$BACKEND_PORT/health"
    echo ""
    echo "Useful Commands:"
    echo "  View logs:    docker-compose -f docker-compose.unified.yml logs -f"
    echo "  Service status: docker-compose -f docker-compose.unified.yml ps"
    echo "  Stop services: docker-compose -f docker-compose.unified.yml down"
    echo "  Restart:      docker-compose -f docker-compose.unified.yml restart"
    echo ""
}

# Main deployment function
main() {
    log "Starting AI Model Validation Platform Production Deployment"
    log "Target Server: $PRODUCTION_IP"
    log "Timestamp: $(date)"
    
    check_privileges
    validate_prerequisites
    setup_environment
    validate_docker_config
    start_services
    perform_health_checks
    validate_database
    test_api_endpoints
    test_cors_configuration
    validate_performance
    generate_deployment_report
    cleanup_on_success
    
    success "Deployment completed successfully!"
    show_service_info
    
    log "Deployment script finished at $(date)"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "status")
        cd "$PROJECT_ROOT"
        docker-compose -f docker-compose.unified.yml ps
        ;;
    "logs")
        cd "$PROJECT_ROOT"
        docker-compose -f docker-compose.unified.yml logs -f
        ;;
    "stop")
        cd "$PROJECT_ROOT"
        docker-compose -f docker-compose.unified.yml down
        ;;
    "restart")
        cd "$PROJECT_ROOT"
        docker-compose -f docker-compose.unified.yml restart
        ;;
    "health")
        test_api_endpoints
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [command]"
        echo "Commands:"
        echo "  deploy   - Full deployment (default)"
        echo "  status   - Show service status"
        echo "  logs     - Show service logs"
        echo "  stop     - Stop services"
        echo "  restart  - Restart services"
        echo "  health   - Run health checks"
        echo "  help     - Show this help"
        ;;
    *)
        error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac