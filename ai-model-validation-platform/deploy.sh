#!/bin/bash

# VRU AI Model Validation Platform - Unified Deployment Script
# Supports all environments with 155.138.239.131 external access

set -e

ENVIRONMENT="${1:-development}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 VRU Platform Deployment"
echo "=========================="
echo "Environment: $ENVIRONMENT"
echo "Working Directory: $SCRIPT_DIR"
echo ""

# Set environment variables
export HOST_UID=$(id -u)
export HOST_GID=$(id -g)
export COMPOSE_PROJECT_NAME="vru-validation-platform"

# Environment-specific configuration
case $ENVIRONMENT in
    "development")
        export COMPOSE_PROFILES="development"
        export VRU_ENVIRONMENT="development"
        export VRU_DEBUG="true"
        export MOUNT_SOURCE="rw"
        ENV_FILE=".env.unified"
        ;;
    "staging")
        export COMPOSE_PROFILES="staging,postgresql"
        export VRU_ENVIRONMENT="staging"
        export VRU_DEBUG="false"
        export MOUNT_SOURCE="ro"
        ENV_FILE=".env.staging"
        ;;
    "production")
        export COMPOSE_PROFILES="production,postgresql,nginx"
        export VRU_ENVIRONMENT="production"
        export VRU_DEBUG="false"
        export MOUNT_SOURCE="ro"
        ENV_FILE=".env.production"
        ;;
    *)
        echo "❌ Unknown environment: $ENVIRONMENT"
        echo "Valid environments: development, staging, production"
        exit 1
        ;;
esac

# Use unified env file as fallback
if [[ ! -f "$ENV_FILE" ]]; then
    echo "⚠️  Environment file $ENV_FILE not found, using .env.unified"
    ENV_FILE=".env.unified"
fi

echo "📁 Using environment file: $ENV_FILE"
echo "🔧 Profiles: $COMPOSE_PROFILES"
echo ""

# Ensure required directories exist
mkdir -p backend/uploads
mkdir -p models
mkdir -p logs

# Ensure database file exists for SQLite
if [[ "$VRU_ENVIRONMENT" == "development" ]]; then
    if [[ ! -f "backend/dev_database.db" ]]; then
        echo "📊 Creating SQLite database file..."
        touch backend/dev_database.db
        chmod 664 backend/dev_database.db
    fi
fi

# Copy environment file to .env for docker-compose
cp "$ENV_FILE" .env

echo "🐳 Starting Docker Compose..."
echo ""

# Use docker compose (new version) or docker-compose (old version)
if command -v docker &> /dev/null; then
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    elif docker-compose version &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        echo "❌ Neither 'docker compose' nor 'docker-compose' found"
        exit 1
    fi
else
    echo "❌ Docker not found"
    exit 1
fi

# Stop existing containers
echo "🛑 Stopping existing containers..."
$DOCKER_COMPOSE -f docker-compose.unified.yml --env-file .env down

# Build and start services
echo "🏗️  Building and starting services..."
$DOCKER_COMPOSE -f docker-compose.unified.yml --env-file .env up --build -d

echo ""
echo "⏳ Waiting for services to be healthy..."

# Wait for services to be ready
sleep 10

# Check service health
echo ""
echo "🔍 Checking service health..."

services=("vru_redis" "vru_backend" "vru_frontend")
for service in "${services[@]}"; do
    echo -n "  $service: "
    if $DOCKER_COMPOSE -f docker-compose.unified.yml --env-file .env ps "$service" | grep -q "healthy\|Up"; then
        echo "✅ Running"
    else
        echo "❌ Failed"
    fi
done

echo ""
echo "🌐 Service URLs:"
echo "  Frontend:  http://155.138.239.131:3000"
echo "  Backend:   http://155.138.239.131:8000"
echo "  API Docs:  http://155.138.239.131:8000/docs"
echo "  Health:    http://155.138.239.131:8000/health"

if [[ "$ENVIRONMENT" == "production" ]]; then
    echo "  Nginx:     http://155.138.239.131"
    echo "  CVAT:      http://155.138.239.131:8080"
fi

echo ""
echo "📋 Useful Commands:"
echo "  View logs:    $DOCKER_COMPOSE -f docker-compose.unified.yml --env-file .env logs -f"
echo "  Stop all:     $DOCKER_COMPOSE -f docker-compose.unified.yml --env-file .env down"
echo "  Restart:      $DOCKER_COMPOSE -f docker-compose.unified.yml --env-file .env restart"
echo "  Shell access: $DOCKER_COMPOSE -f docker-compose.unified.yml --env-file .env exec backend bash"
echo ""
echo "🎉 Deployment complete!"

# Show running containers
echo ""
echo "🐳 Running Containers:"
$DOCKER_COMPOSE -f docker-compose.unified.yml --env-file .env ps