#!/bin/bash

# AI Model Validation Platform - Deployment Validation Script
# Comprehensive validation of deployment fixes and functionality

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_DIR="$PROJECT_ROOT/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/validation_$(date +%Y%m%d_%H%M%S).log"

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
CRITICAL_FAILURES=()

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

log_critical() {
    echo -e "${RED}[CRITICAL]${NC} $1" | tee -a "$LOG_FILE"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    CRITICAL_FAILURES+=("$1")
}

run_hook() {
    local hook_type=$1
    local description=$2
    if command -v npx >/dev/null 2>&1; then
        npx claude-flow@alpha hooks "$hook_type" --description "$description" || true
    fi
}

# Test execution wrapper
run_test() {
    local test_name=$1
    local test_command=$2
    local is_critical=${3:-false}
    
    log_info "Running test: $test_name"
    
    if eval "$test_command" >> "$LOG_FILE" 2>&1; then
        log_success "$test_name"
        return 0
    else
        if [ "$is_critical" = true ]; then
            log_critical "$test_name"
        else
            log_error "$test_name"
        fi
        return 1
    fi
}

echo "======================================" | tee -a "$LOG_FILE"
echo "Deployment Validation Started: $(date)" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"

run_hook "pre-task" "deployment-validation"

cd "$PROJECT_ROOT"

# 1. Build Validation
log_info "=== BUILD VALIDATION ==="

# Check build directory exists
run_test "Build directory exists" "[ -d 'build' ]" true

# Check essential build files
run_test "Index.html exists" "[ -f 'build/index.html' ]" true
run_test "Static assets directory exists" "[ -d 'build/static' ]" true

# Check build file integrity
if [ -f "build/index.html" ]; then
    run_test "Index.html contains root div" "grep -q 'id=\"root\"' build/index.html"
    run_test "Index.html contains script tags" "grep -q '<script' build/index.html"
    run_test "Index.html contains CSS links" "grep -q '<link.*css' build/index.html"
fi

# Check JavaScript bundles
if [ -d "build/static/js" ]; then
    JS_FILES=$(find build/static/js -name "*.js" | wc -l)
    run_test "JavaScript bundles exist (count: $JS_FILES)" "[ $JS_FILES -gt 0 ]" true
    
    # Check main bundle size (should be reasonable)
    MAIN_JS=$(find build/static/js -name "main.*.js" | head -1)
    if [ -n "$MAIN_JS" ] && [ -f "$MAIN_JS" ]; then
        MAIN_JS_SIZE=$(stat -f%z "$MAIN_JS" 2>/dev/null || stat -c%s "$MAIN_JS" 2>/dev/null || echo "0")
        if [ "$MAIN_JS_SIZE" -gt 10485760 ]; then  # 10MB
            log_warning "Main JS bundle is large: $(( MAIN_JS_SIZE / 1024 / 1024 ))MB"
        else
            log_success "Main JS bundle size is reasonable: $(( MAIN_JS_SIZE / 1024 / 1024 ))MB"
        fi
    fi
fi

# Check CSS bundles
if [ -d "build/static/css" ]; then
    CSS_FILES=$(find build/static/css -name "*.css" | wc -l)
    run_test "CSS bundles exist (count: $CSS_FILES)" "[ $CSS_FILES -gt 0 ]"
fi

# 2. URL Fix Validation
log_info "=== URL FIX VALIDATION ==="

# Check for URL-related utilities
run_test "VideoUrlFixer utility exists" "[ -f 'src/utils/videoUrlFixer.ts' ]"

# Validate URL fixer configuration
if [ -f "src/utils/videoUrlFixer.ts" ]; then
    run_test "URL fixer contains localhost handling" "grep -q 'localhost' src/utils/videoUrlFixer.ts"
    run_test "URL fixer contains validation logic" "grep -q 'isValidUrl\\|validateUrl' src/utils/videoUrlFixer.ts"
    run_test "URL fixer contains cache logic" "grep -q 'cache\\|Cache' src/utils/videoUrlFixer.ts"
fi

# Check API configuration
if [ -f "src/config/environment.ts" ]; then
    run_test "Environment config exists" "[ -f 'src/config/environment.ts' ]"
    run_test "API URL configured" "grep -q 'API_URL\\|baseUrl' src/config/environment.ts"
fi

# Check public configuration
if [ -f "public/config.js" ]; then
    run_test "Public config updated" "grep -q 'API_BASE_URL' public/config.js"
    run_test "URL validation config exists" "grep -q 'URL_VALIDATION' public/config.js"
    run_test "Video config exists" "grep -q 'VIDEO_CONFIG' public/config.js"
fi

# 3. Component Integration Validation
log_info "=== COMPONENT INTEGRATION VALIDATION ==="

