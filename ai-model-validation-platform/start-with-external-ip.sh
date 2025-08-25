#!/bin/bash

# AI Model Validation Platform - External IP Startup Script
# Configures and starts all services for external IP access (155.138.239.131)

set -e

echo "🚀 Starting AI Model Validation Platform with External IP Support"
echo "   Server IP: 155.138.239.131"
echo "   Frontend: http://155.138.239.131:3000"
echo "   Backend API: http://155.138.239.131:8000"
echo "=" * 60

# Set environment for external IP
export BACKEND_HOST=155.138.239.131
export FRONTEND_HOST=155.138.239.131
export DATABASE_HOST=155.138.239.131
export REDIS_HOST=155.138.239.131
export APP_ENV=production
export NODE_ENV=production

# CORS Configuration
export AIVALIDATION_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000,https://155.138.239.131:3000"
export ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000,https://155.138.239.131:3000"

echo "🔧 Environment Configuration:"
echo "   BACKEND_HOST: $BACKEND_HOST"
echo "   FRONTEND_HOST: $FRONTEND_HOST"
echo "   CORS Origins: $AIVALIDATION_CORS_ORIGINS"
echo ""

# Check if docker-compose exists
if [ ! -f docker-compose.yml ]; then
    echo "❌ docker-compose.yml not found!"
    exit 1
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down --remove-orphans 2>/dev/null || true

# Clean up old containers and images (optional)
echo "🧹 Cleaning up old containers..."
docker system prune -f >/dev/null 2>&1 || true

# Build and start services
echo "🏗️  Building and starting services..."
docker-compose --env-file .env.production up -d --build

# Wait for services to start
echo "⏳ Waiting for services to initialize..."
sleep 10

# Check service status
echo "🔍 Checking service status..."

# Check if containers are running
backend_running=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep ai_validation_backend | grep -c "Up" || echo "0")
frontend_running=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep ai_validation_frontend | grep -c "Up" || echo "0")
postgres_running=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep ai_validation_postgres | grep -c "Up" || echo "0")

echo "   Backend: $( [ $backend_running -eq 1 ] && echo "✅ Running" || echo "❌ Not Running" )"
echo "   Frontend: $( [ $frontend_running -eq 1 ] && echo "✅ Running" || echo "❌ Not Running" )"
echo "   Database: $( [ $postgres_running -eq 1 ] && echo "✅ Running" || echo "❌ Not Running" )"
echo ""

# Test external connectivity
echo "🌐 Testing external connectivity..."

# Test backend health endpoint
if curl -s -f "http://155.138.239.131:8000/health" >/dev/null; then
    echo "   Backend API: ✅ Accessible"
else
    echo "   Backend API: ❌ Not Accessible"
fi

# Test frontend
if curl -s -f "http://155.138.239.131:3000" >/dev/null; then
    echo "   Frontend: ✅ Accessible"
else
    echo "   Frontend: ❌ Not Accessible"
fi

# Test CORS
echo "   CORS Test: Running detailed test..."
if command -v python3 >/dev/null; then
    python3 test-cors-external-ip.py
else
    echo "   ⚠️  Python3 not available for CORS testing"
fi

echo ""
echo "🎉 Startup complete!"
echo "=" * 60
echo "🌐 External Access URLs:"
echo "   Frontend: http://155.138.239.131:3000"
echo "   Backend API: http://155.138.239.131:8000"
echo "   API Docs: http://155.138.239.131:8000/docs"
echo ""
echo "📝 To monitor logs:"
echo "   All services: docker-compose logs -f"
echo "   Backend only: docker-compose logs -f backend"
echo "   Frontend only: docker-compose logs -f frontend"
echo ""
echo "🛑 To stop services:"
echo "   docker-compose down"