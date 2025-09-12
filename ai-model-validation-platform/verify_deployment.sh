#!/bin/bash

# Deployment Verification Script
# Tests that all services are accessible and functioning

set -e

echo "🔍 Starting deployment verification..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    print_test "$test_name"
    
    if eval "$test_command" > /dev/null 2>&1; then
        print_pass "$test_name"
        ((TESTS_PASSED++))
        return 0
    else
        print_fail "$test_name"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test 1: Check if containers are running
run_test "All containers are running" "docker-compose ps | grep -q 'Up'"

# Test 2: Backend health check
run_test "Backend health check" "curl -f http://localhost:8000/health"

# Test 3: Frontend accessibility
run_test "Frontend accessibility" "curl -f http://localhost:3000"

# Test 4: Backend API documentation
run_test "Backend API docs" "curl -f http://localhost:8000/docs"

# Test 5: Database connection through backend
run_test "Database connectivity" "curl -f -X GET http://localhost:8000/api/projects"

# Test 6: WebSocket connection test
run_test "WebSocket endpoint" "curl -f http://localhost:8000/socket.io/"

# Test 7: CORS headers test
run_test "CORS headers" "curl -H 'Origin: http://localhost:3000' -I http://localhost:8000/api/projects | grep -q 'Access-Control'"

# Test 8: Static file serving
run_test "Static files" "curl -f http://localhost:3000/static/js/ || curl -f http://localhost:3000/manifest.json"

# Test 9: Container resource usage
run_test "Container resource usage" "docker stats --no-stream --format 'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}' | grep -v '0.00%'"

# Test 10: Log output verification
print_test "Checking for critical errors in logs"
if docker-compose logs backend 2>&1 | grep -i "error\|exception\|failed" | grep -v "ModuleNotFoundError\|ImportError\|auto-installer"; then
    print_fail "Critical errors found in backend logs"
    ((TESTS_FAILED++))
else
    print_pass "No critical errors in backend logs"
    ((TESTS_PASSED++))
fi

# Summary
echo ""
echo "=============================================="
echo "🧪 Test Results:"
echo "   ✅ Passed: $TESTS_PASSED"
echo "   ❌ Failed: $TESTS_FAILED"
echo "=============================================="

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! Deployment is working correctly.${NC}"
    
    # Show service status
    echo ""
    echo "📋 Service Status:"
    docker-compose ps
    
    # Show service URLs
    echo ""
    echo "🌐 Service URLs:"
    echo "   Frontend:        http://localhost:3000"
    echo "   Backend API:     http://localhost:8000"
    echo "   API Docs:        http://localhost:8000/docs"
    echo "   Health Check:    http://localhost:8000/health"
    
    exit 0
else
    echo -e "${RED}💥 $TESTS_FAILED test(s) failed! Please check the deployment.${NC}"
    
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   📋 View all logs: docker-compose logs"
    echo "   🔍 Check specific service: docker-compose logs [service_name]"
    echo "   🔄 Restart services: docker-compose restart"
    echo "   🛑 Stop and rebuild: docker-compose down && docker-compose up -d --build"
    
    exit 1
fi