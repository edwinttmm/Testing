#!/bin/bash
# Simple Development Mode Startup Script
# This script configures and starts the application with Docker-matching credentials

set -e

echo "🚀 Starting AI Model Validation Platform - Simple Development Mode"
echo "=================================================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Set environment file for simple mode
export ENV_FILE=".env.development.simple"
export COMPOSE_FILE="docker-compose.simple.yml"

# Copy simple development environment if main .env doesn't exist
if [ ! -f ".env" ] || [ "$1" = "--force-config" ]; then
    echo "📋 Setting up simple development environment..."
    cp .env.development.simple .env
    echo "✅ Environment configuration updated"
fi

# Ensure proper database credentials in backend
echo "🔧 Updating backend configuration..."
cp .env.development.simple backend/.env

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.simple.yml down --remove-orphans

# Remove any existing volumes if requested
if [ "$1" = "--clean" ]; then
    echo "🧹 Cleaning up existing data volumes..."
    docker-compose -f docker-compose.simple.yml down -v
    docker volume prune -f
fi

# Build and start services
echo "🏗️  Building and starting services..."
docker-compose -f docker-compose.simple.yml up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🔍 Checking service health..."
echo "Database container:"
docker-compose -f docker-compose.simple.yml exec postgres pg_isready -U postgres || echo "⚠️  Database not ready yet"

echo "Backend API:"
curl -s http://localhost:8000/health || echo "⚠️  Backend not ready yet"

echo ""
echo "🎉 Simple development mode started successfully!"
echo "=================================================="
echo "📊 Services:"
echo "   • Backend API:    http://localhost:8000"
echo "   • Frontend UI:    http://localhost:3000"
echo "   • API Docs:       http://localhost:8000/docs"
echo "   • PostgreSQL:     localhost:5432"
echo "   • Redis:          localhost:6379"
echo ""
echo "🔐 Database Credentials:"
echo "   • Host:           postgres (internal) / localhost (external)"
echo "   • Database:       vru_validation"
echo "   • Username:       postgres"
echo "   • Password:       password"
echo ""
echo "📝 To view logs:"
echo "   docker-compose -f docker-compose.simple.yml logs -f"
echo ""
echo "🛑 To stop services:"
echo "   docker-compose -f docker-compose.simple.yml down"
echo "=================================================="