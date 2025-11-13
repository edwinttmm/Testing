#!/bin/bash
# Automated Test Runner Script for Timing Fixes Integration Tests

set -e  # Exit on error

echo "🚀 Starting Integration Test Suite for Timing Fixes"
echo "===================================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Install test dependencies
echo "📦 Installing test dependencies..."
python3 -m pip install -q pytest pytest-asyncio pytest-cov sqlalchemy

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run tests with coverage
echo ""
echo "🧪 Running integration tests with coverage..."
echo ""

python3 -m pytest tests/test_timing_fixes_integration.py \
    -v \
    --tb=short \
    --color=yes \
    -s \
    --cov=services \
    --cov=models \
    --cov-report=term-missing \
    --cov-report=html:tests/coverage_html \
    --cov-report=json:tests/coverage.json

# Check exit code
TEST_EXIT_CODE=$?

echo ""
echo "===================================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ ALL TESTS PASSED!"
    echo ""
    echo "📊 Coverage Report: tests/coverage_html/index.html"
    echo "📄 JSON Report: tests/coverage.json"
else
    echo "❌ TESTS FAILED (exit code: $TEST_EXIT_CODE)"
    exit $TEST_EXIT_CODE
fi

echo ""
echo "🎯 Test Summary:"
python3 -c "
import json
try:
    with open('tests/coverage.json', 'r') as f:
        data = json.load(f)
        total = data['totals']
        print(f'  Lines covered: {total[\"covered_lines\"]}/{total[\"num_statements\"]} ({total[\"percent_covered\"]:.1f}%)')
        print(f'  Missing lines: {total[\"missing_lines\"]}')

        if total['percent_covered'] >= 80:
            print('  ✅ Coverage target met (>80%)')
        else:
            print(f'  ⚠️  Coverage below target: {total[\"percent_covered\"]:.1f}% < 80%')
except Exception as e:
    print(f'  ⚠️  Could not parse coverage report: {e}')
"

exit 0
