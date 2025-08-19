#!/bin/bash

# TypeScript Error Fix Tests Runner
# London School TDD Test Execution Script

set -e

echo "🚀 Starting TypeScript Error Fix Tests - London School TDD"
echo "============================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$TEST_DIR")"
COVERAGE_DIR="$ROOT_DIR/coverage/typescript-error-fixes"
REPORTS_DIR="$ROOT_DIR/reports/typescript-error-fixes"

# Create directories
mkdir -p "$COVERAGE_DIR"
mkdir -p "$REPORTS_DIR"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to run specific test suite
run_test_suite() {
    local suite_name="$1"
    local test_pattern="$2"
    
    print_status "Running $suite_name tests..."
    
    if npx jest --config="$TEST_DIR/jest.config.js" \
              --testPathPattern="$test_pattern" \
              --coverage \
              --coverageDirectory="$COVERAGE_DIR/$suite_name" \
              --verbose; then
        print_success "$suite_name tests passed!"
        return 0
    else
        print_error "$suite_name tests failed!"
        return 1
    fi
}

# Function to validate TypeScript compilation
validate_typescript() {
    print_status "Validating TypeScript compilation..."
    
    if npx tsc --noEmit --project "$ROOT_DIR/tsconfig.json"; then
        print_success "TypeScript compilation successful!"
        return 0
    else
        print_error "TypeScript compilation failed!"
        return 1
    fi
}

# Function to run linting
run_linting() {
    print_status "Running ESLint checks..."
    
    if npx eslint "$TEST_DIR/**/*.{ts,tsx}" --fix; then
        print_success "Linting passed!"
        return 0
    else
        print_warning "Linting issues found (fixed automatically where possible)"
        return 0
    fi
}

# Function to generate comprehensive report
generate_report() {
    print_status "Generating test reports..."
    
    # Combine coverage reports
    if command -v lcov &> /dev/null; then
        find "$COVERAGE_DIR" -name "lcov.info" -exec cat {} \; > "$REPORTS_DIR/combined-coverage.lcov"
    fi
    
    # Generate HTML coverage report
    if command -v genhtml &> /dev/null; then
        genhtml "$REPORTS_DIR/combined-coverage.lcov" -o "$REPORTS_DIR/html-coverage"
    fi
    
    # Create summary report
    cat > "$REPORTS_DIR/test-summary.md" << EOF
# TypeScript Error Fix Tests - Summary Report

## Test Execution Summary
- **Execution Time**: $(date)
- **Test Environment**: $(node --version)
- **Jest Version**: $(npx jest --version)

## Test Results

### Unit Tests
$(if [ -f "$COVERAGE_DIR/unit/coverage-summary.json" ]; then
    echo "✅ Unit tests completed"
    node -e "
    const coverage = require('$COVERAGE_DIR/unit/coverage-summary.json');
    console.log('- Lines: ' + coverage.total.lines.pct + '%');
    console.log('- Functions: ' + coverage.total.functions.pct + '%');
    console.log('- Branches: ' + coverage.total.branches.pct + '%');
    "
else
    echo "❌ Unit test coverage not available"
fi)

### Integration Tests
$(if [ -f "$COVERAGE_DIR/integration/coverage-summary.json" ]; then
    echo "✅ Integration tests completed"
else
    echo "❌ Integration test coverage not available"
fi)

## Coverage Report
- Combined coverage report: [HTML Report]($REPORTS_DIR/html-coverage/index.html)
- LCOV report: $REPORTS_DIR/combined-coverage.lcov

EOF

    print_success "Test reports generated in $REPORTS_DIR"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Node.js version
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed!"
        exit 1
    fi
    
    # Check npm/yarn
    if ! command -v npm &> /dev/null && ! command -v yarn &> /dev/null; then
        print_error "Neither npm nor yarn is installed!"
        exit 1
    fi
    
    # Check Jest
    if ! npx jest --version &> /dev/null; then
        print_error "Jest is not available!"
        exit 1
    fi
    
    print_success "All prerequisites satisfied"
}

# Main execution function
main() {
    local test_pattern=""
    local run_specific=""
    local skip_typescript=false
    local skip_linting=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --unit)
                run_specific="unit"
                shift
                ;;
            --integration)
                run_specific="integration"
                shift
                ;;
            --pattern)
                test_pattern="$2"
                shift 2
                ;;
            --skip-typescript)
                skip_typescript=true
                shift
                ;;
            --skip-linting)
                skip_linting=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --unit              Run only unit tests"
                echo "  --integration       Run only integration tests"
                echo "  --pattern PATTERN   Run tests matching pattern"
                echo "  --skip-typescript   Skip TypeScript compilation check"
                echo "  --skip-linting      Skip ESLint checks"
                echo "  --help              Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                           # Run all tests"
                echo "  $0 --unit                    # Run only unit tests"
                echo "  $0 --pattern import          # Run tests matching 'import'"
                echo "  $0 --skip-typescript         # Skip TS compilation check"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Start execution
    echo "Configuration:"
    echo "  Test Directory: $TEST_DIR"
    echo "  Coverage Directory: $COVERAGE_DIR"
    echo "  Reports Directory: $REPORTS_DIR"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # TypeScript compilation check
    if [ "$skip_typescript" = false ]; then
        if ! validate_typescript; then
            print_error "TypeScript validation failed. Use --skip-typescript to bypass."
            exit 1
        fi
    fi
    
    # Linting check
    if [ "$skip_linting" = false ]; then
        run_linting
    fi
    
    # Initialize test results
    local test_failures=0
    
    # Run tests based on parameters
    if [ -n "$test_pattern" ]; then
        print_status "Running tests matching pattern: $test_pattern"
        if ! npx jest --config="$TEST_DIR/jest.config.js" \
                     --testNamePattern="$test_pattern" \
                     --coverage \
                     --coverageDirectory="$COVERAGE_DIR/pattern" \
                     --verbose; then
            ((test_failures++))
        fi
    elif [ "$run_specific" = "unit" ]; then
        if ! run_test_suite "unit" "unit"; then
            ((test_failures++))
        fi
    elif [ "$run_specific" = "integration" ]; then
        if ! run_test_suite "integration" "integration"; then
            ((test_failures++))
        fi
    else
        # Run all test suites
        print_status "Running all test suites..."
        
        if ! run_test_suite "unit" "unit"; then
            ((test_failures++))
        fi
        
        if ! run_test_suite "integration" "integration"; then
            ((test_failures++))
        fi
        
        # Run combined coverage
        print_status "Generating combined coverage report..."
        if ! npx jest --config="$TEST_DIR/jest.config.js" \
                     --coverage \
                     --coverageDirectory="$COVERAGE_DIR/combined" \
                     --passWithNoTests \
                     --verbose; then
            print_warning "Combined coverage generation had issues"
        fi
    fi
    
    # Generate reports
    generate_report
    
    # Final summary
    echo ""
    echo "============================================================"
    if [ $test_failures -eq 0 ]; then
        print_success "🎉 All TypeScript Error Fix Tests Passed!"
        echo ""
        echo "📊 Coverage Report: $REPORTS_DIR/html-coverage/index.html"
        echo "📋 Test Summary: $REPORTS_DIR/test-summary.md"
        exit 0
    else
        print_error "❌ $test_failures test suite(s) failed!"
        echo ""
        echo "Check the output above for details on failures."
        echo "📋 Test Summary: $REPORTS_DIR/test-summary.md"
        exit 1
    fi
}

# Execute main function with all arguments
main "$@"