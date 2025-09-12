#!/bin/bash

# LabJack Integration Verification Script
# This script verifies that all LabJack integration fixes are working correctly

echo "🧪 LabJack Integration Verification Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_TOTAL=0
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to run test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_pattern="$3"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -e "\n${BLUE}Testing:${NC} $test_name"
    
    # Run the test command
    result=$(eval "$test_command" 2>&1)
    exit_code=$?
    
    # Check if test passed
    if [ $exit_code -eq 0 ] && [[ $result =~ $expected_pattern ]]; then
        echo -e "${GREEN}✅ PASS${NC}: $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}: $test_name"
        echo -e "${RED}   Command:${NC} $test_command"
        echo -e "${RED}   Expected:${NC} $expected_pattern"
        echo -e "${RED}   Got:${NC} $result"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Check if backend server is running
echo -e "\n${YELLOW}1. Checking Backend Server${NC}"
run_test "Backend Health Check" \
    "curl -s http://localhost:8000/health" \
    "\"status\".*\"healthy\""

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Backend server not running or not healthy${NC}"
    echo -e "${YELLOW}💡 Try: cd backend && source .venv/bin/activate && uvicorn main:app --reload${NC}"
    exit 1
fi

# Test LabJack API endpoints
echo -e "\n${YELLOW}2. Testing LabJack API Endpoints${NC}"

run_test "LabJack Status Endpoint" \
    "curl -s http://localhost:8000/api/signal-validation/labjack/status" \
    "\"connected\""

run_test "LabJack Initialization Endpoint" \
    "curl -s -X POST http://localhost:8000/api/signal-validation/labjack/initialize -H 'Content-Type: application/json' -d '{\"voltage_threshold\":{\"lower\":4.0,\"upper\":5.5}}'" \
    "\"status\".*\"connected\""

# Test Signal Validation Endpoints  
echo -e "\n${YELLOW}3. Testing Signal Validation Endpoints${NC}"

run_test "Test Connection Endpoint" \
    "curl -s http://localhost:8000/api/signal-validation/test-connection" \
    "\"status\""

run_test "Start Monitoring Endpoint" \
    "curl -s -X POST http://localhost:8000/api/signal-validation/monitoring/start/test-session" \
    "\"status\""

run_test "Stop Monitoring Endpoint" \
    "curl -s -X POST http://localhost:8000/api/signal-validation/monitoring/stop" \
    "\"status\""

# Check frontend files exist and are properly configured
echo -e "\n${YELLOW}4. Checking Frontend Files${NC}"

run_test "Frontend API Service File" \
    "test -f frontend/src/services/api.ts && grep -q 'checkLabJackStatus' frontend/src/services/api.ts" \
    ""

run_test "Enhanced API Service File" \
    "test -f frontend/src/services/enhancedApiService.ts && grep -q 'initializeLabJack' frontend/src/services/enhancedApiService.ts" \
    ""

run_test "Enhanced Test Execution File" \
    "test -f frontend/src/pages/EnhancedTestExecution.tsx && grep -q 'labJackStatus' frontend/src/pages/EnhancedTestExecution.tsx" \
    ""

run_test "Integration Test File" \
    "test -f frontend/src/tests/labjack-integration-test.ts" \
    ""

# Check WebSocket server (if running)
echo -e "\n${YELLOW}5. Testing WebSocket Connection${NC}"

# Try to connect to WebSocket server
run_test "WebSocket Server Availability" \
    "timeout 5 bash -c '</dev/tcp/localhost/8001' 2>/dev/null" \
    ""

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ WebSocket server is running on port 8001${NC}"
else
    echo -e "${YELLOW}⚠️  WebSocket server not running on port 8001 (may be expected)${NC}"
fi

# Frontend server check
echo -e "\n${YELLOW}6. Checking Frontend Server${NC}"

run_test "Frontend Server Running" \
    "curl -s -I http://localhost:3000" \
    "HTTP.*200"

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Frontend server not running${NC}"
    echo -e "${YELLOW}💡 Try: cd frontend && npm start${NC}"
else
    echo -e "${GREEN}✅ Frontend server is running on port 3000${NC}"
fi

# Test specific frontend components
echo -e "\n${YELLOW}7. Testing Frontend Integration${NC}"

if curl -s http://localhost:3000 > /dev/null; then
    echo -e "${GREEN}✅ Frontend is accessible${NC}"
    echo -e "${BLUE}🔗 Access Enhanced Test Execution at:${NC} http://localhost:3000/enhanced-test-execution"
else
    echo -e "${RED}❌ Frontend not accessible${NC}"
fi

# Summary
echo -e "\n${BLUE}=========================================="
echo -e "📊 Test Results Summary"
echo -e "==========================================${NC}"
echo -e "Total Tests: $TESTS_TOTAL"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All tests passed! LabJack integration is working correctly.${NC}"
    echo -e "\n${BLUE}Next Steps:${NC}"
    echo -e "1. Open browser to http://localhost:3000/enhanced-test-execution"
    echo -e "2. Find the 'LabJack Camera Detection System' section"
    echo -e "3. Click 'Initialize LabJack' button"
    echo -e "4. Verify status shows 'LabJack Connected'"
    echo -e "5. Check voltage readings appear"
    
    echo -e "\n${BLUE}For manual testing:${NC}"
    echo -e "- Initialize LabJack should work without 500 errors"
    echo -e "- Connection status should update properly" 
    echo -e "- Mock mode should provide simulated voltage readings"
    echo -e "- WebSocket connection should work for real-time monitoring"
else
    echo -e "\n${RED}⚠️  $TESTS_FAILED test(s) failed. Check the output above for details.${NC}"
    
    echo -e "\n${BLUE}Troubleshooting:${NC}"
    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "1. Ensure backend server is running: ${YELLOW}cd backend && source .venv/bin/activate && uvicorn main:app --reload${NC}"
        echo -e "2. Ensure frontend server is running: ${YELLOW}cd frontend && npm start${NC}"
        echo -e "3. Check CORS configuration allows localhost:3000"
        echo -e "4. Verify all dependencies are installed"
        echo -e "5. Check firewall/network settings"
    fi
fi

echo -e "\n${BLUE}Configuration Information:${NC}"
echo -e "Backend API: http://localhost:8000"
echo -e "Frontend App: http://localhost:3000"
echo -e "WebSocket: ws://localhost:8001"
echo -e "LabJack Mode: Mock (no hardware required)"

exit $TESTS_FAILED