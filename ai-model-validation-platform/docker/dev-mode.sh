#!/bin/bash
# ===========================================
# VRU Platform Development Mode Script
# Quick setup for local development
# ===========================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

log_info "🔧 VRU Platform - Development Mode"
log_info "=================================="

# Create development override file
DEV_OVERRIDE_FILE="docker/docker-compose.dev-override.yml"

log_info "📝 Creating development override configuration..."

cat > "$DEV_OVERRIDE_FILE" << 'EOF'
# Development Override Configuration
# Adds development-specific settings

version: '3.8'

services:
  postgres:
    ports:
      - "127.0.0.1:5432:5432"
    environment:
      POSTGRES_DB: vru_validation_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: devpassword
    command: [
      "postgres",
      "-c", "log_statement=all",
      "-c", "log_destination=stderr",
      "-c", "logging_collector=off",
      "-c", "log_connections=on",
      "-c", "log_disconnections=on",
      "-c", "max_connections=100"
    ]

  redis:
    ports:
      - "127.0.0.1:6379:6379"
    command: [
      "redis-server",
      "--requirepass", "devredis",
      "--appendonly", "yes",
      "--loglevel", "notice"
    ]

  backend:
    build:
      target: development  # Use development stage
    environment:
      - VRU_ENVIRONMENT=development
      - VRU_DEBUG=true
      - LOG_LEVEL=DEBUG
      - AIVALIDATION_LOG_LEVEL=DEBUG
      - DATABASE_ECHO=true
      - VRU_DATABASE_URL=postgresql://postgres:devpassword@postgres:5432/vru_validation_dev
      - VRU_REDIS_URL=redis://:devredis@redis:6379/0
      - VRU_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
      - PYTHONPATH=/app
      - PYTHONUNBUFFERED=1
    volumes:
      # Mount source code for hot reload
      - ./backend:/app:rw
      - ./models:/app/models:rw
      - ./scripts:/app/scripts:rw
      - uploaded_videos:/app/uploads
    command: ["uvicorn", "main:socketio_app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]

  frontend:
    build:
      target: development  # Use development stage
    environment:
      - NODE_ENV=development
      - REACT_APP_API_URL=http://localhost:8000
      - REACT_APP_WS_URL=ws://localhost:8000
      - REACT_APP_SOCKETIO_URL=http://localhost:8001
      - REACT_APP_VIDEO_BASE_URL=http://localhost:8000
      - REACT_APP_ENVIRONMENT=development
      - REACT_APP_DEBUG=true
      - REACT_APP_LOG_LEVEL=debug
      - GENERATE_SOURCEMAP=true
      - FAST_REFRESH=true
      - CHOKIDAR_USEPOLLING=true
    volumes:
      # Mount source code for hot reload
      - ./frontend:/app:rw
      - /app/node_modules  # Preserve node_modules
    command: ["sh", "-c", "HOST=0.0.0.0 PORT=3000 npm start"]
EOF

# Create development environment file
DEV_ENV_FILE=".env.development"

log_info "🔧 Creating development environment file..."

cat > "$DEV_ENV_FILE" << 'EOF'
# Development Environment Variables
VRU_ENVIRONMENT=development
NODE_ENV=development
VRU_DEBUG=true

# Database Configuration (Development)
VRU_DATABASE_TYPE=postgresql
VRU_DATABASE_NAME=vru_validation_dev
VRU_DATABASE_USER=postgres
VRU_DATABASE_PASSWORD=devpassword
VRU_DATABASE_URL=postgresql://postgres:devpassword@postgres:5432/vru_validation_dev

# Redis Configuration (Development)
VRU_REDIS_PASSWORD=devredis
VRU_REDIS_URL=redis://:devredis@redis:6379/0

# Security (Development - not for production)
VRU_SECRET_KEY=development-secret-key-change-for-production-32-chars
JWT_SECRET_KEY=dev-jwt-secret-key-change-for-production

# External IP (for testing)
VRU_EXTERNAL_IP=localhost

# API Configuration
VRU_API_HOST=0.0.0.0
VRU_API_PORT=8000

# Frontend Configuration
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_SOCKETIO_URL=http://localhost:8001
REACT_APP_VIDEO_BASE_URL=http://localhost:8000
REACT_APP_ENVIRONMENT=development
REACT_APP_DEBUG=true
GENERATE_SOURCEMAP=true

# CORS Configuration (Development)
VRU_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000

# Performance Settings (Reduced for development)
UVICORN_WORKERS=1
VRU_ML_WORKERS=1
VRU_ML_BATCH_SIZE=2

# Logging
LOG_LEVEL=DEBUG
VRU_LOG_FORMAT=text

# Docker Configuration
COMPOSE_PROJECT_NAME=vru-development
DOCKER_BUILDKIT=1
COMPOSE_DOCKER_CLI_BUILD=1
EOF

# Stop any running containers
log_info "🛑 Stopping any existing containers..."
docker compose -f docker/docker-compose.unified-fixed.yml down --remove-orphans 2>/dev/null || true

# Start development environment
log_info "🚀 Starting development environment..."
docker compose \
  -f docker/docker-compose.unified-fixed.yml \
  -f "$DEV_OVERRIDE_FILE" \
  --env-file="$DEV_ENV_FILE" \
  up --build -d

# Wait for services to start
log_info "⏳ Waiting for services to start..."
sleep 30

# Check service health
log_info "🔍 Checking service health..."

# Check database
if docker compose -f docker/docker-compose.unified-fixed.yml ps postgres | grep -q "healthy"; then
    log_success "PostgreSQL is healthy"
else
    log_warning "PostgreSQL may still be starting up"
fi

# Check Redis
if docker compose -f docker/docker-compose.unified-fixed.yml ps redis | grep -q "healthy"; then
    log_success "Redis is healthy"
else
    log_warning "Redis may still be starting up"
fi

# Check backend
if curl -f -s "http://localhost:8000/health" > /dev/null 2>&1; then
    log_success "Backend API is responding"
else
    log_warning "Backend API may still be starting up"
    log_info "Try: curl http://localhost:8000/health"
fi

# Check frontend
if curl -f -s "http://localhost:3000" > /dev/null 2>&1; then
    log_success "Frontend is responding"  
else
    log_warning "Frontend may still be starting up"
    log_info "Try: curl http://localhost:3000"
fi

# Display running services
log_info "📊 Development services:"
docker compose \
  -f docker/docker-compose.unified-fixed.yml \
  -f "$DEV_OVERRIDE_FILE" \
  ps

log_success "✅ Development environment started!"

echo ""
log_info "🌐 Development URLs:"
echo "   Frontend:     http://localhost:3000"  
echo "   Backend API:  http://localhost:8000/docs"
echo "   Backend Health: http://localhost:8000/health"
echo ""

log_info "📝 Development commands:"
echo "   View logs:    docker compose -f docker/docker-compose.unified-fixed.yml -f $DEV_OVERRIDE_FILE logs -f"
echo "   Stop all:     docker compose -f docker/docker-compose.unified-fixed.yml down"
echo "   Restart:      docker compose -f docker/docker-compose.unified-fixed.yml -f $DEV_OVERRIDE_FILE restart"
echo "   Shell (backend): docker exec -it vru_backend_unified bash"
echo "   Shell (frontend): docker exec -it vru_frontend_unified sh"
echo ""

log_info "🔧 Development features enabled:"
echo "   ✓ Hot reload for both frontend and backend"
echo "   ✓ Debug logging enabled"
echo "   ✓ Source code mounted for live editing" 
echo "   ✓ Development database with detailed logs"
echo "   ✓ Relaxed CORS settings"
echo "   ✓ Reduced worker counts for faster startup"
echo ""

log_info "💡 Tips:"
echo "   - Edit files in ./backend/ or ./frontend/ and see changes instantly"
echo "   - Use 'docker compose logs -f backend' to see backend logs"
echo "   - Use 'docker compose logs -f frontend' to see frontend logs" 
echo "   - Database data persists between restarts"
echo ""

log_info "🎉 Happy coding!"