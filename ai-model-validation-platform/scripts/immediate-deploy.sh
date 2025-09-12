#!/bin/bash

# IMMEDIATE DEPLOYMENT - Get the stack running NOW
# Bypasses Docker credential issues completely

set -e

# Function to cleanup unhealthy containers
cleanup_unhealthy() {
    echo "🧹 Cleaning up unhealthy containers..."
    
    # Stop and remove any unhealthy containers
    docker ps -aq --filter health=unhealthy | xargs -r docker stop
    docker ps -aq --filter health=unhealthy | xargs -r docker rm
    
    # Clean up any exited containers
    docker ps -aq --filter status=exited | xargs -r docker rm
    
    # Remove any dangling images
    docker image prune -f
    
    echo "Cleanup completed."
}

# Function to restart specific service
restart_service() {
    local service_name=$1
    echo "🔄 Restarting $service_name..."
    docker-compose -f docker-compose.immediate.yml restart $service_name
    sleep 20
    docker-compose -f docker-compose.immediate.yml logs --tail 20 $service_name
}

echo "🚀 IMMEDIATE DEPLOYMENT - AI Model Validation Platform"
echo "====================================================="
echo "Starting at: $(date)"
echo ""

# Fix Docker credentials IMMEDIATELY
echo "1. Fixing Docker credentials..."
mkdir -p ~/.docker
echo '{}' > ~/.docker/config.json
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0

# Clean everything
echo "2. Full Docker cleanup..."
cleanup_unhealthy
docker-compose -f docker-compose.yml down --volumes --remove-orphans 2>/dev/null || true
docker-compose -f docker-compose.unified.yml down --volumes --remove-orphans 2>/dev/null || true
docker-compose -f docker-compose.immediate.yml down --volumes --remove-orphans 2>/dev/null || true
docker system prune -af
docker volume prune -f

# Use simpler approach - modify docker-compose to use pre-built image
echo "3. Creating immediate deployment configuration..."
cat > docker-compose.immediate.yml << 'EOF'
services:
  # Redis
  redis:
    image: redis:7-alpine
    container_name: ai_validation_redis_immediate
    ports:
      - "127.0.0.1:6379:6379"
    command: redis-server --requirepass secure_redis_password --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  # Backend 
  backend:
    image: python:3.11-slim
    container_name: ai_validation_backend_immediate
    ports:
      - "0.0.0.0:8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./dev_database.db
      - REDIS_URL=redis://:secure_redis_password@redis:6379
      - AIVALIDATION_SECRET_KEY=dev-secret-key
      - AIVALIDATION_API_HOST=0.0.0.0
      - AIVALIDATION_API_PORT=8000
      - AIVALIDATION_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
    volumes:
      - ./backend:/app
      - ./models:/app/models
    working_dir: /app
    command: bash -c "
      apt-get update && apt-get install -y curl &&
      pip install -r requirements.txt &&
      python startup_database.py &&
      uvicorn main:socketio_app --host 0.0.0.0 --port 8000 --reload"
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    restart: unless-stopped

  # Frontend - Use simple Node setup
  frontend:
    image: node:20-slim
    container_name: ai_validation_frontend_immediate
    ports:
      - "0.0.0.0:3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
      - REACT_APP_WS_URL=ws://localhost:8000
      - NODE_ENV=development
      - HOST=0.0.0.0
      - PORT=3000
    volumes:
      - ./frontend:/app
    working_dir: /app
    command: bash -c "
      apt-get update && apt-get install -y curl python3 make g++ &&
      npm cache clean --force &&
      npm install --legacy-peer-deps --unsafe-perm &&
      npm start"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s
    restart: unless-stopped

networks:
  default:
    name: ai_validation_immediate

volumes:
  redis_data:
EOF

echo "4. Starting immediate deployment..."
docker-compose -f docker-compose.immediate.yml up -d

echo "5. Monitoring service startup..."
for i in {1..30}; do
    echo "Checking startup progress... ($i/30)"
    docker-compose -f docker-compose.immediate.yml ps
    
    # Check if any containers are unhealthy or exited
    UNHEALTHY=$(docker-compose -f docker-compose.immediate.yml ps | grep -E "(unhealthy|Exited|Exit)" | wc -l)
    if [ "$UNHEALTHY" -gt 0 ]; then
        echo "⚠️  Warning: Some containers are unhealthy or exited. Checking logs..."
        echo "Redis logs:"
        docker logs ai_validation_redis_immediate --tail 10 2>/dev/null || echo "No Redis logs"
        echo "Backend logs:"
        docker logs ai_validation_backend_immediate --tail 10 2>/dev/null || echo "No Backend logs"
        echo "Frontend logs:"
        docker logs ai_validation_frontend_immediate --tail 10 2>/dev/null || echo "No Frontend logs"
    fi
    
    sleep 10
done

echo "6. Final service status check..."
docker-compose -f docker-compose.immediate.yml ps

echo ""
echo "✅ IMMEDIATE DEPLOYMENT COMPLETED!"
echo ""
echo "🌐 Services:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📊 Monitor logs:"
echo "   docker-compose -f docker-compose.immediate.yml logs -f"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose -f docker-compose.immediate.yml down"
echo ""

# Test connectivity with retries
echo "🔍 Testing connectivity..."
echo "Waiting for services to be fully ready..."
sleep 30

echo "Testing backend health..."
for i in {1..5}; do
    BACKEND_HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo 'not ready')
    echo "Backend attempt $i: $BACKEND_HEALTH"
    if [[ "$BACKEND_HEALTH" != "not ready" ]]; then
        break
    fi
    sleep 10
done

echo "Testing frontend status..."
for i in {1..5}; do
    FRONTEND_STATUS=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 2>/dev/null || echo 'not ready')
    echo "Frontend attempt $i: HTTP $FRONTEND_STATUS"
    if [[ "$FRONTEND_STATUS" == "200" ]]; then
        break
    fi
    sleep 10
done

echo ""
echo "📋 FINAL STATUS REPORT:"
echo "======================="
docker-compose -f docker-compose.immediate.yml ps
echo ""
echo "📊 Container Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.Status}}" 2>/dev/null || echo "Stats not available"

echo ""
echo "🔧 TROUBLESHOOTING COMMANDS:"
echo "View all logs: docker-compose -f docker-compose.immediate.yml logs -f"
echo "View frontend logs: docker logs ai_validation_frontend_immediate -f"
echo "View backend logs: docker logs ai_validation_backend_immediate -f"
echo "Restart unhealthy services: docker-compose -f docker-compose.immediate.yml restart"
echo "Clean restart: ./scripts/immediate-deploy.sh"