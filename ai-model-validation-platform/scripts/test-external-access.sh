#!/bin/bash

# Test External Access Script for AI Model Validation Platform
# This script tests accessibility on both localhost and external IP

set -e

echo "=== AI Model Validation Platform - External Access Test ==="
echo "Testing connectivity to both localhost and external IP (155.138.239.131)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test function
test_endpoint() {
    local url=$1
    local service=$2
    local expected_status=${3:-200}
    
    echo -n "Testing $service at $url ... "
    
    if command -v curl >/dev/null 2>&1; then
        response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 "$url" 2>/dev/null || echo "000")
        
        if [ "$response" -eq "$expected_status" ] || [ "$response" -eq "200" ] || [ "$response" -eq "404" ] || [ "$response" -eq "302" ]; then
            echo -e "${GREEN}✓ ACCESSIBLE${NC} (HTTP $response)"
        else
            echo -e "${RED}✗ FAILED${NC} (HTTP $response or connection failed)"
        fi
    else
        echo -e "${YELLOW}⚠ SKIPPED${NC} (curl not available)"
    fi
}

# Wait for services
echo "Waiting for Docker containers to be ready..."
sleep 5

echo ""
echo "=== Testing Frontend (Port 3000) ==="
test_endpoint "http://127.0.0.1:3000" "Frontend (localhost)"
test_endpoint "http://155.138.239.131:3000" "Frontend (external IP)"

echo ""
echo "=== Testing Backend (Port 8000) ==="
test_endpoint "http://127.0.0.1:8000/health" "Backend Health (localhost)"
test_endpoint "http://155.138.239.131:8000/health" "Backend Health (external IP)"
test_endpoint "http://127.0.0.1:8000/docs" "Backend API Docs (localhost)"
test_endpoint "http://155.138.239.131:8000/docs" "Backend API Docs (external IP)"

echo ""
echo "=== Testing Database Access (Should be INTERNAL ONLY) ==="
if nc -z 127.0.0.1 5432 2>/dev/null; then
    echo -e "PostgreSQL (localhost): ${YELLOW}⚠ ACCESSIBLE${NC} (Expected - internal access)"
else
    echo -e "PostgreSQL (localhost): ${RED}✗ NOT ACCESSIBLE${NC}"
fi

if timeout 3 bash -c '</dev/tcp/155.138.239.131/5432' 2>/dev/null; then
    echo -e "PostgreSQL (external IP): ${RED}✗ EXTERNALLY ACCESSIBLE${NC} (SECURITY RISK!)"
else
    echo -e "PostgreSQL (external IP): ${GREEN}✓ NOT EXTERNALLY ACCESSIBLE${NC} (Secure)"
fi

echo ""
echo "=== Testing Redis Access (Should be INTERNAL ONLY) ==="
if nc -z 127.0.0.1 6379 2>/dev/null; then
    echo -e "Redis (localhost): ${YELLOW}⚠ ACCESSIBLE${NC} (Expected - internal access)"
else
    echo -e "Redis (localhost): ${RED}✗ NOT ACCESSIBLE${NC}"
fi

if timeout 3 bash -c '</dev/tcp/155.138.239.131/6379' 2>/dev/null; then
    echo -e "Redis (external IP): ${RED}✗ EXTERNALLY ACCESSIBLE${NC} (SECURITY RISK!)"
else
    echo -e "Redis (external IP): ${GREEN}✓ NOT EXTERNALLY ACCESSIBLE${NC} (Secure)"
fi

echo ""
echo "=== Docker Container Status ==="
docker-compose ps

echo ""
echo "=== Network Configuration ==="
docker network inspect vru_validation_network --format '{{json .IPAM.Config}}'

echo ""
echo "=== Port Binding Check ==="
echo "Checking which ports are bound to external interfaces..."
netstat -tulpn | grep -E ':(3000|8000|5432|6379)' || echo "No matching ports found"

echo ""
echo -e "${GREEN}=== Test Complete ===${NC}"
echo ""
echo "Expected Results:"
echo "  ✓ Frontend and Backend should be accessible on both localhost and external IP"
echo "  ✓ PostgreSQL and Redis should NOT be accessible externally (security)"
echo ""
echo "Access URLs:"
echo "  Frontend: http://155.138.239.131:3000"
echo "  Backend API: http://155.138.239.131:8000"
echo "  API Documentation: http://155.138.239.131:8000/docs"