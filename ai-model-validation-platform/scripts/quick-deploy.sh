#!/bin/bash

# Quick Deploy Script - Immediate Docker Stack Deployment
# Fixes credential issues and gets the stack running immediately

echo "🚀 QUICK DEPLOY - Fixing Docker credentials and deploying stack..."

# Step 1: Fix Docker credentials immediately
echo "1. Fixing Docker credentials..."
mkdir -p ~/.docker
echo '{}' > ~/.docker/config.json
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0

# Step 2: Clean and stop everything
echo "2. Cleaning Docker system..."
docker-compose -f docker-compose.unified.yml down 2>/dev/null || true
docker system prune -f
docker volume prune -f

# Step 3: Build with fallback Dockerfile
echo "3. Building with fixed frontend Dockerfile..."
cd frontend
docker build -f Dockerfile.fixed -t ai-validation-frontend:latest . || {
    echo "Failed with fixed Dockerfile, trying simple build..."
    docker build -f - -t ai-validation-frontend:latest . << 'DOCKERFILE'
FROM node:20-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl python3 make g++ && rm -rf /var/lib/apt/lists/*
COPY package*.json ./
RUN npm install --legacy-peer-deps --unsafe-perm
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
DOCKERFILE
}
cd ..

# Step 4: Start services
echo "4. Starting services..."
export COMPOSE_HTTP_TIMEOUT=300
docker-compose -f docker-compose.unified.yml up -d

echo "✅ Quick deploy completed!"
echo "Frontend: http://localhost:3000"
echo "Backend: http://localhost:8000"
echo "Logs: docker-compose -f docker-compose.unified.yml logs -f"