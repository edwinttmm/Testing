#!/bin/bash
# LabJack Hardware Reconnection Script
# Run this after reconnecting LabJack T7 hardware

set -e

echo "🔌 LabJack Hardware Reconnection Script"
echo "========================================"

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Backend not running! Start with: ./scripts/start_hardware_mode.sh"
    exit 1
fi

echo "✅ Backend is running"

# Check USB connection
echo "🔍 Checking USB connection..."
if lsusb | grep -i "0cd5"; then
    echo "✅ LabJack T7 detected in USB!"
else
    echo "⚠️  LabJack T7 not detected in USB"
    echo "   Please ensure device is physically connected"
fi

# Try to initialize direct hardware connection
echo "🚀 Attempting direct hardware connection..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/signal-validation/labjack/initialize" \
     -H "Content-Type: application/json" \
     -d '{"force_mode": "direct"}')

if echo "$RESPONSE" | grep -q '"status":"success"'; then
    echo "✅ DIRECT HARDWARE CONNECTION SUCCESSFUL!"
else
    echo "⚠️  Direct connection failed, trying bridge mode..."
    
    # Try bridge mode
    BRIDGE_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/signal-validation/labjack/initialize" \
         -H "Content-Type: application/json" \
         -d '{"force_mode": "bridge"}')
    
    if echo "$BRIDGE_RESPONSE" | grep -q '"status":"success"'; then
        echo "✅ BRIDGE CONNECTION SUCCESSFUL!"
    else
        echo "❌ Both hardware and bridge connections failed"
        echo "   System will continue in mock mode"
    fi
fi

# Get final status
echo ""
echo "📊 Final LabJack Status:"
curl -s "http://localhost:8000/api/labjack/status" | python3 -m json.tool 2>/dev/null || \
curl -s "http://localhost:8000/api/labjack/status"

echo ""
echo "🎯 Status Check Complete!"
echo "   Backend running at: http://localhost:8000"
echo "   LabJack API: http://localhost:8000/api/labjack/status"
echo "   Health check: http://localhost:8000/health"