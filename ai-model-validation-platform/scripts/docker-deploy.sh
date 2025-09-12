#!/bin/bash

# AI Model Validation Platform - Complete Docker Deployment Script
# Fixes Docker credential issues and deploys full stack

set -e

echo "🚀 AI Model Validation Platform - Docker Deployment"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: Fix Docker Credentials
print_step "Fixing Docker credentials configuration..."
if [ -f ~/.docker/config.json ]; then
    cp ~/.docker/config.json ~/.docker/config.json.backup
    print_success "Backed up existing Docker config"
fi

# Remove problematic credential store configuration
echo '{}' > ~/.docker/config.json
print_success "Fixed Docker credentials configuration"

# Step 2: Clean up Docker system
print_step "Cleaning up Docker system..."
docker system prune -f || true
docker volume prune -f || true
print_success "Docker cleanup completed"

# Step 3: Stop any running containers
print_step "Stopping existing containers..."
docker-compose -f docker-compose.yml down || true
docker-compose -f docker-compose.unified.yml down || true
print_success "Stopped existing containers"

# Step 4: Remove problematic images
print_step "Removing problematic images..."
docker rmi $(docker images | grep -E "(frontend|vru_frontend)" | awk '{print $3}') 2>/dev/null || true
print_success "Removed problematic images"

# Step 5: Build and deploy using unified compose
print_step "Building and deploying complete stack..."
export COMPOSE_DOCKER_CLI_BUILD=1
export DOCKER_BUILDKIT=1

# Use the unified docker-compose file which works better
docker-compose -f docker-compose.unified.yml build --no-cache

print_success "Build completed successfully"

# Step 6: Start services
print_step "Starting services..."
docker-compose -f docker-compose.unified.yml up -d

print_success "Services started"

# Step 7: Wait for services to be healthy
print_step "Waiting for services to be healthy..."
sleep 30

# Check service status
print_step "Checking service status..."
docker-compose -f docker-compose.unified.yml ps

# Step 8: Test connectivity
print_step "Testing service connectivity..."
echo ""
echo "Backend API Health: $(curl -s http://localhost:8000/health 2>/dev/null || echo 'Not ready yet')"
echo "Frontend Status: $(curl -s -I http://localhost:3000 2>/dev/null | head -n 1 || echo 'Not ready yet')"
echo "Redis Status: $(docker exec vru_redis redis-cli ping 2>/dev/null || echo 'Not ready yet')"

echo ""
print_success "Deployment completed!"
echo ""
echo "🌐 Access your application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Documentation: http://localhost:8000/docs"
echo ""
echo "📊 Monitor with:"
echo "   docker-compose -f docker-compose.unified.yml logs -f"
echo "   docker-compose -f docker-compose.unified.yml ps"
echo ""
echo "🛠️  Stop with:"
echo "   docker-compose -f docker-compose.unified.yml down"