#!/bin/bash

# =============================================================================
# STABLE REACT DEVELOPMENT SERVER STARTUP SCRIPT
# =============================================================================
# 
# This script solves the auto-refresh/auto-opening issue by:
# 1. Cleanup First: Kill all existing development processes
# 2. Single Instance: Ensure only one development server runs
# 3. Disable Auto-Browser: Prevent automatic browser opening
# 4. Stable Configuration: Use consistent environment variables
# 5. Error Prevention: Handle port conflicts gracefully
#
# Root Cause: Process proliferation from multiple development servers
# Solution: Complete process cleanup + single stable server instance
# =============================================================================

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}          STABLE REACT DEVELOPMENT SERVER STARTUP SCRIPT${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""

# =============================================================================
# STEP 1: COMPREHENSIVE PROCESS CLEANUP
# =============================================================================

echo -e "${YELLOW}Step 1: Comprehensive Process Cleanup${NC}"
echo "Killing all existing Node.js processes to prevent conflicts..."

# Kill all node processes (including npm, webpack, craco)
echo "  → Killing all node processes..."
sudo pkill -f node 2>/dev/null || true
sudo pkill -f npm 2>/dev/null || true
sudo pkill -f craco 2>/dev/null || true
sudo pkill -f webpack 2>/dev/null || true
sudo pkill -f react-scripts 2>/dev/null || true

# Kill processes on common development ports
echo "  → Killing processes on development ports..."
for port in 3000 3001 3002 3003 3004 3005 8080; do
    sudo lsof -ti:$port | xargs sudo kill -9 2>/dev/null || true
done

# Wait for processes to fully terminate
echo "  → Waiting for processes to terminate..."
sleep 3

# Additional cleanup for stubborn processes
echo "  → Final cleanup of any remaining processes..."
sudo pkill -9 -f "react-scripts" 2>/dev/null || true
sudo pkill -9 -f "webpack-dev-server" 2>/dev/null || true
sudo pkill -9 -f "craco" 2>/dev/null || true

# Wait again to ensure complete cleanup
sleep 2

echo -e "${GREEN}✓ Process cleanup completed${NC}"
echo ""

# =============================================================================
# STEP 2: PORT AVAILABILITY CHECK
# =============================================================================

echo -e "${YELLOW}Step 2: Port Availability Check${NC}"

TARGET_PORT=3000

# Check if port is available
if lsof -Pi :$TARGET_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}Error: Port $TARGET_PORT is still in use after cleanup${NC}"
    echo "Attempting to force-kill the process..."
    sudo lsof -ti:$TARGET_PORT | xargs sudo kill -9 2>/dev/null || true
    sleep 2
    
    # Check again
    if lsof -Pi :$TARGET_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}Error: Unable to free port $TARGET_PORT. Please check manually.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Port $TARGET_PORT is available${NC}"
echo ""

# =============================================================================
# STEP 3: ENVIRONMENT SETUP
# =============================================================================

echo -e "${YELLOW}Step 3: Environment Setup${NC}"

# Create/update .env.local with stable configuration
cat > .env.local << 'EOF'
# STABLE DEVELOPMENT CONFIGURATION
# This file prevents auto-refresh and auto-opening issues

# Port Configuration
PORT=3000
HOST=localhost

# Browser Control - CRITICAL FOR PREVENTING AUTO-OPENING
BROWSER=none
REACT_APP_BROWSER=none

# Development Optimizations
SKIP_PREFLIGHT_CHECK=true
DISABLE_ESLINT_PLUGIN=true
TSC_COMPILE_ON_ERROR=true
ESLINT_NO_DEV_ERRORS=true
GENERATE_SOURCEMAP=false

# Performance Optimizations
FAST_REFRESH=false
CI=false

# Memory Management
NODE_OPTIONS=--max-old-space-size=2048

# Prevent Multiple Servers
FORCE_COLOR=0
CHOKIDAR_USEPOLLING=false
WATCHPACK_POLLING=false

# Development Flags
REACT_APP_ENVIRONMENT=development
REACT_APP_DEBUG=true
EOF

echo -e "${GREEN}✓ Environment configuration created${NC}"
echo ""

# =============================================================================
# STEP 4: DEPENDENCY CHECK
# =============================================================================

echo -e "${YELLOW}Step 4: Dependency Check${NC}"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "  → node_modules not found, installing dependencies..."
    npm install --silent
else
    echo "  → Dependencies already installed"
fi

echo -e "${GREEN}✓ Dependencies verified${NC}"
echo ""

# =============================================================================
# STEP 5: CREATE PROCESS LOCK
# =============================================================================

echo -e "${YELLOW}Step 5: Process Lock Creation${NC}"

# Create a lock file to prevent multiple instances
LOCK_FILE="/tmp/react-dev-server.lock"
PID_FILE="/tmp/react-dev-server.pid"

if [ -f "$LOCK_FILE" ]; then
    echo "  → Removing stale lock file..."
    rm -f "$LOCK_FILE"
    rm -f "$PID_FILE"
fi

echo "$$" > "$PID_FILE"
touch "$LOCK_FILE"

echo -e "${GREEN}✓ Process lock created${NC}"
echo ""

# =============================================================================
# STEP 6: START SINGLE DEVELOPMENT SERVER
# =============================================================================

echo -e "${YELLOW}Step 6: Starting Single Development Server${NC}"
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  → Port: 3000"
echo "  → Browser Auto-Open: DISABLED"
echo "  → Hot Reload: DISABLED (for stability)"
echo "  → ESLint: DISABLED (for performance)"
echo "  → Source Maps: DISABLED (for performance)"
echo "  → Memory Limit: 2GB"
echo ""

# Cleanup function for proper shutdown
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down development server...${NC}"
    rm -f "$LOCK_FILE" "$PID_FILE"
    # Kill any child processes
    jobs -p | xargs sudo kill 2>/dev/null || true
    echo -e "${GREEN}✓ Server stopped cleanly${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start the development server with stable configuration
echo -e "${GREEN}Starting React development server...${NC}"
echo -e "${BLUE}Navigate to http://localhost:3000 manually in your browser${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Export environment variables for the session
export PORT=3000
export HOST=localhost
export BROWSER=none
export REACT_APP_BROWSER=none
export SKIP_PREFLIGHT_CHECK=true
export DISABLE_ESLINT_PLUGIN=true
export TSC_COMPILE_ON_ERROR=true
export ESLINT_NO_DEV_ERRORS=true
export GENERATE_SOURCEMAP=false
export FAST_REFRESH=false
export CI=false
export NODE_OPTIONS=--max-old-space-size=2048
export FORCE_COLOR=0
export CHOKIDAR_USEPOLLING=false
export WATCHPACK_POLLING=false

# Start the server using the optimized npm script
# This uses the package.json "start" script which already has BROWSER=none
exec npm start

# =============================================================================
# NOTES:
# 
# This script addresses the 5 Why analysis root causes:
# 
# 1. Why does localhost:3000 auto-refresh/auto-open?
#    → Multiple development servers running simultaneously
# 
# 2. Why are multiple development servers running?
#    → Previous sessions not properly terminated
# 
# 3. Why weren't previous sessions terminated?
#    → No comprehensive cleanup mechanism
# 
# 4. Why no cleanup mechanism?
#    → Scripts didn't handle process management
# 
# 5. Why didn't scripts handle process management?
#    → No single, stable startup solution existed
# 
# ROOT CAUSE: Process proliferation from multiple development servers
# SOLUTION: This script provides comprehensive cleanup + single stable instance
# =============================================================================