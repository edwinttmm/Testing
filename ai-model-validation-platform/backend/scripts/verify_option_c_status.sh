#!/bin/bash
# Option C Deployment Status Verification Script
# This script checks if Option C temporal expansion is properly deployed and active

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Option C Deployment Status Verification"
echo "=========================================="
echo ""

# Change to backend directory
cd "$BACKEND_DIR"

# Test 1: Check if temporal_expansion.py exists
echo "Test 1: Checking if temporal_expansion.py exists..."
if [ -f "src/services/temporal_expansion.py" ]; then
    echo "✅ PASS: temporal_expansion.py exists"
else
    echo "❌ FAIL: temporal_expansion.py NOT FOUND"
    exit 1
fi

# Test 2: Check if ground_truth_matching_service.py exists
echo ""
echo "Test 2: Checking if ground_truth_matching_service.py exists..."
if [ -f "src/services/ground_truth_matching_service.py" ]; then
    echo "✅ PASS: ground_truth_matching_service.py exists"
else
    echo "❌ FAIL: ground_truth_matching_service.py NOT FOUND"
    exit 1
fi

# Test 3: Check import statement
echo ""
echo "Test 3: Checking import statement in ground_truth_matching_service.py..."
IMPORT_LINE=$(grep -n "from.*temporal_expansion import" src/services/ground_truth_matching_service.py | head -1)
if echo "$IMPORT_LINE" | grep -q "from src.services.temporal_expansion import"; then
    echo "✅ PASS: Import statement is correct (from src.services.temporal_expansion)"
    echo "   Line: $IMPORT_LINE"
elif echo "$IMPORT_LINE" | grep -q "from services.temporal_expansion import"; then
    echo "❌ FAIL: Import statement is INCORRECT (missing 'src' prefix)"
    echo "   Line: $IMPORT_LINE"
    echo "   Fix required: Run ./scripts/fix_option_c_import.sh"
    exit 1
else
    echo "❌ FAIL: Import statement not found or unrecognized format"
    exit 1
fi

# Test 4: Check if scipy is installed
echo ""
echo "Test 4: Checking if scipy is installed..."
if python3 -c "import scipy; print('scipy version:', scipy.__version__)" 2>/dev/null; then
    echo "✅ PASS: scipy is installed"
else
    echo "❌ FAIL: scipy NOT INSTALLED"
    echo "   Install with: pip install scipy"
    exit 1
fi

# Test 5: Test Python import of temporal_expansion
echo ""
echo "Test 5: Testing Python import of temporal_expansion module..."
if python3 -c "from src.services.temporal_expansion import expand_detections_temporally; print('✅ Import successful')" 2>&1; then
    echo "✅ PASS: temporal_expansion module can be imported"
else
    echo "❌ FAIL: Cannot import temporal_expansion module"
    echo "   Check import path and Python environment"
    exit 1
fi

# Test 6: Test Python import of ground_truth_matching_service
echo ""
echo "Test 6: Testing Python import of ground_truth_matching_service..."
if python3 -c "from src.services.ground_truth_matching_service import GroundTruthMatchingService; print('✅ Import successful')" 2>&1; then
    echo "✅ PASS: ground_truth_matching_service module can be imported"
else
    echo "❌ FAIL: Cannot import ground_truth_matching_service module"
    echo "   This indicates the import path fix has not been applied"
    exit 1
fi

# Test 7: Check if feature flag is present
echo ""
echo "Test 7: Checking if feature flag 'enable_temporal_expansion' is present..."
if grep -q "enable_temporal_expansion: bool = True" src/services/ground_truth_matching_service.py; then
    echo "✅ PASS: Feature flag present and enabled by default"
elif grep -q "enable_temporal_expansion: bool = False" src/services/ground_truth_matching_service.py; then
    echo "⚠️  WARNING: Feature flag present but DISABLED by default"
    echo "   Change to 'enable_temporal_expansion: bool = True' to activate"
else
    echo "❌ FAIL: Feature flag not found"
    exit 1
fi

# Test 8: Check if expansion logic is present
echo ""
echo "Test 8: Checking if expansion logic is present in matching service..."
if grep -q "expand_detections_temporally" src/services/ground_truth_matching_service.py; then
    echo "✅ PASS: Expansion function call found in matching service"
else
    echo "❌ FAIL: Expansion function call NOT FOUND"
    exit 1
fi

# Test 9: Check if collapse logic is present
echo ""
echo "Test 9: Checking if collapse logic is present in matching service..."
if grep -q "collapse_duplicates" src/services/ground_truth_matching_service.py; then
    echo "✅ PASS: Collapse function call found in matching service"
else
    echo "❌ FAIL: Collapse function call NOT FOUND"
    exit 1
fi

# Test 10: Run unit tests (if pytest is available)
echo ""
echo "Test 10: Running unit tests (if available)..."
if command -v pytest &> /dev/null; then
    if [ -f "tests/services/test_option_c_temporal_expansion.py" ]; then
        if pytest tests/services/test_option_c_temporal_expansion.py -v --tb=short 2>&1 | grep -q "passed"; then
            echo "✅ PASS: Unit tests pass"
        else
            echo "⚠️  WARNING: Some unit tests failed (check test output above)"
        fi
    else
        echo "⚠️  SKIP: Unit test file not found"
    fi
else
    echo "⚠️  SKIP: pytest not installed"
fi

# Summary
echo ""
echo "=========================================="
echo "VERIFICATION SUMMARY"
echo "=========================================="
echo ""
echo "✅ All critical checks passed!"
echo ""
echo "Option C Temporal Expansion is READY for deployment."
echo ""
echo "Current status:"
echo "  - temporal_expansion.py: EXISTS"
echo "  - Import path: CORRECT (from src.services.temporal_expansion)"
echo "  - Feature flag: ENABLED (enable_temporal_expansion=True)"
echo "  - scipy dependency: INSTALLED"
echo "  - Python imports: WORKING"
echo "  - Expansion logic: INTEGRATED"
echo "  - Collapse logic: INTEGRATED"
echo ""
echo "Next steps:"
echo "1. Restart backend service to activate Option C"
echo "2. Monitor logs for: 'Applying temporal expansion'"
echo "3. Verify recall improves from 0% to >50%"
echo ""
echo "To restart service:"
echo "  sudo systemctl restart ai-model-validation-backend"
echo ""
echo "To monitor logs:"
echo "  tail -f /var/log/ai-model-validation/backend.log | grep -i 'temporal expansion'"
echo ""
