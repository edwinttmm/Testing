#!/bin/bash

# Configuration Validation Script
# Validates that all configuration files are properly set for external access

set -e

echo "=== AI Model Validation Platform - Configuration Validation ==="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

validation_passed=true

# Function to check configuration
check_config() {
    local file=$1
    local pattern=$2
    local description=$3
    
    echo -n "Checking $description in $file ... "
    
    if [ -f "$file" ]; then
        if grep -q "$pattern" "$file"; then
            echo -e "${GREEN}✓ CONFIGURED${NC}"
        else
            echo -e "${RED}✗ MISSING${NC}"
            validation_passed=false
        fi
    else
        echo -e "${RED}✗ FILE NOT FOUND${NC}"
        validation_passed=false
    fi
}

echo "=== Docker Compose Configuration ==="
check_config "docker-compose.yml" "0.0.0.0:3000:3000" "Frontend external port binding"
check_config "docker-compose.yml" "0.0.0.0:8000:8000" "Backend external port binding"
check_config "docker-compose.yml" "127.0.0.1:5432:5432" "PostgreSQL internal-only binding"
check_config "docker-compose.yml" "127.0.0.1:6379:6379" "Redis internal-only binding"
check_config "docker-compose.yml" "155.138.239.131:8000" "Frontend API URL configuration"
check_config "docker-compose.yml" "AIVALIDATION_API_HOST=0.0.0.0" "Backend host configuration"

echo ""
echo "=== Environment Configuration ==="
check_config ".env" "BACKEND_HOST=155.138.239.131" "Root .env backend host"
check_config ".env" "FRONTEND_HOST=155.138.239.131" "Root .env frontend host"
check_config "backend/.env" "AIVALIDATION_API_HOST=0.0.0.0" "Backend API host"
check_config "backend/.env" "155.138.239.131:3000" "Backend CORS origins"
check_config "frontend/.env" "155.138.239.131:8000" "Frontend API URL"
check_config "frontend/.env" "HOST=0.0.0.0" "Frontend host binding"

echo ""
echo "=== Security Configuration ==="
check_config "docker-compose.yml" "127.0.0.1:5432" "PostgreSQL secured (internal only)"
check_config "docker-compose.yml" "127.0.0.1:6379" "Redis secured (internal only)"

echo ""
echo "=== File Permissions ==="
if [ -x "scripts/test-external-access.sh" ]; then
    echo -e "Test script executable: ${GREEN}✓ YES${NC}"
else
    echo -e "Test script executable: ${RED}✗ NO${NC}"
    validation_passed=false
fi

echo ""
if [ "$validation_passed" = true ]; then
    echo -e "${GREEN}=== VALIDATION PASSED ===${NC}"
    echo "All configuration files are properly set for external access."
    echo ""
    echo "Next steps:"
    echo "1. docker-compose down"
    echo "2. docker-compose build --no-cache"
    echo "3. docker-compose up -d"
    echo "4. ./scripts/test-external-access.sh"
    echo ""
    echo "Access URLs will be:"
    echo "  Frontend: http://155.138.239.131:3000"
    echo "  Backend: http://155.138.239.131:8000"
else
    echo -e "${RED}=== VALIDATION FAILED ===${NC}"
    echo "Some configuration issues were found. Please review the output above."
fi