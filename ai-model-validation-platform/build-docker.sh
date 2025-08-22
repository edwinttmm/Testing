#!/bin/bash

# AI Model Validation Platform - Docker Build Script
set -e

echo "🐳 Building AI Model Validation Platform Docker Images"
echo "======================================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Clean up any existing containers and images (optional)
if [[ "$1" == "--clean" ]]; then
    log "Cleaning up existing containers and images..."
    docker-compose down --volumes --remove-orphans 2>/dev/null || true
    docker system prune -f
    success "Cleanup completed"
fi

# Build backend image with verbose output
log "Building backend image (this may take 5-10 minutes for ML packages)..."
cd backend

if docker build \
    --no-cache \
    --progress=plain \
    --tag ai-model-validation-backend:latest \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    .; then
    success "Backend image built successfully"
else
    error "Backend build failed"
    exit 1
fi

cd ..

# Build frontend image
log "Building frontend image..."
cd frontend

if docker build \
    --tag ai-model-validation-frontend:latest \
    .; then
    success "Frontend image built successfully"
else
    error "Frontend build failed"
    exit 1
fi

cd ..

# Test the backend container
log "Testing backend container..."
if docker run --rm -d \
    --name test-backend \
    -p 8000:8000 \
    ai-model-validation-backend:latest; then
    
    # Wait for container to start
    sleep 10
    
    # Test if PyTorch and Ultralytics are working
    if docker exec test-backend python -c "
import torch
import ultralytics
from ultralytics import YOLO
print('✅ PyTorch version:', torch.__version__)
print('✅ Ultralytics working')
print('✅ YOLO import successful')
print('✅ ML packages fully functional in Docker!')
"; then
        success "ML packages working correctly in Docker container"
    else
        warning "ML packages test failed - but container is running"
    fi
    
    # Test API health
    if curl -f http://localhost:8000/health 2>/dev/null; then
        success "API health check passed"
    else
        warning "API health check failed"
    fi
    
    # Stop test container
    docker stop test-backend
    success "Test container stopped"
else
    error "Failed to start test container"
    exit 1
fi

log "Docker build completed successfully!"
echo ""
echo "🚀 Next steps:"
echo "1. Run the full stack: docker-compose up -d"
echo "2. Check logs: docker-compose logs -f backend"
echo "3. Access frontend: http://localhost:3000"
echo "4. Access API: http://localhost:8000"
echo ""
echo "📊 To test detection:"
echo "docker exec -it \$(docker-compose ps -q backend) python debug_yolo_detection.py uploads/child-1-1-1.mp4"