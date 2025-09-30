#!/bin/bash

# Ground Truth Integration Test Execution Script
# ==============================================
# 
# Comprehensive test execution script for ground truth functionality
# with environment setup, test execution, and result analysis.
#
# Usage:
#   ./run_ground_truth_tests.sh [options]
#
# Options:
#   --category <name>     Run specific test category only
#   --parallel <n>        Number of parallel workers (default: 4)
#   --timeout <seconds>   Test timeout (default: 3600)
#   --no-cleanup          Skip cleanup after tests
#   --debug               Enable debug mode
#   --help                Show this help message
#
# Author: QA Specialist
# Date: 2024-09-29

set -e  # Exit on any error

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_CONFIG="$SCRIPT_DIR/config/ground_truth_test_config.json"
RESULTS_DIR="$SCRIPT_DIR/results/$(date +%Y%m%d_%H%M%S)"

# Default options
CATEGORY=""
PARALLEL_WORKERS=4
TIMEOUT=3600
CLEANUP=true
DEBUG=false
VERBOSE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
Ground Truth Integration Test Runner

Usage: $0 [options]

Options:
    --category <name>     Run specific test category only
                         (e2e, data_flow, concurrency, error_handling)
    --parallel <n>        Number of parallel workers (default: 4)
    --timeout <seconds>   Test timeout (default: 3600)
    --no-cleanup          Skip cleanup after tests
    --debug               Enable debug mode
    --verbose             Enable verbose output
    --help                Show this help message

Examples:
    $0                                    # Run all tests
    $0 --category e2e                     # Run only E2E tests
    $0 --parallel 8 --timeout 1800       # Use 8 workers, 30min timeout
    $0 --debug --no-cleanup              # Debug mode with no cleanup

Test Categories:
    e2e                  End-to-end integration tests
    data_flow            Data consistency validation tests
    concurrency          Concurrent operations tests
    error_handling       Error scenario tests
    all                  All test categories (default)

EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --category)
                CATEGORY="$2"
                shift 2
                ;;
            --parallel)
                PARALLEL_WORKERS="$2"
                shift 2
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            --no-cleanup)
                CLEANUP=false
                shift
                ;;
            --debug)
                DEBUG=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Environment validation
validate_environment() {
    log_info "Validating test environment..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    log_info "Python version: $PYTHON_VERSION"
    
    # Check if we're in the correct directory
    if [[ ! -f "$PROJECT_ROOT/main.py" ]]; then
        log_error "Must be run from the project root directory"
        exit 1
    fi
    
    # Check if test configuration exists
    if [[ ! -f "$TEST_CONFIG" ]]; then
        log_error "Test configuration not found: $TEST_CONFIG"
        exit 1
    fi
    
    # Check database access
    if [[ -f "$PROJECT_ROOT/dev_database.db" ]]; then
        log_info "Found development database"
    else
        log_warning "Development database not found - will create test database"
    fi
    
    # Check required Python packages
    log_info "Checking Python dependencies..."
    if ! python3 -c "import pytest, fastapi, sqlalchemy" 2>/dev/null; then
        log_error "Required Python packages not installed. Run: pip install -r requirements.txt"
        exit 1
    fi
    
    log_success "Environment validation completed"
}

# Setup test environment
setup_test_environment() {
    log_info "Setting up test environment..."
    
    # Create results directory
    mkdir -p "$RESULTS_DIR"
    log_info "Results directory: $RESULTS_DIR"
    
    # Set environment variables
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    export TEST_MODE="integration"
    export TEST_RESULTS_DIR="$RESULTS_DIR"
    
    if [[ "$DEBUG" == "true" ]]; then
        export DEBUG_MODE="true"
        export PYTEST_VERBOSITY="-vvv"
    else
        export PYTEST_VERBOSITY="-v"
    fi
    
    # Create temporary directories
    export TEMP_UPLOAD_DIR="$RESULTS_DIR/temp_uploads"
    export TEMP_SCREENSHOTS_DIR="$RESULTS_DIR/temp_screenshots"
    mkdir -p "$TEMP_UPLOAD_DIR" "$TEMP_SCREENSHOTS_DIR"
    
    log_success "Test environment setup completed"
}

