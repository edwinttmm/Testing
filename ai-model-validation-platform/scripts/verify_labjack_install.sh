#!/bin/bash
# LabJack Installation Verification Script
# Checks system-level and Python-level LabJack LJM installation

set -e

echo "============================================"
echo "  LabJack LJM Installation Verification"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
ALL_PASSED=true

# Function to print status
print_status() {
    local status=$1
    local message=$2

    if [ "$status" == "PASS" ]; then
        echo -e "${GREEN}✅ PASS${NC}: $message"
    elif [ "$status" == "FAIL" ]; then
        echo -e "${RED}❌ FAIL${NC}: $message"
        ALL_PASSED=false
    elif [ "$status" == "WARN" ]; then
        echo -e "${YELLOW}⚠️  WARN${NC}: $message"
    else
        echo -e "ℹ️  INFO: $message"
    fi
}

echo "=== Step 1: System Architecture ==="
ARCH=$(uname -m)
if [ "$ARCH" == "x86_64" ]; then
    print_status "PASS" "Architecture: $ARCH (compatible)"
else
    print_status "FAIL" "Architecture: $ARCH (x86_64 required)"
fi
echo ""

echo "=== Step 2: LabJack Libraries ==="
if [ -f "/usr/local/lib/libLabJackM.so" ]; then
    print_status "PASS" "libLabJackM.so found in /usr/local/lib"

    # Check library version
    if command -v strings &> /dev/null; then
        LIB_VERSION=$(strings /usr/local/lib/libLabJackM.so | grep -oP '(?<=LJM_LIBRARY_VERSION )\d+\.\d+\.\d+' | head -1)
        if [ -n "$LIB_VERSION" ]; then
            print_status "INFO" "LJM Library version: $LIB_VERSION"
        fi
    fi
else
    print_status "FAIL" "libLabJackM.so NOT found in /usr/local/lib"
    print_status "INFO" "Run: sudo dpkg -i labjack_ljm.deb"
fi
echo ""

echo "=== Step 3: LabJack Headers ==="
if [ -f "/usr/local/include/LabJackM.h" ]; then
    print_status "PASS" "LabJackM.h found in /usr/local/include"
else
    print_status "FAIL" "LabJackM.h NOT found"
fi
echo ""

echo "=== Step 4: Library Loader Cache ==="
if ldconfig -p | grep -q "libLabJackM.so"; then
    LIB_PATH=$(ldconfig -p | grep libLabJackM.so | head -1 | awk '{print $NF}')
    print_status "PASS" "Library registered in ldconfig: $LIB_PATH"
else
    print_status "WARN" "Library not in ldconfig cache"
    print_status "INFO" "Run: sudo ldconfig"
fi
echo ""

echo "=== Step 5: udev Rules ==="
if [ -f "/etc/udev/rules.d/99-labjack.rules" ]; then
    print_status "PASS" "udev rules file exists"

    # Check if rules contain LabJack vendor ID
    if grep -q "0cd5" /etc/udev/rules.d/99-labjack.rules; then
        print_status "PASS" "Rules contain LabJack vendor ID (0cd5)"
    else
        print_status "WARN" "Rules file exists but may be incomplete"
    fi
else
    print_status "WARN" "udev rules not found (USB permissions may fail)"
    print_status "INFO" "See installation guide for udev rules setup"
fi
echo ""

echo "=== Step 6: USB Device Detection ==="
if command -v lsusb &> /dev/null; then
    if lsusb | grep -qi "labjack"; then
        DEVICE_INFO=$(lsusb | grep -i labjack)
        print_status "PASS" "LabJack USB device detected: $DEVICE_INFO"
    else
        print_status "WARN" "No LabJack USB device found"
        print_status "INFO" "Check USB connection or configure network access"
        print_status "INFO" "For WSL2: Use 'usbipd attach --wsl' in Windows"
    fi
else
    print_status "WARN" "lsusb not available (install: sudo apt-get install usbutils)"
fi
echo ""

