#!/bin/bash
# Activation and Startup Script for AI Model Validation Platform Backend
#
# This script:
# 1. Activates the virtual environment
# 2. Verifies all dependencies (including scipy)
# 3. Optionally starts the backend service
#
# Usage:
#   ./scripts/activate_and_run.sh              # Check dependencies only
#   ./scripts/activate_and_run.sh --start      # Start backend service
#   ./scripts/activate_and_run.sh --verify     # Run verification script

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "======================================================================="
echo "AI Model Validation Platform - Backend Activation"
echo "======================================================================="
echo ""

# Check if venv exists
if [ ! -d "$BACKEND_DIR/venv" ]; then
    echo -e "${RED}✗ Virtual environment not found at: $BACKEND_DIR/venv${NC}"
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv "$BACKEND_DIR/venv"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$BACKEND_DIR/venv/bin/activate"

# Verify activation
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}✗ Failed to activate virtual environment${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo "  Path: $VIRTUAL_ENV"
echo ""

# Run dependency check
echo "Running dependency checks..."
echo "-----------------------------------------------------------------------"
python3 "$BACKEND_DIR/scripts/startup_check.py"
CHECK_STATUS=$?

if [ $CHECK_STATUS -ne 0 ]; then
    echo ""
    echo -e "${RED}✗ Dependency checks failed${NC}"
    echo ""
    echo "Would you like to install missing dependencies? (y/n)"
    read -r INSTALL_DEPS

    if [ "$INSTALL_DEPS" = "y" ]; then
        if [ -f "$BACKEND_DIR/requirements.txt" ]; then
            echo "Installing dependencies from requirements.txt..."
            pip install -r "$BACKEND_DIR/requirements.txt"
            echo ""
            echo "Re-running dependency checks..."
            python3 "$BACKEND_DIR/scripts/startup_check.py"
            CHECK_STATUS=$?
        else
            echo -e "${YELLOW}⚠ requirements.txt not found, installing scipy manually${NC}"
            pip install scipy numpy sqlalchemy fastapi
            echo ""
            echo "Re-running dependency checks..."
            python3 "$BACKEND_DIR/scripts/startup_check.py"
            CHECK_STATUS=$?
        fi
    fi

    if [ $CHECK_STATUS -ne 0 ]; then
        echo ""
        echo -e "${RED}✗ Unable to resolve all dependencies${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}✓ All dependencies verified${NC}"
echo ""

# Parse command line arguments
START_SERVICE=false
RUN_VERIFY=false

for arg in "$@"; do
    case $arg in
        --start)
            START_SERVICE=true
            ;;
        --verify)
            RUN_VERIFY=true
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --start      Start the backend service"
            echo "  --verify     Run scipy verification script"
            echo "  --help       Show this help message"
            echo ""
            exit 0
            ;;
    esac
done

# Run verification if requested
if [ "$RUN_VERIFY" = true ]; then
    echo "Running scipy verification..."
    echo "-----------------------------------------------------------------------"
    python3 "$BACKEND_DIR/scripts/verify_scipy.py"
    echo ""
fi

# Start service if requested
if [ "$START_SERVICE" = true ]; then
    echo "======================================================================="
    echo "Starting Backend Service"
    echo "======================================================================="
    echo ""

    # Check if app/main.py or similar exists
    if [ -f "$BACKEND_DIR/app/main.py" ]; then
        echo "Starting FastAPI server..."
        cd "$BACKEND_DIR"
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    elif [ -f "$BACKEND_DIR/main.py" ]; then
        echo "Starting application..."
        cd "$BACKEND_DIR"
        python3 main.py
    else
        echo -e "${YELLOW}⚠ Main application file not found${NC}"
        echo "  Tried: app/main.py, main.py"
        echo ""
        echo "To start manually:"
        echo "  cd $BACKEND_DIR"
        echo "  python3 <your_main_file>.py"
    fi
else
    echo "======================================================================="
    echo "Environment Ready"
    echo "======================================================================="
    echo ""
    echo "Virtual environment is activated. You can now:"
    echo ""
    echo "  1. Start the backend service:"
    echo "     cd $BACKEND_DIR"
    echo "     python3 app/main.py"
    echo ""
    echo "  2. Run tests:"
    echo "     pytest tests/"
    echo ""
    echo "  3. Run scipy verification:"
    echo "     python3 scripts/verify_scipy.py"
    echo ""
    echo "Or run this script with --start to automatically start the service:"
    echo "  ./scripts/activate_and_run.sh --start"
    echo ""
fi
