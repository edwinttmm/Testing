#!/bin/bash

# Quick Deployment Script for AI Model Validation Platform
# This script creates a minimal working deployment

set -e

echo "🚀 Quick Deploy - AI Model Validation Platform"
echo "============================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Stop any existing containers
print_status "Cleaning up existing containers..."
docker stop ai_validation_backend ai_validation_frontend ai_validation_postgres ai_validation_redis 2>/dev/null || true
docker rm ai_validation_backend ai_validation_frontend ai_validation_postgres ai_validation_redis 2>/dev/null || true

# Create network if it doesn't exist
print_status "Creating network..."
docker network create ai_validation_net 2>/dev/null || true

# Start PostgreSQL
print_status "Starting PostgreSQL..."
docker run -d --name ai_validation_postgres \
  --network ai_validation_net \
  -p 5432:5432 \
  -e POSTGRES_DB=vru_validation_prod \
  -e POSTGRES_USER=vru_prod_user \
  -e POSTGRES_PASSWORD=VRU_Prod_2024_SecureDB_Password_9876 \
  postgres:15

# Start Redis
print_status "Starting Redis..."
docker run -d --name ai_validation_redis \
  --network ai_validation_net \
  -p 6379:6379 \
  redis:7-alpine redis-server --appendonly yes

# Wait for databases
print_status "Waiting for databases to be ready..."
sleep 15

# Build and start backend
print_status "Building and starting backend..."
docker build -t ai_validation_backend ./backend
docker run -d --name ai_validation_backend \
  --network ai_validation_net \
  -p 8000:8000 \
  ai_validation_backend

# Wait for backend to start
print_status "Waiting for backend to start..."
sleep 10

# Test backend
for i in {1..10}; do
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        print_success "Backend is healthy!"
        break
    else
        print_status "Waiting for backend... (attempt $i/10)"
        sleep 3
    fi
done

# Create minimal frontend
print_status "Creating minimal frontend..."
mkdir -p frontend_minimal
cat > frontend_minimal/index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>AI Model Validation Platform</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .status { padding: 20px; margin: 10px 0; border-radius: 5px; }
        .healthy { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; margin: 5px; cursor: pointer; border-radius: 3px; }
        button:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AI Model Validation Platform</h1>
        <h2>Deployment Status</h2>
        <div id="status" class="status">Checking status...</div>
        <button onclick="checkHealth()">Check Backend Health</button>
        <button onclick="testAPI()">Test API</button>
        
        <h2>API Endpoints</h2>
        <ul>
            <li><a href="http://localhost:8000/health">Health Check</a></li>
            <li><a href="http://localhost:8000/docs">API Documentation</a></li>
            <li><a href="http://localhost:8000/api/projects">Projects API</a></li>
        </ul>
        
        <h2>Services</h2>
        <ul>
            <li>PostgreSQL Database: localhost:5432</li>
            <li>Redis Cache: localhost:6379</li>
            <li>Backend API: localhost:8000</li>
            <li>Frontend: localhost:3000</li>
        </ul>
    </div>
    
    <script>
        async function checkHealth() {
            const status = document.getElementById('status');
            try {
                const response = await fetch('http://localhost:8000/health');
                const data = await response.json();
                status.className = 'status healthy';
                status.innerHTML = '✅ Backend is healthy: ' + JSON.stringify(data, null, 2);
            } catch (error) {
                status.className = 'status error';
                status.innerHTML = '❌ Backend error: ' + error.message;
            }
        }
        
        async function testAPI() {
            const status = document.getElementById('status');
            try {
                const response = await fetch('http://localhost:8000/api/projects');
                const data = await response.json();
                status.className = 'status healthy';
                status.innerHTML = '✅ API test successful: ' + JSON.stringify(data, null, 2);
            } catch (error) {
                status.className = 'status error';
                status.innerHTML = '❌ API test failed: ' + error.message;
            }
        }
        
        // Auto-check status on page load
        checkHealth();
    </script>
</body>
</html>
EOF

# Start simple HTTP server for frontend
print_status "Starting frontend server..."
docker run -d --name ai_validation_frontend \
  --network ai_validation_net \
  -p 3000:8080 \
  -v "$(pwd)/frontend_minimal:/usr/share/nginx/html:ro" \
  nginx:alpine

# Final status check
print_status "Running final verification..."
sleep 5

echo ""
echo "============================================="
print_success "🎉 Deployment completed!"
echo ""
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📊 API Docs: http://localhost:8000/docs"
echo "🏥 Health Check: http://localhost:8000/health"
echo ""
echo "To stop deployment:"
echo "docker stop ai_validation_backend ai_validation_frontend ai_validation_postgres ai_validation_redis"
echo "============================================="

# Test services
if curl -f http://localhost:8000/health >/dev/null 2>&1; then
    print_success "✅ Backend is accessible"
else
    print_error "❌ Backend is not accessible"
fi

if curl -f http://localhost:3000 >/dev/null 2>&1; then
    print_success "✅ Frontend is accessible"
else
    print_error "❌ Frontend is not accessible"
fi