echo "=== Step 7: Python Virtual Environment ==="
BACKEND_DIR="/home/rigade/Testing/ai-model-validation-platform/backend"
VENV_DIR="$BACKEND_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    print_status "PASS" "Virtual environment found: $VENV_DIR"

    # Activate venv and check Python package
    source "$VENV_DIR/bin/activate"

    if command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1)
        print_status "INFO" "Python version: $PYTHON_VERSION"
    fi

    echo ""
    echo "=== Step 8: Python Package Installation ==="
    if python -c "import labjack.ljm" 2>/dev/null; then
        print_status "PASS" "labjack-ljm Python package installed"

        # Get package version
        PKG_VERSION=$(pip show labjack-ljm 2>/dev/null | grep Version | awk '{print $2}')
        if [ -n "$PKG_VERSION" ]; then
            print_status "INFO" "Package version: $PKG_VERSION"
        fi

        # Get library version from Python
        LIB_VER=$(python -c "from labjack import ljm; print(ljm.constants.LIBRARY_VERSION)" 2>/dev/null || echo "unknown")
        if [ "$LIB_VER" != "unknown" ]; then
            print_status "INFO" "Python reports LJM version: $LIB_VER"
        fi
    else
        print_status "FAIL" "labjack-ljm Python package NOT installed"
        print_status "INFO" "Run: pip install labjack-ljm"
    fi

    echo ""
    echo "=== Step 9: Python Import Test ==="
    if python -c "from labjack import ljm; print('Import successful')" 2>/dev/null | grep -q "successful"; then
        print_status "PASS" "Python can import labjack.ljm module"
    else
        print_status "FAIL" "Python import failed"
        print_status "INFO" "Check library path or reinstall package"
    fi

    echo ""
    echo "=== Step 10: Device Connection Test ==="
    CONNECTION_TEST=$(python << 'EOF' 2>&1
import sys
try:
    from labjack import ljm
    try:
        handle = ljm.openS("ANY", "ANY", "ANY")
        info = ljm.getHandleInfo(handle)
        print(f"CONNECTED|{info[0]}|{info[1]}|{info[2]}")
        ljm.close(handle)
    except ljm.LJMError as e:
        print(f"LJMERROR|{e}")
    except Exception as e:
        print(f"ERROR|{e}")
except ImportError as e:
    print(f"IMPORTERROR|{e}")
EOF
    )

    if echo "$CONNECTION_TEST" | grep -q "CONNECTED"; then
        DEVICE_TYPE=$(echo "$CONNECTION_TEST" | cut -d'|' -f2)
        CONN_TYPE=$(echo "$CONNECTION_TEST" | cut -d'|' -f3)
        SERIAL=$(echo "$CONNECTION_TEST" | cut -d'|' -f4)
        print_status "PASS" "Successfully connected to LabJack"
        print_status "INFO" "Device Type: $DEVICE_TYPE, Connection: $CONN_TYPE, Serial: $SERIAL"
    elif echo "$CONNECTION_TEST" | grep -q "LJMERROR"; then
        ERROR_MSG=$(echo "$CONNECTION_TEST" | cut -d'|' -f2)
        print_status "WARN" "LabJack library works but device not found"
        print_status "INFO" "Error: $ERROR_MSG"
        print_status "INFO" "Check USB connection or configure network access"
    else
        ERROR_MSG=$(echo "$CONNECTION_TEST" | cut -d'|' -f2-)
        print_status "FAIL" "Connection test failed: $ERROR_MSG"
    fi

    deactivate 2>/dev/null || true

else
    print_status "FAIL" "Backend virtual environment not found: $VENV_DIR"
    print_status "INFO" "Create with: python3 -m venv venv"
fi
echo ""

echo "============================================"
if [ "$ALL_PASSED" = true ]; then
    echo -e "${GREEN}✅ All critical checks PASSED${NC}"
    echo ""
    echo "LabJack LJM is properly installed and ready for use!"
    echo ""
    echo "Next steps:"
    echo "  1. Start backend: cd $BACKEND_DIR && source venv/bin/activate && uvicorn main:app --reload"
    echo "  2. Open frontend: http://localhost:3000/hil-test"
    echo "  3. Check LabJack status indicator (should show 'Connected')"
    echo "  4. Run a test session to verify detection events"
    exit 0
else
    echo -e "${RED}❌ Some checks FAILED${NC}"
    echo ""
    echo "Review the failures above and refer to the installation guide:"
    echo "  $BACKEND_DIR/../docs/setup/LABJACK_INSTALLATION_GUIDE.md"
    echo ""
    echo "Common fixes:"
    echo "  - Missing library: sudo dpkg -i labjack_ljm.deb"
    echo "  - Library cache: sudo ldconfig"
    echo "  - Python package: source venv/bin/activate && pip install labjack-ljm"
    echo "  - USB permissions: Check udev rules and WSL USB passthrough"
    exit 1
fi
