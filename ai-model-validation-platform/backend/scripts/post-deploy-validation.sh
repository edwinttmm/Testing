#!/bin/bash
################################################################################
# HIL Backend Post-Deployment Validation Script
# Version: 1.0.0
# Description: Comprehensive validation after deployment to ensure system health
################################################################################

set -e
set -o pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
BASE_URL="http://localhost:8000"
TIMEOUT=10

# Results tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNING=0

################################################################################
# Utility Functions
################################################################################

log_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((TESTS_PASSED++))
}

log_fail() {
    echo -e "${RED}✗${NC} $1"
    ((TESTS_FAILED++))
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((TESTS_WARNING++))
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

http_get() {
    local url="$1"
    curl -sf --max-time "$TIMEOUT" "$url" 2>/dev/null
}

http_get_status() {
    local url="$1"
    curl -sf -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null
}

################################################################################
# Process Checks
################################################################################

check_process_running() {
    log_info "Checking if backend process is running..."

    if pgrep -f "python3 main.py" > /dev/null; then
        local pid=$(pgrep -f "python3 main.py")
        local uptime=$(ps -p "$pid" -o etime= 2>/dev/null | xargs)
        log_pass "Backend process running (PID: $pid, uptime: $uptime)"
        return 0
    else
        log_fail "Backend process not found"
        return 1
    fi
}

check_port_listening() {
    log_info "Checking if port 8000 is listening..."

    if lsof -ti:8000 > /dev/null 2>&1; then
        log_pass "Port 8000 is listening"
        return 0
    else
        log_fail "Port 8000 is not listening"
        return 1
    fi
}

check_memory_usage() {
    log_info "Checking backend memory usage..."

    local pid=$(pgrep -f "python3 main.py" | head -1)

    if [ -n "$pid" ]; then
        local mem_mb=$(ps -p "$pid" -o rss= | awk '{print int($1/1024)}')

        if [ "$mem_mb" -gt 1024 ]; then
            log_warn "High memory usage: ${mem_mb}MB"
        else
            log_pass "Memory usage: ${mem_mb}MB"
        fi
        return 0
    else
        log_fail "Cannot check memory usage - process not found"
        return 1
    fi
}

################################################################################
# Health Endpoint Tests
################################################################################

test_health_endpoint() {
    log_info "Testing /health endpoint..."

    local status=$(http_get_status "${BASE_URL}/health")

    if [ "$status" = "200" ]; then
        local response=$(http_get "${BASE_URL}/health")
        log_pass "Health endpoint responding (status: 200)"
        log_info "Response: $response"
        return 0
    else
        log_fail "Health endpoint failed (status: ${status:-timeout})"
        return 1
    fi
}

test_api_health() {
    log_info "Testing /api/health endpoint..."

    local status=$(http_get_status "${BASE_URL}/api/health")

    if [ "$status" = "200" ]; then
        log_pass "API health endpoint responding"
        return 0
    else
        log_warn "API health endpoint not responding (status: ${status:-timeout})"
        return 0
    fi
}

test_database_health() {
    log_info "Testing /api/database/health endpoint..."

    local status=$(http_get_status "${BASE_URL}/api/database/health")

    if [ "$status" = "200" ]; then
        local response=$(http_get "${BASE_URL}/api/database/health")
        log_pass "Database health check passed"
        log_info "Response: $response"
        return 0
    else
        log_warn "Database health endpoint not responding (status: ${status:-timeout})"
        return 0
    fi
}

################################################################################
# API Smoke Tests
################################################################################

test_projects_endpoint() {
    log_info "Testing /api/projects endpoint..."

    local status=$(http_get_status "${BASE_URL}/api/projects")

    if [ "$status" = "200" ]; then
        log_pass "Projects endpoint responding"
        return 0
    else
        log_fail "Projects endpoint failed (status: ${status:-timeout})"
        return 1
    fi
}

test_videos_endpoint() {
    log_info "Testing /api/videos endpoint..."

    local status=$(http_get_status "${BASE_URL}/api/videos")

    if [ "$status" = "200" ]; then
        log_pass "Videos endpoint responding"
        return 0
    else
        log_warn "Videos endpoint not responding (status: ${status:-timeout})"
        return 0
    fi
}

test_test_sessions_endpoint() {
    log_info "Testing /api/test-sessions endpoint..."

    local status=$(http_get_status "${BASE_URL}/api/test-sessions")

    if [ "$status" = "200" ]; then
        log_pass "Test sessions endpoint responding"
        return 0
    else
        log_warn "Test sessions endpoint not responding (status: ${status:-timeout})"
        return 0
    fi
}

################################################################################
# Timing Calculator Check
################################################################################

check_timing_calculator() {
    log_info "Checking timing synchronization calculator..."

    cd "$BACKEND_DIR"

    # Check if timing calculator modules are importable
    if python3 -c "from services.timing_synchronization_calculator import TimingSynchronizationCalculator" 2>/dev/null; then
        log_pass "Timing synchronization calculator loaded successfully"
        return 0
    else
        log_fail "Timing synchronization calculator failed to load"
        return 1
    fi
}

check_labjack_service() {
    log_info "Checking LabJack services..."

    cd "$BACKEND_DIR"

    # Check if LabJack services are importable
    if python3 -c "from services.real_labjack_service import get_real_labjack_service" 2>/dev/null; then
        log_pass "LabJack services loaded successfully"
        return 0
    else
        log_warn "LabJack services not available (may be optional)"
        return 0
    fi
}

################################################################################
# Log Analysis
################################################################################

check_startup_logs() {
    log_info "Analyzing startup logs..."

    local log_dir="${BACKEND_DIR}/logs"

    if [ ! -d "$log_dir" ]; then
        log_warn "Logs directory not found"
        return 0
    fi

    local recent_log=$(ls -t "${log_dir}"/backend_*.log 2>/dev/null | head -1)

    if [ -z "$recent_log" ]; then
        log_warn "No recent log files found"
        return 0
    fi

    # Check for critical errors
    local critical_errors=$(grep -i "critical\|fatal" "$recent_log" 2>/dev/null | wc -l)
    if [ "$critical_errors" -gt 0 ]; then
        log_fail "Found ${critical_errors} critical errors in logs"
        return 1
    fi

    # Check for errors
    local error_count=$(grep -i "error\|exception" "$recent_log" 2>/dev/null | wc -l)
    if [ "$error_count" -gt 10 ]; then
        log_warn "Found ${error_count} errors in logs (may be acceptable)"
    else
        log_pass "Minimal errors in logs (${error_count})"
    fi

    # Check for successful startup indicators
    if grep -q "Application startup complete\|Uvicorn running" "$recent_log" 2>/dev/null; then
        log_pass "Successful startup detected in logs"
    else
        log_warn "Could not confirm successful startup in logs"
    fi

    return 0
}

check_error_patterns() {
    log_info "Checking for common error patterns..."

    local log_dir="${BACKEND_DIR}/logs"
    local recent_log=$(ls -t "${log_dir}"/backend_*.log 2>/dev/null | head -1)

    if [ -z "$recent_log" ]; then
        return 0
    fi

    # Check for port binding errors
    if grep -q "Address already in use" "$recent_log" 2>/dev/null; then
        log_fail "Port binding error detected in logs"
        return 1
    fi

    # Check for import errors
    if grep -q "ImportError\|ModuleNotFoundError" "$recent_log" 2>/dev/null; then
        log_warn "Import errors detected (may be non-critical)"
    fi

    # Check for database errors
    if grep -q "database is locked\|OperationalError" "$recent_log" 2>/dev/null; then
        log_warn "Database errors detected"
    fi

    log_pass "No critical error patterns found"
    return 0
}

################################################################################
# WebSocket Tests
################################################################################

test_websocket_available() {
    log_info "Checking WebSocket endpoints..."

    # Just check if the service is running (actual WebSocket testing requires special tools)
    if pgrep -f "socketio" > /dev/null 2>&1; then
        log_pass "SocketIO service detected"
        return 0
    else
        log_info "SocketIO service status unknown (requires active connection to test)"
        return 0
    fi
}

################################################################################
# Performance Checks
################################################################################

check_response_time() {
    log_info "Checking API response times..."

    local start_time=$(date +%s%N)
    http_get "${BASE_URL}/health" > /dev/null 2>&1
    local end_time=$(date +%s%N)

    local response_time=$(( (end_time - start_time) / 1000000 ))

    if [ "$response_time" -lt 1000 ]; then
        log_pass "Health endpoint response time: ${response_time}ms"
    elif [ "$response_time" -lt 5000 ]; then
        log_warn "Slow response time: ${response_time}ms"
    else
        log_fail "Very slow response time: ${response_time}ms"
        return 1
    fi

    return 0
}

################################################################################
# Main Execution
################################################################################

main() {
    echo "=========================================="
    echo "HIL Backend Post-Deployment Validation"
    echo "=========================================="
    echo "Time: $(date)"
    echo "Backend: ${BACKEND_DIR}"
    echo "Base URL: ${BASE_URL}"
    echo ""

    # Wait a moment for services to stabilize
    sleep 2

    # Process checks
    check_process_running || true
    check_port_listening || true
    check_memory_usage || true
    echo ""

    # Health checks
    test_health_endpoint || true
    test_api_health || true
    test_database_health || true
    echo ""

    # API smoke tests
    test_projects_endpoint || true
    test_videos_endpoint || true
    test_test_sessions_endpoint || true
    echo ""

    # Service checks
    check_timing_calculator || true
    check_labjack_service || true
    echo ""

    # Log analysis
    check_startup_logs || true
    check_error_patterns || true
    echo ""

    # Additional checks
    test_websocket_available || true
    check_response_time || true
    echo ""

    # Summary
    echo "=========================================="
    echo "Post-Deployment Validation Summary"
    echo "=========================================="
    echo -e "${GREEN}Passed:${NC} ${TESTS_PASSED}"
    echo -e "${YELLOW}Warnings:${NC} ${TESTS_WARNING}"
    echo -e "${RED}Failed:${NC} ${TESTS_FAILED}"
    echo ""

    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "${RED}❌ Post-deployment validation FAILED${NC}"
        echo "Critical issues detected - review logs and consider rollback"
        exit 1
    elif [ $TESTS_WARNING -gt 0 ]; then
        echo -e "${YELLOW}⚠ Post-deployment validation passed with warnings${NC}"
        echo "System is running but review warnings"
        exit 0
    else
        echo -e "${GREEN}✅ All post-deployment validation tests PASSED${NC}"
        echo "System is healthy and ready for production use"
        exit 0
    fi
}

main "$@"
