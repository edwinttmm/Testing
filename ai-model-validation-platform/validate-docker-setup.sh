#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Docker Setup Validation Script ===${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Error: docker-compose.yml not found. Please run from ai-model-validation-platform directory${NC}"
    exit 1
fi

echo -e "${BLUE}1. Checking required files...${NC}"

# Array of required files
declare -a required_files=(
    "backend/Dockerfile"
    "backend/scripts/wait-for-services.sh"
    "backend/requirements-minimal.txt"
    "backend/requirements-docker-minimal.txt"
    "backend/auto_install_ml.py"
    "backend/main.py"
    "docker-compose.yml"
)

all_files_present=true
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ Found: $file${NC}"
    else
        echo -e "${RED}❌ Missing: $file${NC}"
        all_files_present=false
    fi
done

if [ "$all_files_present" = false ]; then
    echo -e "${RED}Some required files are missing!${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}2. Checking file permissions...${NC}"

# Check if wait-for-services.sh is executable
if [ -x "backend/scripts/wait-for-services.sh" ]; then
    echo -e "${GREEN}✅ wait-for-services.sh is executable${NC}"
else
    echo -e "${YELLOW}⚠️  wait-for-services.sh is not executable. Fixing...${NC}"
    chmod +x backend/scripts/wait-for-services.sh
    echo -e "${GREEN}✅ Fixed permissions${NC}"
fi

echo ""
echo -e "${BLUE}3. Checking Docker installation...${NC}"

if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker is installed${NC}"
    docker --version
else
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi

if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✅ Docker Compose is installed${NC}"
    docker-compose --version
else
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}4. Testing Docker build (backend only)...${NC}"

echo -e "${YELLOW}Building backend service...${NC}"
if docker-compose build backend; then
    echo -e "${GREEN}✅ Backend build successful!${NC}"
else
    echo -e "${RED}❌ Backend build failed. Check the error messages above.${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}5. Starting all services...${NC}"

echo -e "${YELLOW}Starting services with docker-compose up -d...${NC}"
if docker-compose up -d; then
    echo -e "${GREEN}✅ Services started successfully!${NC}"
else
    echo -e "${RED}❌ Failed to start services${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}6. Waiting for services to be ready...${NC}"

# Wait a bit for services to initialize
sleep 10

echo -e "${YELLOW}Checking service status...${NC}"
docker-compose ps

echo ""
echo -e "${BLUE}7. Testing backend health endpoint...${NC}"

# Try to hit the health endpoint
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -f http://localhost:8000/health 2>/dev/null; then
        echo ""
        echo -e "${GREEN}✅ Backend is responding to health checks!${NC}"
        break
    else
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    fi
done

if [ $attempt -eq $max_attempts ]; then
    echo ""
    echo -e "${RED}❌ Backend health check failed after $max_attempts attempts${NC}"
    echo -e "${YELLOW}Checking logs...${NC}"
    docker-compose logs --tail=50 backend
    exit 1
fi

echo ""
echo -e "${BLUE}8. Final service status:${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}🎉 All validation checks passed! Your Docker setup is working correctly.${NC}"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  - View logs: docker-compose logs -f backend"
echo "  - Stop services: docker-compose down"
echo "  - Restart services: docker-compose restart"
echo "  - Rebuild and restart: docker-compose down && docker-compose up --build -d"

echo ""
echo -e "${YELLOW}External access:${NC}"
echo "  - Backend API: http://$(hostname -I | awk '{print $1}'):8000"
echo "  - Frontend: http://$(hostname -I | awk '{print $1}'):3000"