#!/bin/bash
# HIL Platform Deployment Script
# Version: 1.0
# Date: 2025-11-04

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}HIL Platform Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if we're in the correct directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    print_error "Must be run from ai-model-validation-platform root directory"
    exit 1
fi

print_status "Working directory: $(pwd)"
echo ""

# Step 1: Backup database
echo -e "${YELLOW}Step 1: Database Backup${NC}"
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
cd backend

if [ -f "dev_database.db" ]; then
    cp dev_database.db "${BACKUP_FILE}.db"
    print_status "SQLite database backed up to ${BACKUP_FILE}.db"
elif command -v pg_dump &> /dev/null; then
    print_warning "PostgreSQL detected, attempting backup..."
    pg_dump -h localhost -U postgres -d hil_validation > "$BACKUP_FILE" 2>/dev/null || print_warning "PostgreSQL backup failed (may not be configured)"
else
    print_warning "No database backup created"
fi
cd ..
echo ""

# Step 2: Git status check
echo -e "${YELLOW}Step 2: Git Status Check${NC}"
git status --short | head -10
MODIFIED_COUNT=$(git status --short | wc -l)
print_status "Total modified files: $MODIFIED_COUNT"
echo ""

# Step 3: Backend deployment
echo -e "${YELLOW}Step 3: Backend Deployment${NC}"

# Stop existing backend
print_status "Stopping existing backend processes..."
pkill -f "uvicorn main:app" 2>/dev/null || print_warning "No existing backend process found"
sleep 2

# Start backend
cd backend
print_status "Starting backend server..."
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!
print_status "Backend started with PID: $BACKEND_PID"

# Wait for backend to start
print_status "Waiting for backend to initialize..."
sleep 5

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    print_status "Backend health check: OK"
else
    print_error "Backend health check failed!"
    print_warning "Check backend.log for errors:"
    tail -20 backend.log
    cd ..
    exit 1
fi
cd ..
echo ""

# Step 4: Frontend deployment
echo -e "${YELLOW}Step 4: Frontend Deployment${NC}"
cd frontend

# Clear cache
print_status "Clearing build cache..."
rm -rf build/ node_modules/.cache/ 2>/dev/null || true

# Install dependencies (if needed)
if [ ! -d "node_modules" ]; then
    print_status "Installing dependencies..."
    npm install
fi

# Build production bundle
print_status "Building production bundle..."
npm run build

if [ -d "build" ]; then
    BUILD_SIZE=$(du -sh build | cut -f1)
    print_status "Production build created (size: $BUILD_SIZE)"
else
    print_error "Build failed!"
    cd ..
    exit 1
fi

# Start development server (change this for production deployment)
print_status "Starting frontend server..."
nohup npx serve -s build -l 3000 > frontend.log 2>&1 &
FRONTEND_PID=$!
print_status "Frontend started with PID: $FRONTEND_PID"

sleep 3

# Check if frontend is running
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    print_status "Frontend health check: OK"
else
    print_warning "Frontend may not be accessible yet (give it a moment)"
fi
cd ..
echo ""

# Step 5: Smoke tests
echo -e "${YELLOW}Step 5: Smoke Tests${NC}"

# Test backend API
if curl -s http://localhost:8000/api/test-sessions | grep -q '\['; then
    print_status "Backend API: Responding"
else
    print_warning "Backend API: Not responding properly"
fi

# Test frontend
if curl -s http://localhost:3000 | grep -q 'html'; then
    print_status "Frontend: Serving content"
else
    print_warning "Frontend: Not serving content yet"
fi
echo ""

# Step 6: Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Services:"
echo "  Backend:  http://localhost:8000 (PID: $BACKEND_PID)"
echo "  Frontend: http://localhost:3000 (PID: $FRONTEND_PID)"
echo ""
echo "Logs:"
echo "  Backend:  tail -f backend/backend.log"
echo "  Frontend: tail -f frontend/frontend.log"
echo ""
echo "Next Steps:"
echo "  1. Open http://localhost:3000 in browser"
echo "  2. Run smoke tests: cd backend/tests && pytest -v"
echo "  3. Monitor logs for errors"
echo ""

# Optional: Run quick test
read -p "Run integration tests? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd backend/tests
    print_status "Running integration tests..."
    pytest test_detection_api_filtering.py -v || print_warning "Some tests failed"
    cd ../..
fi

echo ""
print_status "Deployment script completed!"
echo ""
