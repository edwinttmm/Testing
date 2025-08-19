#!/bin/bash
set -e

echo "🔧 Fixing syntax error and restarting backend..."

# Get the container ID
CONTAINER_ID=$(docker ps -qf "name=vru_validation_backend_1")

if [[ -z "$CONTAINER_ID" ]]; then
    echo "❌ Backend container not found"
    exit 1
fi

echo "📋 Container ID: $CONTAINER_ID"

# Copy the fixed main.py to the container
echo "📂 Copying fixed main.py to container..."
docker cp main.py $CONTAINER_ID:/app/main.py

# Restart the container to reload the code
echo "🔄 Restarting backend container..."
docker restart $CONTAINER_ID

# Wait a moment for container to start
sleep 5

# Check if container is running
if docker ps | grep -q $CONTAINER_ID; then
    echo "✅ Backend container restarted successfully"
    echo "🔍 Checking logs..."
    docker logs --tail 10 $CONTAINER_ID
else
    echo "❌ Backend container failed to restart"
    docker logs --tail 20 $CONTAINER_ID
    exit 1
fi

echo "🎉 Syntax error fixed and backend restarted!"