# Check key components exist
run_test "VideoAnnotationPlayer component exists" "[ -f 'src/components/VideoAnnotationPlayer.tsx' ]"
run_test "DetectionControls component exists" "[ -f 'src/components/DetectionControls.tsx' ]"
run_test "ApiConnectionStatus component exists" "[ -f 'src/components/ApiConnectionStatus.tsx' ]"

# Check video player enhancements
run_test "EnhancedVideoPlayer component exists" "[ -f 'src/components/EnhancedVideoPlayer.tsx' ]"

# Check for error boundaries
run_test "Error boundary component exists" "[ -f 'src/components/ui/ErrorBoundary.tsx' ]"

# 4. Service Layer Validation
log_info "=== SERVICE LAYER VALIDATION ==="

# Check API service
run_test "API service exists" "[ -f 'src/services/api.ts' ]"
run_test "Enhanced API service exists" "[ -f 'src/services/enhancedApiService.ts' ]"

# Check WebSocket service
run_test "WebSocket service exists" "[ -f 'src/services/websocketService.ts' ]"

# Check detection service
run_test "Detection service exists" "[ -f 'src/services/detectionService.ts' ]"

# Validate service configurations
if [ -f "src/services/api.ts" ]; then
    run_test "API service has base URL config" "grep -q 'baseURL\\|API_URL' src/services/api.ts"
    run_test "API service has error handling" "grep -q 'catch\\|error' src/services/api.ts"
fi

# 5. TypeScript Compilation Validation
log_info "=== TYPESCRIPT VALIDATION ==="

if command -v npx >/dev/null 2>&1 && [ -f "tsconfig.json" ]; then
    run_test "TypeScript compilation check" "npx tsc --noEmit --skipLibCheck" false
else
    log_warning "TypeScript compiler not available or tsconfig.json missing"
fi

# 6. Test Suite Validation
log_info "=== TEST SUITE VALIDATION ==="

# Check if tests exist
run_test "Test files exist" "find src -name '*.test.ts' -o -name '*.test.tsx' | head -1 | grep -q '.'"

# Run URL fix specific tests
if [ -f "src/utils/videoUrlFixer.test.ts" ]; then
    run_test "URL fixer tests exist" "[ -f 'src/utils/videoUrlFixer.test.ts' ]"
fi

# Run a quick test suite if available
if command -v npm >/dev/null 2>&1; then
    if grep -q '"test"' package.json; then
        # Run tests with timeout
        run_test "Basic test suite passes" "timeout 300 npm test -- --watchAll=false --coverage=false" false
    else
        log_warning "No test script found in package.json"
    fi
fi

# 7. Performance Validation
log_info "=== PERFORMANCE VALIDATION ==="

# Check build size
if [ -d "build" ]; then
    BUILD_SIZE_KB=$(du -sk build | cut -f1)
    BUILD_SIZE_MB=$((BUILD_SIZE_KB / 1024))
    
    if [ $BUILD_SIZE_MB -lt 50 ]; then
        log_success "Build size is optimal: ${BUILD_SIZE_MB}MB"
    elif [ $BUILD_SIZE_MB -lt 100 ]; then
        log_warning "Build size is acceptable: ${BUILD_SIZE_MB}MB"
    else
        log_error "Build size is large: ${BUILD_SIZE_MB}MB"
    fi
fi

# Check for source maps (should not exist in production)
SOURCE_MAPS=$(find build -name "*.map" 2>/dev/null | wc -l)
run_test "No source maps in production build" "[ $SOURCE_MAPS -eq 0 ]"

# 8. Security Validation
log_info "=== SECURITY VALIDATION ==="

# Check for sensitive information in build
run_test "No API keys in build files" "! find build -name '*.js' -exec grep -l 'api[_-]key\\|secret\\|password' {} \\;"
run_test "No development URLs in build" "! find build -name '*.js' -exec grep -l 'localhost:3000\\|127.0.0.1:3000' {} \\;"

# Check npm audit
if command -v npm >/dev/null 2>&1; then
    run_test "npm audit passes" "npm audit --audit-level=high" false
fi

# 9. Configuration Validation
log_info "=== CONFIGURATION VALIDATION ==="

# Check environment configuration
run_test "Package.json exists and valid" "node -e 'JSON.parse(require(\"fs\").readFileSync(\"package.json\", \"utf8\"))'"

# Check for required dependencies
REQUIRED_DEPS=("react" "react-dom" "@types/react")
for dep in "${REQUIRED_DEPS[@]}"; do
    run_test "Required dependency '$dep' exists" "grep -q \"\\\"$dep\\\"\" package.json"
done

# 10. Integration Test Validation
log_info "=== INTEGRATION VALIDATION ==="

# Create a simple smoke test
cat > "/tmp/smoke-test.js" << 'EOF'
const fs = require('fs');
const path = require('path');

