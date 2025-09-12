#!/bin/bash

# Workflow Test Execution Script
# ===============================
# This script runs the comprehensive workflow validation tests
# addressing user concerns about sequential video processing and automation

echo "🚀 AI Model Validation Platform - Workflow Test Suite"
echo "======================================================"
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Activating virtual environment..."
    source ../venv/bin/activate || source ../.venv/bin/activate
fi

# Check if backend server is running
echo "🔍 Checking backend server status..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend server is running on port 8000"
elif curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Backend server is running on port 8001"
    BASE_URL="http://localhost:8001"
else
    echo "❌ Backend server is not running!"
    echo "   Please start the backend server first:"
    echo "   cd ../backend && python main.py"
    exit 1
fi

# Set base URL (default to 8000, fallback to 8001)
BASE_URL=${BASE_URL:-"http://localhost:8000"}

echo ""
echo "🎯 Running Workflow Tests..."
echo "----------------------------"

# Test 1: Sequential Video Processing
echo ""
echo "🎥 Test 1: Sequential Video Processing (Phantom Session Prevention)"
echo "   User Concern: 'videos are coming separately it should automatically play one after another'"
python workflow_test_runner.py --test-type=sequential --base-url="$BASE_URL"
SEQUENTIAL_RESULT=$?

# Test 2: Frontend Integration
echo ""
echo "🖥️  Test 2: Frontend Integration (Enhanced Test Execution)"
echo "   User Concern: Enhanced Test Execution page and exportTestResults function"
python workflow_test_runner.py --test-type=frontend --base-url="$BASE_URL"
FRONTEND_RESULT=$?

# Test 3: End-to-End Automation
echo ""
echo "🤖 Test 3: End-to-End Automation"
echo "   User Concern: 'click start test and come back everything done'"
python workflow_test_runner.py --test-type=automation --base-url="$BASE_URL"
AUTOMATION_RESULT=$?

# Test 4: Specific Video Files
echo ""
echo "📹 Test 4: Specific Video Files"
echo "   Testing: child-1-1-1.mp4 and ae8e974b-0533-4cab-959a-493793e00328.mp4"
python workflow_test_runner.py --test-type=specific --base-url="$BASE_URL"
SPECIFIC_RESULT=$?

# Generate summary
echo ""
echo "📊 TEST SUMMARY"
echo "==============="

TOTAL_TESTS=4
PASSED_TESTS=0

echo "Test Results:"
if [ $SEQUENTIAL_RESULT -eq 0 ]; then
    echo "  ✅ Sequential Video Processing: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  ❌ Sequential Video Processing: FAILED"
fi

if [ $FRONTEND_RESULT -eq 0 ]; then
    echo "  ✅ Frontend Integration: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  ❌ Frontend Integration: FAILED"
fi

if [ $AUTOMATION_RESULT -eq 0 ]; then
    echo "  ✅ End-to-End Automation: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  ❌ End-to-End Automation: FAILED"
fi

if [ $SPECIFIC_RESULT -eq 0 ]; then
    echo "  ✅ Specific Video Files: PASSED"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  ❌ Specific Video Files: FAILED"
fi

echo ""
echo "Summary: $PASSED_TESTS/$TOTAL_TESTS tests passed"

# Overall result
if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo ""
    echo "🎉 ALL WORKFLOW TESTS PASSED!"
    echo ""
    echo "✅ Key User Concerns Addressed:"
    echo "   - Sequential video processing (no phantom sessions)"
    echo "   - End-to-end automation workflow"
    echo "   - Enhanced Test Execution page functionality" 
    echo "   - Specific video files processing correctly"
    echo ""
    exit 0
else
    echo ""
    echo "⚠️  Some tests failed. Review the output above for details."
    echo ""
    echo "Common Issues:"
    echo "  - Backend server not fully started"
    echo "  - Missing API endpoints"
    echo "  - Database not initialized"
    echo "  - WebSocket connections failing"
    echo ""
    exit 1
fi