# Run specific test category
run_test_category() {
    local category=$1
    local test_files=""
    
    case $category in
        "e2e")
            test_files="tests/integration/test_ground_truth_e2e_integration.py"
            ;;
        "data_flow")
            test_files="tests/integration/test_ground_truth_data_flow.py"
            ;;
        "concurrency")
            test_files="tests/integration/test_ground_truth_concurrency.py"
            ;;
        "error_handling")
            test_files="tests/integration/test_ground_truth_error_handling.py"
            ;;
        "existing")
            test_files="tests/test_ground_truth_system.py"
            ;;
        *)
            log_error "Unknown test category: $category"
            return 1
            ;;
    esac
    
    if [[ ! -f "$PROJECT_ROOT/$test_files" ]]; then
        log_warning "Test file not found: $test_files"
        return 1
    fi
    
    log_info "Running $category tests: $test_files"
    
    # Build pytest command
    local pytest_cmd="python3 -m pytest"
    pytest_cmd="$pytest_cmd $PYTEST_VERBOSITY"
    pytest_cmd="$pytest_cmd --tb=short"
    pytest_cmd="$pytest_cmd --durations=10"
    pytest_cmd="$pytest_cmd --junit-xml=$RESULTS_DIR/${category}_results.xml"
    pytest_cmd="$pytest_cmd --cov=services.ground_truth_service"
    pytest_cmd="$pytest_cmd --cov=services.detection_pipeline_service"
    pytest_cmd="$pytest_cmd --cov=routers.ground_truth"
    pytest_cmd="$pytest_cmd --cov-report=html:$RESULTS_DIR/${category}_coverage"
    pytest_cmd="$pytest_cmd --cov-report=xml:$RESULTS_DIR/${category}_coverage.xml"
    pytest_cmd="$pytest_cmd --cov-report=term-missing"
    
    if [[ $PARALLEL_WORKERS -gt 1 ]]; then
        pytest_cmd="$pytest_cmd -n $PARALLEL_WORKERS"
    fi
    
    pytest_cmd="$pytest_cmd --timeout=$TIMEOUT"
    pytest_cmd="$pytest_cmd $test_files"
    
    # Execute tests
    cd "$PROJECT_ROOT"
    
    if [[ "$VERBOSE" == "true" ]]; then
        log_info "Executing: $pytest_cmd"
    fi
    
    local start_time=$(date +%s)
    
    if eval $pytest_cmd; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_success "$category tests completed in ${duration}s"
        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_error "$category tests failed after ${duration}s"
        return 1
    fi
}

# Run all test categories
run_all_tests() {
    log_info "Running all ground truth integration tests..."
    
    local categories=("e2e" "data_flow" "concurrency" "error_handling")
    local failed_categories=()
    local start_time=$(date +%s)
    
    # Run comprehensive test suite using the Python runner
    log_info "Using comprehensive test runner..."
    cd "$PROJECT_ROOT"
    
    local runner_cmd="python3 tests/run_ground_truth_integration_suite.py"
    runner_cmd="$runner_cmd --config $TEST_CONFIG"
    runner_cmd="$runner_cmd --parallel $PARALLEL_WORKERS"
    runner_cmd="$runner_cmd --timeout $TIMEOUT"
    
    if [[ "$VERBOSE" == "true" ]]; then
        runner_cmd="$runner_cmd --verbose"
    fi
    
    if [[ "$DEBUG" == "false" ]]; then
        runner_cmd="$runner_cmd --no-html"
    fi
    
    log_info "Executing comprehensive test suite..."
    if eval $runner_cmd; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_success "All tests completed successfully in ${duration}s"
        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_error "Test suite failed after ${duration}s"
        return 1
    fi
}

# Generate test summary
generate_summary() {
    log_info "Generating test summary..."
    
    local summary_file="$RESULTS_DIR/test_execution_summary.txt"
    
    cat > "$summary_file" << EOF
Ground Truth Integration Test Execution Summary
==============================================

Execution Details:
- Date: $(date)
- Category: ${CATEGORY:-"all"}
- Parallel Workers: $PARALLEL_WORKERS
- Timeout: ${TIMEOUT}s
- Debug Mode: $DEBUG
- Cleanup: $CLEANUP

Results Directory: $RESULTS_DIR

Test Files:
$(find "$RESULTS_DIR" -name "*.xml" -o -name "*.html" -o -name "*.json" | sort)

Environment:
- Python: $(python3 --version)
- Platform: $(uname -a)
- Working Directory: $(pwd)

EOF
    
    log_info "Summary saved to: $summary_file"
}

# Cleanup function
cleanup_test_environment() {
    if [[ "$CLEANUP" == "true" ]]; then
        log_info "Cleaning up test environment..."
        
        # Remove temporary files (but preserve results)
        if [[ -d "$TEMP_UPLOAD_DIR" ]]; then
            rm -rf "$TEMP_UPLOAD_DIR"
            log_info "Removed temporary upload directory"
        fi
        
        if [[ -d "$TEMP_SCREENSHOTS_DIR" ]]; then
            rm -rf "$TEMP_SCREENSHOTS_DIR"  
            log_info "Removed temporary screenshots directory"
        fi
        
        # Clean up any test database files
        find "$PROJECT_ROOT" -name "test_*.db" -delete 2>/dev/null || true
        
        log_success "Cleanup completed"
    else
        log_warning "Cleanup skipped (--no-cleanup specified)"
    fi
}

# Signal handlers
trap 'log_error "Test execution interrupted"; cleanup_test_environment; exit 130' INT TERM

# Main execution function
main() {
    echo "=========================================="
    echo "Ground Truth Integration Test Runner"
    echo "=========================================="
    echo
    
    parse_arguments "$@"
    validate_environment
    setup_test_environment
    
    local exit_code=0
    
    if [[ -n "$CATEGORY" ]]; then
        log_info "Running specific category: $CATEGORY"
        if ! run_test_category "$CATEGORY"; then
            exit_code=1
        fi
    else
        log_info "Running all test categories"
        if ! run_all_tests; then
            exit_code=1
        fi
    fi
    
    generate_summary
    cleanup_test_environment
    
    echo
    echo "=========================================="
    if [[ $exit_code -eq 0 ]]; then
        log_success "All tests completed successfully!"
        echo "Results available in: $RESULTS_DIR"
    else
        log_error "Some tests failed!"
        echo "Check results in: $RESULTS_DIR"
    fi
    echo "=========================================="
    
    exit $exit_code
}

# Run main function with all arguments
main "$@"