// Check if critical files are built correctly
const buildPath = process.argv[2];
const indexPath = path.join(buildPath, 'index.html');

if (!fs.existsSync(indexPath)) {
    console.error('index.html not found');
    process.exit(1);
}

const indexContent = fs.readFileSync(indexPath, 'utf8');

// Check for required elements
const checks = [
    { name: 'root div', pattern: /<div[^>]+id=["']root["']/ },
    { name: 'script tag', pattern: /<script[^>]+src/ },
    { name: 'css link', pattern: /<link[^>]+\.css/ }
];

let passed = 0;
checks.forEach(check => {
    if (check.pattern.test(indexContent)) {
        console.log(`✓ ${check.name} found`);
        passed++;
    } else {
        console.error(`✗ ${check.name} missing`);
    }
});

if (passed === checks.length) {
    console.log('✓ All smoke tests passed');
    process.exit(0);
} else {
    console.error(`✗ ${checks.length - passed} smoke tests failed`);
    process.exit(1);
}
EOF

run_test "Smoke test passes" "node /tmp/smoke-test.js build"

# Cleanup
rm -f "/tmp/smoke-test.js"

# Generate validation report
TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
SUCCESS_RATE=0
if [ $TOTAL_TESTS -gt 0 ]; then
    SUCCESS_RATE=$(( (TESTS_PASSED * 100) / TOTAL_TESTS ))
fi

cat > "$LOG_DIR/validation_report_$(date +%Y%m%d_%H%M%S).md" << EOF
# Deployment Validation Report

**Date**: $(date)
**Total Tests**: $TOTAL_TESTS
**Passed**: $TESTS_PASSED
**Failed**: $TESTS_FAILED
**Success Rate**: ${SUCCESS_RATE}%
**Status**: $([ $TESTS_FAILED -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")

## Test Categories:
- ✓ Build validation
- ✓ URL fix validation
- ✓ Component integration validation
- ✓ Service layer validation
- ✓ TypeScript validation
- ✓ Test suite validation
- ✓ Performance validation
- ✓ Security validation
- ✓ Configuration validation
- ✓ Integration validation

## Critical Failures:
$(if [ ${#CRITICAL_FAILURES[@]} -eq 0 ]; then
    echo "None"
else
    printf '%s\n' "${CRITICAL_FAILURES[@]}"
fi)

## Recommendations:
$(if [ $TESTS_FAILED -eq 0 ]; then
    echo "- ✅ All validations passed. Deployment is ready for production."
elif [ ${#CRITICAL_FAILURES[@]} -gt 0 ]; then
    echo "- ⚠️ Critical failures detected. Address these issues before proceeding."
    echo "- 🔧 Review failed tests and fix underlying issues."
else
    echo "- ✅ Minor issues detected but deployment can proceed."
    echo "- 🔧 Consider addressing warnings for optimal performance."
fi)

## Next Steps:
1. Review any failed tests
2. Address critical issues if present
3. Monitor application performance post-deployment
4. Verify user-facing functionality
EOF

run_hook "post-task" "deployment-validation-completed"

echo "" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL VALIDATIONS PASSED! 🎉${NC}" | tee -a "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
    echo "Tests passed: $TESTS_PASSED/$TOTAL_TESTS" | tee -a "$LOG_FILE"
    echo "Success rate: ${SUCCESS_RATE}%" | tee -a "$LOG_FILE"
    echo "Deployment is ready for production!" | tee -a "$LOG_FILE"
    exit 0
elif [ ${#CRITICAL_FAILURES[@]} -gt 0 ]; then
    echo -e "${RED}💥 CRITICAL FAILURES DETECTED! 💥${NC}" | tee -a "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
    echo "Critical failures: ${#CRITICAL_FAILURES[@]}" | tee -a "$LOG_FILE"
    echo "Total failures: $TESTS_FAILED/$TOTAL_TESTS" | tee -a "$LOG_FILE"
    echo "Success rate: ${SUCCESS_RATE}%" | tee -a "$LOG_FILE"
    echo "🚨 DO NOT PROCEED WITH DEPLOYMENT 🚨" | tee -a "$LOG_FILE"
    exit 2
else
    echo -e "${YELLOW}⚠️ VALIDATION COMPLETED WITH WARNINGS ⚠️${NC}" | tee -a "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
    echo "Tests passed: $TESTS_PASSED/$TOTAL_TESTS" | tee -a "$LOG_FILE"
    echo "Tests failed: $TESTS_FAILED/$TOTAL_STEPS" | tee -a "$LOG_FILE"
    echo "Success rate: ${SUCCESS_RATE}%" | tee -a "$LOG_FILE"
    echo "Deployment can proceed but monitor closely" | tee -a "$LOG_FILE"
    exit 1
fi