#!/bin/bash

# AI Model Validation Platform - Stop Script

echo "🛑 Stopping AI Model Validation Platform..."

# Set environment variables
export COMPOSE_PROJECT_NAME=vru_validation

# Stop all services
docker-compose down

echo "✅ All services stopped successfully!"
echo ""
echo "To start again: ./scripts/start.sh"
echo "To remove all data: ./scripts/clean.sh"