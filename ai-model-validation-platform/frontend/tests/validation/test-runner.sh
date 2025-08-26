#!/bin/bash

# Comprehensive Test Runner for Deployment Validation
# This script runs all validation tests and generates reports

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEST_DIR="tests/validation"
RESULTS_DIR="test-results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="${RESULTS_DIR}/validation_report_${TIMESTAMP}.log"

echo -e "${BLUE}🚀 Starting Comprehensive Deployment Validation${NC}"
echo -e "${BLUE}================================================${NC}"

# Create results directory
mkdir -p "${RESULTS_DIR}"

# Initialize report file
echo "Deployment Validation Report - $(date)" > "${REPORT_FILE}"
echo "=============================================" >> "${REPORT_FILE}"
echo "" >> "${REPORT_FILE}"

# Function to log messages
log_message() {
    local level=$1
    local message=$2
    local color=""
    
    case $level in
        "INFO") color=$GREEN ;;
        "WARN") color=$YELLOW ;;
        "ERROR") color=$RED ;;
    esac
    
    echo -e "${color}[$level]${NC} $message"
    echo "[$level] $message" >> "${REPORT_FILE}"
}

# Function to run a specific test suite
run_test_suite() {
    local test_file=$1
    local test_name=$2
    
    log_message "INFO" "Running $test_name..."
    
    local start_time=$(date +%s)
    
    if npm test -- --testPathPattern="${test_file}" --verbose --coverage=false --silent 2>&1 | tee -a "${REPORT_FILE}"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_message "INFO" "$test_name completed successfully in ${duration}s"
        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_message "ERROR" "$test_name failed after ${duration}s"
        return 1
    fi
}

# Function to check prerequisites
check_prerequisites() {
    log_message "INFO" "Checking prerequisites..."
    
    # Check if npm is installed
    if ! command -v npm &> /dev/null; then
        log_message "ERROR" "npm is not installed"
        exit 1
    fi
    
    # Check if test files exist
    local test_files=(
        "${TEST_DIR}/comprehensive-fix-validation.test.ts"
        "${TEST_DIR}/deployment-verification.test.ts"
        "${TEST_DIR}/performance-monitoring.test.ts"
        "${TEST_DIR}/url-integrity-validation.test.ts"
        "${TEST_DIR}/configuration-validation.test.ts"
    )
    
    for test_file in "${test_files[@]}"; do
        if [[ ! -f "$test_file" ]]; then
            log_message "ERROR" "Test file not found: $test_file"
            exit 1
        fi
    done
    
    log_message "INFO" "Prerequisites check passed"
}

# Function to run quick validation
run_quick_validation() {
    log_message "INFO" "Running quick validation tests..."
    
    local quick_tests=(
        "${TEST_DIR}/comprehensive-fix-validation.test.ts|Core URL Fixing"
    )
    
    local total_tests=0
    local passed_tests=0
    
    for test_info in "${quick_tests[@]}"; do
        IFS='|' read -r test_file test_name <<< "$test_info"
        total_tests=$((total_tests + 1))
        
        if run_test_suite "$test_file" "$test_name"; then
            passed_tests=$((passed_tests + 1))
        fi
    done
    
    log_message "INFO" "Quick validation: $passed_tests/$total_tests tests passed"
    return $((total_tests - passed_tests))
}

# Function to run full validation
run_full_validation() {
    log_message "INFO" "Running full validation test suite..."
    
    local test_suites=(
        "${TEST_DIR}/comprehensive-fix-validation.test.ts|Comprehensive Fix Validation"
        "${TEST_DIR}/deployment-verification.test.ts|Deployment Verification"
        "${TEST_DIR}/performance-monitoring.test.ts|Performance Monitoring"
        "${TEST_DIR}/url-integrity-validation.test.ts|URL Integrity Validation"
        "${TEST_DIR}/configuration-validation.test.ts|Configuration Validation"
    )
    
    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    
    echo "" >> "${REPORT_FILE}"
    echo "DETAILED TEST RESULTS:" >> "${REPORT_FILE}"
    echo "=====================" >> "${REPORT_FILE}"
    
    for test_info in "${test_suites[@]}"; do
        IFS='|' read -r test_file test_name <<< "$test_info"
        total_tests=$((total_tests + 1))
        
        echo "" >> "${REPORT_FILE}"
        echo "--- $test_name ---" >> "${REPORT_FILE}"
        
        if run_test_suite "$test_file" "$test_name"; then
            passed_tests=$((passed_tests + 1))
            echo "RESULT: PASSED" >> "${REPORT_FILE}"
        else
            failed_tests=$((failed_tests + 1))
            echo "RESULT: FAILED" >> "${REPORT_FILE}"
        fi
    done
    
    # Generate summary
    echo "" >> "${REPORT_FILE}"
    echo "TEST SUMMARY:" >> "${REPORT_FILE}"
    echo "=============" >> "${REPORT_FILE}"
    echo "Total Tests: $total_tests" >> "${REPORT_FILE}"
    echo "Passed: $passed_tests" >> "${REPORT_FILE}"
    echo "Failed: $failed_tests" >> "${REPORT_FILE}"
    echo "Success Rate: $(( (passed_tests * 100) / total_tests ))%" >> "${REPORT_FILE}"
    
    log_message "INFO" "Full validation completed: $passed_tests/$total_tests tests passed"
    
    if [[ $failed_tests -eq 0 ]]; then
        log_message "INFO" "🎉 All validation tests passed!"
        return 0
    else
        log_message "ERROR" "⚠️ $failed_tests test(s) failed"
        return $failed_tests
    fi
}

