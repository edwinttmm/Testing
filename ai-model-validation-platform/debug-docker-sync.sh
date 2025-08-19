#!/bin/bash

# DOCKER SYNC DEBUGGING SCRIPT
# Purpose: Diagnose Docker file synchronization issues

echo "🔍 DOCKER FILE SYNC DIAGNOSTIC"
echo "==============================="
echo ""

# Check if Docker is running
if ! docker --version > /dev/null 2>&1; then
    echo "❌ Docker is not available or not running"
    exit 1
fi

echo "📋 Current Docker Status:"
echo "-------------------------"
docker-compose ps
echo ""

echo "📁 Local File Timestamps (Fixed Files):"
echo "----------------------------------------"
echo "Dashboard.tsx: $(stat -c '%Y %n' frontend/src/pages/Dashboard.tsx 2>/dev/null || echo 'File not found')"
echo "Projects.tsx:  $(stat -c '%Y %n' frontend/src/pages/Projects.tsx 2>/dev/null || echo 'File not found')"
echo "errorTypes.ts: $(stat -c '%Y %n' frontend/src/utils/errorTypes.ts 2>/dev/null || echo 'File not found')"
echo ""

echo "🐳 Container File Timestamps (if container is running):"
echo "-------------------------------------------------------"
if docker-compose ps frontend | grep -q "Up"; then
    echo "Dashboard.tsx: $(docker-compose exec frontend stat -c '%Y %n' /app/src/pages/Dashboard.tsx 2>/dev/null || echo 'File not found in container')"
    echo "Projects.tsx:  $(docker-compose exec frontend stat -c '%Y %n' /app/src/pages/Projects.tsx 2>/dev/null || echo 'File not found in container')"
    echo "errorTypes.ts: $(docker-compose exec frontend stat -c '%Y %n' /app/src/utils/errorTypes.ts 2>/dev/null || echo 'File not found in container')"
else
    echo "❌ Frontend container is not running"
fi
echo ""

echo "🔍 Volume Mount Analysis:"
echo "------------------------"
echo "docker-compose.yml frontend volumes section:"
grep -A 5 "frontend:" docker-compose.yml
echo ""

echo "📦 .dockerignore Contents:"
echo "-------------------------"
if [ -f "frontend/.dockerignore" ]; then
    cat frontend/.dockerignore
else
    echo "❌ .dockerignore not found"
fi
echo ""

echo "🏗️ Dockerfile COPY Commands:"
echo "-----------------------------"
if [ -f "frontend/Dockerfile" ]; then
    grep "COPY" frontend/Dockerfile
else
    echo "❌ Dockerfile not found"
fi
echo ""

echo "📊 Docker Image Layers:"
echo "-----------------------"
if docker images | grep -q "ai-model-validation-platform"; then
    docker images | grep "ai-model-validation-platform"
    echo ""
    echo "🔍 Image history (recent layers):"
    IMAGE_ID=$(docker images | grep "ai-model-validation-platform.*frontend" | awk '{print $3}' | head -1)
    if [ -n "$IMAGE_ID" ]; then
        docker history "$IMAGE_ID" | head -10
    fi
else
    echo "❌ No project images found"
fi
echo ""

echo "🔄 Recent Container Logs (last 20 lines):"
echo "-----------------------------------------"
if docker-compose ps frontend | grep -q "Up"; then
    docker-compose logs --tail=20 frontend
else
    echo "❌ Frontend container is not running - cannot show logs"
fi
echo ""

echo "💡 RECOMMENDED ACTIONS:"
echo "======================"
echo "1. Run the docker-reset.sh script to force complete rebuild"
echo "2. Check if volume mounts are correctly configured"
echo "3. Verify .dockerignore doesn't exclude source files"
echo "4. Ensure Dockerfile COPY commands include all source"
echo ""
echo "🚀 Quick Fix Command:"
echo "./docker-reset.sh"