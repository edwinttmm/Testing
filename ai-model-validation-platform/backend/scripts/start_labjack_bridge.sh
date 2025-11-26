#!/bin/bash
#
# Start LabJack HTTP Bridge Service
# This script starts the bridge service on port 8080
#

echo "🌉 Starting LabJack HTTP Bridge Service"
echo "========================================"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found"
    exit 1
fi

# Check if script exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_SCRIPT="$SCRIPT_DIR/labjack_bridge_http.py"

if [ ! -f "$BRIDGE_SCRIPT" ]; then
    echo "❌ Error: Bridge script not found at $BRIDGE_SCRIPT"
    exit 1
fi

# Make script executable
chmod +x "$BRIDGE_SCRIPT"

# Check if port 8080 is already in use
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Warning: Port 8080 is already in use"
    echo "    Checking what's running..."
    lsof -i :8080
    echo ""
    read -p "Kill existing process and restart? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔪 Killing process on port 8080..."
        lsof -ti:8080 | xargs kill -9
        sleep 1
    else
        echo "❌ Exiting. Please stop the existing service first."
        exit 1
    fi
fi

# Load environment variables if .env exists
ENV_FILE="$SCRIPT_DIR/../.env"
if [ -f "$ENV_FILE" ]; then
    echo "📋 Loading environment from $ENV_FILE"
    export $(cat "$ENV_FILE" | grep -v '^#' | xargs)
fi

# Get host and port from environment or use defaults
BRIDGE_HOST="${LABJACK_BRIDGE_HOST:-0.0.0.0}"
BRIDGE_PORT="${LABJACK_BRIDGE_PORT:-8080}"

echo ""
echo "🚀 Starting bridge service..."
echo "   Host: $BRIDGE_HOST"
echo "   Port: $BRIDGE_PORT"
echo "   Script: $BRIDGE_SCRIPT"
echo ""
echo "📡 To test the bridge:"
echo "   curl http://localhost:$BRIDGE_PORT/status"
echo "   curl http://localhost:$BRIDGE_PORT/health"
echo ""
echo "⏹️  To stop: Press Ctrl+C"
echo "========================================"
echo ""

# Start the bridge service
python3 "$BRIDGE_SCRIPT" --host "$BRIDGE_HOST" --port "$BRIDGE_PORT"