# Function to generate coverage report
generate_coverage_report() {
    log_message "INFO" "Generating test coverage report..."
    
    if npm test -- --coverage --coverageDirectory="${RESULTS_DIR}/coverage" --watchAll=false 2>&1 | tee -a "${REPORT_FILE}"; then
        log_message "INFO" "Coverage report generated in ${RESULTS_DIR}/coverage"
        
        # Copy coverage summary to main report
        if [[ -f "${RESULTS_DIR}/coverage/lcov-report/index.html" ]]; then
            echo "" >> "${REPORT_FILE}"
            echo "COVERAGE REPORT:" >> "${REPORT_FILE}"
            echo "================" >> "${REPORT_FILE}"
            echo "Detailed coverage report: ${RESULTS_DIR}/coverage/lcov-report/index.html" >> "${REPORT_FILE}"
        fi
    else
        log_message "WARN" "Failed to generate coverage report"
    fi
}

# Function to validate environment
validate_environment() {
    log_message "INFO" "Validating environment setup..."
    
    # Check Node.js version
    local node_version=$(node --version)
    log_message "INFO" "Node.js version: $node_version"
    echo "Node.js version: $node_version" >> "${REPORT_FILE}"
    
    # Check npm version
    local npm_version=$(npm --version)
    log_message "INFO" "npm version: $npm_version"
    echo "npm version: $npm_version" >> "${REPORT_FILE}"
    
    # Check if dependencies are installed
    if [[ ! -d "node_modules" ]]; then
        log_message "WARN" "node_modules not found, installing dependencies..."
        npm install
    fi
    
    # Check current hostname/environment
    local hostname=$(hostname)
    log_message "INFO" "Running on: $hostname"
    echo "Hostname: $hostname" >> "${REPORT_FILE}"
    
    # Check environment variables
    echo "" >> "${REPORT_FILE}"
    echo "ENVIRONMENT VARIABLES:" >> "${REPORT_FILE}"
    echo "=====================" >> "${REPORT_FILE}"
    echo "NODE_ENV: ${NODE_ENV:-'not set'}" >> "${REPORT_FILE}"
    echo "REACT_APP_API_URL: ${REACT_APP_API_URL:-'not set'}" >> "${REPORT_FILE}"
    echo "REACT_APP_WS_URL: ${REACT_APP_WS_URL:-'not set'}" >> "${REPORT_FILE}"
    echo "REACT_APP_VIDEO_BASE_URL: ${REACT_APP_VIDEO_BASE_URL:-'not set'}" >> "${REPORT_FILE}"
}

# Function to cleanup
cleanup() {
    log_message "INFO" "Cleaning up temporary files..."
    # Add any cleanup operations here
}

# Function to display usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  --quick       Run only quick validation tests"
    echo "  --full        Run full validation test suite (default)"
    echo "  --coverage    Generate test coverage report"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                  # Run full validation"
    echo "  $0 --quick          # Run quick validation only"
    echo "  $0 --full --coverage # Run full validation with coverage"
}

# Main execution
main() {
    local mode="full"
    local generate_coverage=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick)
                mode="quick"
                shift
                ;;
            --full)
                mode="full"
                shift
                ;;
            --coverage)
                generate_coverage=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                log_message "ERROR" "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Setup trap for cleanup
    trap cleanup EXIT
    
    # Start validation process
    local start_time=$(date +%s)
    
    validate_environment
    check_prerequisites
    
    local exit_code=0
    
    case $mode in
        "quick")
            run_quick_validation || exit_code=$?
            ;;
        "full")
            run_full_validation || exit_code=$?
            ;;
    esac
    
    if [[ $generate_coverage == true ]]; then
        generate_coverage_report
    fi
    
    # Calculate total execution time
    local end_time=$(date +%s)
    local total_time=$((end_time - start_time))
    
    echo "" >> "${REPORT_FILE}"
    echo "EXECUTION SUMMARY:" >> "${REPORT_FILE}"
    echo "==================" >> "${REPORT_FILE}"
    echo "Total execution time: ${total_time}s" >> "${REPORT_FILE}"
    echo "Report file: ${REPORT_FILE}" >> "${REPORT_FILE}"
    echo "Timestamp: $(date)" >> "${REPORT_FILE}"
    
    log_message "INFO" "Validation completed in ${total_time}s"
    log_message "INFO" "Full report saved to: ${REPORT_FILE}"
    
    if [[ $exit_code -eq 0 ]]; then
        log_message "INFO" "🎉 Deployment validation successful!"
    else
        log_message "ERROR" "⚠️ Deployment validation failed with exit code: $exit_code"
    fi
    
    exit $exit_code
}

# Run main function with all arguments
main "$@"