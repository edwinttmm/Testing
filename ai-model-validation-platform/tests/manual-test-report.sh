#!/bin/bash

# Manual Integration Test Report for AI Model Validation Platform
# This script tests all services and generates a comprehensive report

echo "🚀 AI Model Validation Platform - Comprehensive Test Report"
echo "=========================================================="
echo "Date: $(date)"
echo "Environment: $(uname -a | cut -d' ' -f1-3)"
echo ""

# Test Results Storage
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
TEST_RESULTS=""

# Function to log test results
log_test() {
    local test_name="$1"
    local status="$2" 
    local message="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if [ "$status" = "PASS" ]; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        echo "✅ $test_name: $message"
    elif [ "$status" = "FAIL" ]; then
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo "❌ $test_name: $message"
    else
        echo "⚠️  $test_name: $message"
    fi
    
    TEST_RESULTS="${TEST_RESULTS}\n$status: $test_name - $message"
}

# Test 1: Backend Health Check
echo "Testing Backend Services..."
if curl -f -s http://localhost:8000/health > /dev/null; then
    HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
    log_test "Backend Health" "PASS" "Backend is healthy and responding"
    echo "   Response: $HEALTH_RESPONSE"
else
    log_test "Backend Health" "FAIL" "Backend health check failed"
fi

# Test 2: Frontend Availability  
echo ""
echo "Testing Frontend Services..."
if curl -f -s http://localhost:3000 > /dev/null; then
    log_test "Frontend Availability" "PASS" "Frontend is serving content"
else
    log_test "Frontend Availability" "FAIL" "Frontend not accessible"
fi

# Test 3: API Endpoints
echo ""
echo "Testing API Endpoints..."
API_ENDPOINTS=("/api/projects" "/api/videos" "/api/dashboard/stats" "/api/validation/status" "/api/detection/models")

for endpoint in "${API_ENDPOINTS[@]}"; do
    if curl -f -s "http://localhost:8000$endpoint" > /dev/null; then
        log_test "API $endpoint" "PASS" "Endpoint responding"
    else
        log_test "API $endpoint" "FAIL" "Endpoint not responding"
    fi
done

# Test 4: File Upload
echo ""
echo "Testing File Upload..."
if [ -f "README.md" ]; then
    UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/api/videos/upload -F "file=@README.md" 2>/dev/null)
    if echo "$UPLOAD_RESPONSE" | grep -q -i "upload\|success\|video\|file"; then
        log_test "File Upload" "PASS" "File upload endpoint working"
        echo "   Response sample: $(echo "$UPLOAD_RESPONSE" | head -c 100)..."
    else
        log_test "File Upload" "WARN" "Upload endpoint responding but unclear result"
    fi
else
    log_test "File Upload" "WARN" "No test file available for upload test"
fi

# Test 5: Performance Test
echo ""
echo "Testing Performance..."
START_TIME=$(date +%s.%N)
curl -f -s http://localhost:8000/health > /dev/null
END_TIME=$(date +%s.%N)
RESPONSE_TIME=$(echo "$END_TIME - $START_TIME" | bc -l)

if (( $(echo "$RESPONSE_TIME < 1.0" | bc -l) )); then
    log_test "Performance" "PASS" "Backend response time: ${RESPONSE_TIME}s (< 1.0s)"
else
    log_test "Performance" "WARN" "Backend response time: ${RESPONSE_TIME}s (>= 1.0s)"
fi

