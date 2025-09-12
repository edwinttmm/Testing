#!/bin/bash
# ===========================================
# VRU Platform Quick Deploy Script
# Unified deployment with health checks
# ===========================================

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
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
COMPOSE_FILE="docker/docker-compose.unified-fixed.yml"
ENV_FILE=".env.production"
PROJECT_NAME="vru-platform-unified"
TIMEOUT=300

log_info "🚀 VRU AI Model Validation Platform - Quick Deploy"
log_info "================================================="

# Check if running as root (not recommended)
if [[ $EUID -eq 0 ]]; then
    log_warning "Running as root. Consider using a non-root user for better security."
fi

# Verify Docker is running
if ! docker info > /dev/null 2>&1; then
    log_error "Docker daemon is not running. Please start Docker and try again."
    exit 1
fi

# Verify Docker Compose is available  
if ! docker compose version > /dev/null 2>&1; then
    log_error "Docker Compose is not available. Please install Docker Compose and try again."
    exit 1
fi

# Check if compose file exists
if [[ ! -f "$COMPOSE_FILE" ]]; then
    log_error "Docker Compose file not found: $COMPOSE_FILE"
    log_info "Make sure you're running this script from the project root directory."
    exit 1
fi

# Check environment file
if [[ ! -f "$ENV_FILE" ]]; then
    log_warning "Environment file not found: $ENV_FILE"
    log_info "Using default environment variables. Consider creating $ENV_FILE for production."
else
    log_info "Using environment file: $ENV_FILE"
fi

# Check available disk space (at least 5GB recommended)
AVAILABLE_SPACE=$(df . | tail -1 | awk '{print $4}')
REQUIRED_SPACE=5242880  # 5GB in KB

if [[ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]]; then
    log_warning "Low disk space detected. At least 5GB is recommended."
    log_info "Available: $(( AVAILABLE_SPACE / 1024 / 1024 ))GB, Recommended: 5GB"
fi

# Stop existing containers
log_info "🛑 Stopping existing containers..."
docker compose -f "$COMPOSE_FILE" --env-file="$ENV_FILE" down --remove-orphans || true

# Clean up old containers and images (optional)
read -p "Clean up old Docker images? This will free disk space but increase build time (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "🧹 Cleaning up old Docker images..."
    docker image prune -f
    docker volume prune -f --filter "label!=keep"
fi

# Pull base images to speed up build
log_info "📥 Pulling base images..."
docker pull python:3.11-slim || log_warning "Failed to pull Python base image"
docker pull node:20-alpine || log_warning "Failed to pull Node base image"  
docker pull postgres:15-alpine || log_warning "Failed to pull PostgreSQL image"
docker pull redis:7-alpine || log_warning "Failed to pull Redis image"

# Build and start services
log_info "🔨 Building and starting services..."
if [[ -f "$ENV_FILE" ]]; then
    docker compose -f "$COMPOSE_FILE" --env-file="$ENV_FILE" up --build -d
else
    docker compose -f "$COMPOSE_FILE" up --build -d
fi

# Wait for services to be healthy
log_info "⏳ Waiting for services to be healthy (timeout: ${TIMEOUT}s)..."
start_time=$(date +%s)

wait_for_health() {
    local service_name=$1
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if docker compose -f "$COMPOSE_FILE" ps | grep "$service_name" | grep -q "healthy"; then
            log_success "$service_name is healthy"
            return 0
        fi
        
        ((attempt++))
        echo -n "."
        sleep 10
        
        # Check if container exited
        if docker compose -f "$COMPOSE_FILE" ps | grep "$service_name" | grep -q "Exit"; then
            log_error "$service_name container exited. Check logs with: docker compose -f $COMPOSE_FILE logs $service_name"
            return 1
        fi
    done
    
    log_warning "$service_name health check timeout after $((max_attempts * 10)) seconds"
    return 1
}

# Check individual service health
wait_for_health "postgres" &
wait_for_health "redis" &
wait_for_health "backend" &
wait_for_health "frontend" &

# Wait for all background jobs
wait

# Final verification
log_info "🔍 Verifying deployment..."

# Check container status
CONTAINER_STATUS=$(docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}")
echo "$CONTAINER_STATUS"

# Test API endpoints
log_info "🌐 Testing service endpoints..."

# Test backend health
if curl -f -s "http://localhost:8000/health" > /dev/null 2>&1; then
    log_success "Backend API is responding"
else
    log_warning "Backend API may not be fully ready. Try: curl http://localhost:8000/health"
fi

# Test frontend  
if curl -f -s "http://localhost:3000/health" > /dev/null 2>&1; then
    log_success "Frontend is responding"
else
    log_warning "Frontend may not be fully ready. Try: curl http://localhost:3000"
fi

# Display running services
log_info "📊 Running services:"
docker compose -f "$COMPOSE_FILE" ps

# Calculate deployment time
end_time=$(date +%s)
deployment_time=$((end_time - start_time))

log_success "✅ Deployment completed in ${deployment_time} seconds!"

# Display access URLs
echo ""
log_info "🌐 Access URLs:"
echo "   Frontend:    http://localhost:3000"
echo "   Backend API: http://localhost:8000/docs"
echo "   External:    http://155.138.239.131:3000 (if configured)"
echo ""

log_info "📝 Useful commands:"
echo "   View logs:    docker compose -f $COMPOSE_FILE logs -f"
echo "   Stop all:     docker compose -f $COMPOSE_FILE down"
echo "   Restart:      docker compose -f $COMPOSE_FILE restart"
echo "   Status:       docker compose -f $COMPOSE_FILE ps"
echo ""

# Check for common issues
log_info "🔧 Troubleshooting:"
if ! curl -f -s "http://localhost:8000/health" > /dev/null 2>&1; then
    echo "   If backend is not responding:"
    echo "   - Check logs: docker compose -f $COMPOSE_FILE logs backend"
    echo "   - Verify database connection"
    echo "   - Check environment variables"
fi

if ! curl -f -s "http://localhost:3000" > /dev/null 2>&1; then
    echo "   If frontend is not responding:"
    echo "   - Check logs: docker compose -f $COMPOSE_FILE logs frontend"
    echo "   - Verify build completed successfully"
    echo "   - Check nginx configuration"
fi

log_info "🎉 VRU Platform deployment complete!"