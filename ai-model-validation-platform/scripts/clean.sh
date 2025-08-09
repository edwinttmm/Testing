#!/bin/bash

# AI Model Validation Platform - Clean Script

echo "🧹 Cleaning AI Model Validation Platform..."

# Set environment variables
export COMPOSE_PROJECT_NAME=vru_validation

# Warning message
echo "⚠️  WARNING: This will remove all containers, volumes, and data!"
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Stop and remove all containers, networks, and volumes
    docker-compose down -v --remove-orphans
    
    # Remove Docker images
    docker-compose down --rmi all
    
    # Remove uploaded files (optional)
    read -p "Remove uploaded files? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf uploads/*
        echo "📁 Uploaded files removed"
    fi
    
    echo "✅ Cleanup completed!"
    echo ""
    echo "To start fresh: ./scripts/start.sh"
else
    echo "❌ Cleanup cancelled"
fi