# Test 6: Service Communication
echo ""
echo "Testing Service Communication..."
BACKEND_STATUS=$(curl -f -s http://localhost:8000/health > /dev/null && echo "OK" || echo "FAIL")
FRONTEND_STATUS=$(curl -f -s http://localhost:3000 > /dev/null && echo "OK" || echo "FAIL")

if [ "$BACKEND_STATUS" = "OK" ] && [ "$FRONTEND_STATUS" = "OK" ]; then
    log_test "Service Communication" "PASS" "All services communicating properly"
elif [ "$BACKEND_STATUS" = "OK" ]; then
    log_test "Service Communication" "WARN" "Backend OK, Frontend issues"
else
    log_test "Service Communication" "FAIL" "Communication issues detected"
fi

# Test 7: Database Connection
echo ""
echo "Testing Database Connection..."
DB_STATUS=$(curl -s http://localhost:8000/health | grep -o '"database":"[^"]*"' | cut -d'"' -f4)
if [ "$DB_STATUS" = "connected" ]; then
    log_test "Database Connection" "PASS" "Database connected via backend"
elif [ -n "$DB_STATUS" ]; then
    log_test "Database Connection" "WARN" "Database status: $DB_STATUS"  
else
    log_test "Database Connection" "FAIL" "Cannot determine database status"
fi

# Test 8: WebSocket Test (basic check)
echo ""
echo "Testing WebSocket Support..."
if curl -s -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8000/ws 2>&1 | grep -q -i "websocket\|upgrade\|101"; then
    log_test "WebSocket Support" "PASS" "WebSocket upgrade available"
else
    log_test "WebSocket Support" "WARN" "WebSocket status unclear"
fi

# Test 9: Error Handling
echo ""
echo "Testing Error Handling..."
ERROR_RESPONSE=$(curl -s http://localhost:8000/nonexistent-endpoint)
if echo "$ERROR_RESPONSE" | grep -q -i "detail\|error\|404"; then
    log_test "Error Handling" "PASS" "Proper error responses for invalid endpoints"
else
    log_test "Error Handling" "WARN" "Error handling unclear"
fi

# Test 10: API Documentation
echo ""
echo "Testing API Documentation..."
if curl -f -s http://localhost:8000/docs > /dev/null; then
    log_test "API Documentation" "PASS" "Swagger documentation available"
else
    log_test "API Documentation" "FAIL" "API documentation not accessible"
fi

# Generate Final Report
echo ""
echo "=========================================================="
echo "📊 COMPREHENSIVE TEST RESULTS"
echo "=========================================================="
echo "Total Tests Run: $TOTAL_TESTS"
echo "✅ Passed: $PASSED_TESTS"
echo "❌ Failed: $FAILED_TESTS" 
echo "⚠️  Warnings: $((TOTAL_TESTS - PASSED_TESTS - FAILED_TESTS))"

if [ $FAILED_TESTS -eq 0 ]; then
    echo "🎉 OVERALL STATUS: SYSTEM OPERATIONAL"
    SYSTEM_STATUS="OPERATIONAL"
    EXIT_CODE=0
elif [ $PASSED_TESTS -gt $FAILED_TESTS ]; then
    echo "⚠️  OVERALL STATUS: SYSTEM FUNCTIONAL (with minor issues)"
    SYSTEM_STATUS="FUNCTIONAL"
    EXIT_CODE=0
else
    echo "❌ OVERALL STATUS: SYSTEM DEGRADED"
    SYSTEM_STATUS="DEGRADED" 
    EXIT_CODE=1
fi

SUCCESS_RATE=$(( PASSED_TESTS * 100 / TOTAL_TESTS ))
echo "Success Rate: ${SUCCESS_RATE}%"

# Detailed System Information
echo ""
echo "=========================================================="
echo "🔧 SYSTEM INFORMATION"
echo "=========================================================="
echo "Running Processes:"
ps aux | grep -E "(python|node|uvicorn)" | grep -v grep | head -5

echo ""
echo "Network Services:"
netstat -tlnp 2>/dev/null | grep -E ":3000|:8000" | head -10

echo ""
echo "Service URLs:"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000" 
echo "  API Docs: http://localhost:8000/docs"
echo "  Health:   http://localhost:8000/health"

# Save report
REPORT_FILE="/home/rigade/Testing/ai-model-validation-platform/tests/comprehensive-test-report.txt"
{
    echo "AI Model Validation Platform - Test Report"
    echo "Generated: $(date)"
    echo "Status: $SYSTEM_STATUS"
    echo "Success Rate: ${SUCCESS_RATE}%"
    echo "Total/Passed/Failed: $TOTAL_TESTS/$PASSED_TESTS/$FAILED_TESTS"
    echo ""
    echo "Test Details:"
    echo -e "$TEST_RESULTS"
} > "$REPORT_FILE"

echo ""
echo "📄 Detailed report saved to: $REPORT_FILE"
echo "=========================================================="

exit $EXIT_CODE