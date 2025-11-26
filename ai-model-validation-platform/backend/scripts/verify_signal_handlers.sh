#!/bin/bash
#
# Signal Handlers Verification Script
# Verifies that signal handlers are properly installed and functional
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "════════════════════════════════════════════════════════════════"
echo "  Signal Handlers Verification"
echo "════════════════════════════════════════════════════════════════"
echo

cd "$BACKEND_DIR"

# Check if required files exist
echo "1. Checking file existence..."
files=(
    "src/utils/signal_handlers.py"
    "tests/utils/test_signal_handlers.py"
    "scripts/test_signal_handlers.py"
    "docs/CRITICAL_FIXES_CONSOLIDATED_REPORT.md"
    "docs/SIGNAL_HANDLERS_IMPLEMENTATION_SUMMARY.md"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✓ $file exists"
    else
        echo "   ✗ $file NOT FOUND"
        exit 1
    fi
done
echo

# Check Python syntax
echo "2. Checking Python syntax..."
if python3 -m py_compile src/utils/signal_handlers.py 2>/dev/null; then
    echo "   ✓ signal_handlers.py syntax valid"
else
    echo "   ✗ signal_handlers.py syntax error"
    exit 1
fi

if python3 -m py_compile tests/utils/test_signal_handlers.py 2>/dev/null; then
    echo "   ✓ test_signal_handlers.py syntax valid"
else
    echo "   ✗ test_signal_handlers.py syntax error"
    exit 1
fi
echo

# Check for required imports in main.py
echo "3. Checking main.py integration..."
if grep -q "from src.utils.signal_handlers import GracefulShutdown" main.py; then
    echo "   ✓ Signal handlers imported in main.py"
else
    echo "   ✗ Signal handlers NOT imported in main.py"
    exit 1
fi

if grep -q "shutdown_handler.install_handlers()" main.py; then
    echo "   ✓ Signal handlers installed in main.py"
else
    echo "   ✗ Signal handlers NOT installed in main.py"
    exit 1
fi
echo

# Check for cleanup method in LabJack monitor
echo "4. Checking LabJack monitor cleanup..."
if grep -q "def cleanup(self)" services/dedicated_labjack_monitor.py; then
    echo "   ✓ Cleanup method exists in dedicated_labjack_monitor.py"
else
    echo "   ✗ Cleanup method NOT FOUND in dedicated_labjack_monitor.py"
    exit 1
fi
echo

# Run quick tests
echo "5. Running quick tests..."
if python3 scripts/test_signal_handlers.py 2>&1 | grep -q "All tests passed"; then
    echo "   ✓ All tests passed"
else
    echo "   ✗ Tests failed"
    exit 1
fi
echo

# Check documentation
echo "6. Checking documentation..."
if grep -q "Signal Handlers Implementation" docs/CRITICAL_FIXES_CONSOLIDATED_REPORT.md; then
    echo "   ✓ Documentation complete"
else
    echo "   ✗ Documentation incomplete"
    exit 1
fi
echo

# Summary
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ ALL VERIFICATIONS PASSED"
echo "════════════════════════════════════════════════════════════════"
echo
echo "Signal handlers are properly installed and functional."
echo
echo "Next steps:"
echo "  1. Start application: uvicorn main:app --reload"
echo "  2. Check logs for: '✅ Signal handlers installed'"
echo "  3. Test with: kill -TERM <pid> or Ctrl+C"
echo "  4. Verify cleanup in logs"
echo
