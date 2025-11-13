#!/bin/bash
#
# Comprehensive Test Suite Runner
# Runs all production-quality tests with coverage reporting
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "================================================"
echo "  Comprehensive Test Suite for All Fixes"
echo "================================================"
echo ""
echo "Project Root: $PROJECT_ROOT"
echo "Python Version: $(python --version)"
echo ""

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    echo "Activating virtual environment..."
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Install test dependencies
echo "Installing test dependencies..."
pip install -q pytest pytest-cov pytest-asyncio pytest-mock faker sqlalchemy

echo ""
echo "================================================"
echo "  Running Test Categories"
echo "================================================"
echo ""

# Test Category 1: Ground Truth Matching
echo "▶ 1. Ground Truth Matching Tests"
echo "   Testing: Double-matching prevention, tolerance clamping, boundary protection"
pytest -v \
    "$SCRIPT_DIR/test_ground_truth_matching_double_matching.py" \
    "$SCRIPT_DIR/test_tolerance_window_clamping.py" \
    --cov=services.ground_truth_matching_service \
    --cov-report=term-missing \
    --cov-report=html:htmlcov/gt_matching

echo ""

# Test Category 2: Transaction Atomicity
echo "▶ 2. Transaction Atomicity Tests"
echo "   Testing: Rollback on failure, idempotent retry, isolation"
pytest -v \
    "$SCRIPT_DIR/test_transaction_atomicity.py" \
    --cov=services.session_completion_service \
    --cov-report=term-missing \
    --cov-append

echo ""

# Test Category 3: Approval Workflow
echo "▶ 3. Approval Workflow Tests"
echo "   Testing: Approve/reject, authorization, conditional pass"
pytest -v \
    "$SCRIPT_DIR/test_approval_workflow.py" \
    --cov=models \
    --cov-report=term-missing \
    --cov-append

echo ""

# Test Category 4: WebSocket Room Isolation
echo "▶ 4. WebSocket Room Isolation Tests"
echo "   Testing: Session-specific events, no cross-leakage"
pytest -v \
    "$SCRIPT_DIR/test_websocket_room_isolation.py" \
    --cov=socketio_server \
    --cov-report=term-missing \
    --cov-append

echo ""

# Test Category 5: Integration Tests
echo "▶ 5. Comprehensive Integration Tests"
echo "   Testing: End-to-end workflow with all fixes"
pytest -v \
    "$SCRIPT_DIR/test_comprehensive_integration.py" \
    --cov=services \
    --cov-report=term-missing \
    --cov-append

echo ""

# Test Category 6: Performance Tests (if they exist)
if [ -f "$SCRIPT_DIR/performance/test_matching_performance.py" ]; then
    echo "▶ 6. Performance Tests"
    echo "   Testing: Matching algorithm performance, concurrent sessions"
    pytest -v \
        "$SCRIPT_DIR/performance/test_matching_performance.py" \
        --cov-append
    echo ""
fi

# Generate final coverage report
echo "================================================"
echo "  Coverage Summary"
echo "================================================"
echo ""

pytest \
    "$SCRIPT_DIR/test_ground_truth_matching_double_matching.py" \
    "$SCRIPT_DIR/test_tolerance_window_clamping.py" \
    "$SCRIPT_DIR/test_transaction_atomicity.py" \
    "$SCRIPT_DIR/test_approval_workflow.py" \
    "$SCRIPT_DIR/test_websocket_room_isolation.py" \
    "$SCRIPT_DIR/test_comprehensive_integration.py" \
    --cov=services \
    --cov=models \
    --cov=socketio_server \
    --cov-report=term \
    --cov-report=html:htmlcov/complete \
    --cov-report=json:coverage.json \
    -q

echo ""
echo "================================================"
echo "  Test Suite Complete"
echo "================================================"
echo ""
echo "Coverage reports generated:"
echo "  - HTML: htmlcov/complete/index.html"
echo "  - JSON: coverage.json"
echo ""

# Check coverage threshold
COVERAGE_PCT=$(python -c "import json; data=json.load(open('coverage.json')); print(data['totals']['percent_covered'])")

echo "Total Coverage: ${COVERAGE_PCT}%"

if (( $(echo "$COVERAGE_PCT >= 90" | bc -l) )); then
    echo "✅ Coverage target met (>90%)"
    exit 0
else
    echo "⚠️  Coverage below 90% threshold"
    echo "   Review htmlcov/complete/index.html for details"
    exit 1
fi
