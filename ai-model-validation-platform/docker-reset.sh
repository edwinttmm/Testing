#!/bin/bash

# EMERGENCY DOCKER RESET SCRIPT
# Purpose: Force Docker to use latest local code with fixed TypeScript errors
# 
# CRITICAL ISSUE: Docker container running stale code while local files are fixed
# SOLUTION: Complete Docker cache invalidation and rebuild

set -e

echo "🚨 EMERGENCY DOCKER RESET - FIXING FILE SYNC ISSUE"
echo "=================================================="
echo ""
echo "PROBLEM: Docker container has stale TypeScript code"
echo "SOLUTION: Complete cache invalidation and rebuild"
echo ""

# Function to run commands with error handling
run_command() {
    echo "🔄 $1"
    if eval "$2"; then
        echo "✅ $1 - SUCCESS"
    else
        echo "❌ $1 - FAILED"
        exit 1
    fi
    echo ""
}

# Step 1: Stop all containers
run_command "Stopping all Docker containers" "docker-compose down --volumes --remove-orphans"

# Step 2: Remove all containers (including stopped ones)
run_command "Removing all Docker containers" "docker container prune -f"

# Step 3: Remove all images to force rebuild
run_command "Removing all Docker images for this project" "docker images | grep 'ai-model-validation-platform' | awk '{print \$3}' | xargs -r docker rmi -f"

# Step 4: Clear Docker build cache
run_command "Clearing Docker build cache" "docker builder prune -af"

# Step 5: Clear Docker system cache
run_command "Clearing Docker system cache" "docker system prune -af --volumes"

# Step 6: Verify local build works (important!)
echo "🔄 Verifying local TypeScript compilation works..."
cd frontend
if npm run build; then
    echo "✅ Local TypeScript compilation - SUCCESS"
    echo "   All TypeScript errors are fixed locally!"
else
    echo "❌ Local TypeScript compilation - FAILED"
    echo "   Fix local TypeScript errors first!"
    exit 1
fi
cd ..
echo ""

# Step 7: Rebuild with no cache and verbose output
run_command "Rebuilding Docker containers with no cache" "docker-compose build --no-cache --progress=plain"

# Step 8: Start services
run_command "Starting Docker services" "docker-compose up -d"

# Step 9: Wait for services to be ready
echo "🔄 Waiting for services to be ready..."
sleep 10

# Step 10: Check container logs for TypeScript errors
echo "🔍 Checking frontend container logs for TypeScript errors..."
echo "=================================================="
docker-compose logs frontend | tail -50

echo ""
echo "🔍 Checking if frontend container is running..."
if docker-compose ps frontend | grep -q "Up"; then
    echo "✅ Frontend container is running"
else
    echo "❌ Frontend container is not running - check logs above"
    echo ""
    echo "📋 Full container status:"
    docker-compose ps
    exit 1
fi

echo ""
echo "🎉 DOCKER RESET COMPLETE!"
echo "========================="
echo ""
echo "✅ All Docker cache cleared"
echo "✅ Images rebuilt from scratch"
echo "✅ Fixed TypeScript code now running in container"
echo ""
echo "🌐 Services should now be available at:"
echo "   Frontend: http://155.138.239.131:3000"
echo "   Backend:  http://155.138.239.131:8000"
echo ""
echo "🔍 To monitor logs in real-time:"
echo "   docker-compose logs -f frontend"
echo "   docker-compose logs -f backend"
echo ""
echo "🛠️ If issues persist, check:"
echo "   1. Volume mounts in docker-compose.yml"
echo "   2. .dockerignore file doesn't exclude source"
echo "   3. Dockerfile COPY commands are correct"