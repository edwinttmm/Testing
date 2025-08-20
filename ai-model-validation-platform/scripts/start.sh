#!/bin/bash

# AI Model Validation Platform - Start Script

echo "🚀 Starting AI Model Validation Platform..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose > /dev/null 2>&1; then
    echo "❌ docker-compose is not installed. Please install it first."
    exit 1
fi

# Create necessary directories
mkdir -p uploads
mkdir -p models

# Set environment variables
export COMPOSE_PROJECT_NAME=vru_validation

# Build and start all services
echo "📦 Building and starting services..."
docker-compose up -d --build

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🔍 Checking service health..."

# Check PostgreSQL
if docker-compose exec postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL is not ready"
fi

# Skip Redis check - not in current docker-compose
echo "⏭️  Redis not configured (skipping check)"

# Check Backend
if curl -f http://155.138.239.131:8000/health > /dev/null 2>&1; then
    echo "✅ Backend API is ready"
else
    echo "❌ Backend API is not ready"
fi

# Check Frontend
if curl -f http://155.138.239.131:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is ready"
else
    echo "❌ Frontend is not ready"
fi

echo ""
echo "🎉 AI Model Validation Platform is starting!"
echo ""
echo "📱 Frontend: http://155.138.239.131:3000"
echo "🔧 Backend API: http://155.138.239.131:8000"
echo "📚 API Documentation: http://155.138.239.131:8000/docs"
echo "🐘 PostgreSQL: 155.138.239.131:5432"
echo "📝 CVAT: http://155.138.239.131:8080 (optional)"
echo ""
echo "To stop the platform: ./scripts/stop.sh"
echo "To view logs: docker-compose logs -f"
echo ""