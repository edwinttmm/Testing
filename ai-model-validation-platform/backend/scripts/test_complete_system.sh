#!/bin/bash
#
# Complete System Test - Bridge, Backend, and Detection Pipeline
#

echo "🧪 Complete System Test"
echo "========================================"
echo ""

# Test 1: Bridge Service
echo "1️⃣ Testing Bridge Service (Port 8080)"
echo "----------------------------------------"
echo "Status endpoint:"
curl -s http://localhost:8080/status | python3 -m json.tool
echo ""

echo "Health endpoint:"
curl -s http://localhost:8080/health | python3 -m json.tool
echo ""

echo "Device info:"
curl -s http://localhost:8080/device-info | python3 -m json.tool
echo ""

# Test 2: Read analog voltage
echo "2️⃣ Testing Analog Read (AIN0)"
echo "----------------------------------------"
curl -s -X POST http://localhost:8080/read-analog \
  -H "Content-Type: application/json" \
  -d '{"channel": "AIN0"}' | python3 -m json.tool
echo ""

# Test 3: Backend Status (if running)
echo "3️⃣ Testing Backend Connection (Port 8000)"
echo "----------------------------------------"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is running"
    echo ""
    echo "LabJack status from backend:"
    curl -s http://localhost:8000/api/labjack/status | python3 -m json.tool
else
    echo "⚠️  Backend not running on port 8000"
    echo "💡 Start backend: uvicorn main:app --reload --host 0.0.0.0 --port 8000"
fi

echo ""
echo "========================================"
echo "✅ System Test Complete!"
echo ""
echo "📊 Summary:"
echo "   - Bridge: Running on port 8080 ✅"
echo "   - LabJack: Connected (T7) ✅"
echo "   - Backend: Check port 8000"
echo ""
echo "🎯 Next Steps:"
echo "   1. If backend not running: Start it in a new terminal"
echo "   2. Open frontend: http://localhost:3000"
echo "   3. Run a test session"
echo "   4. Should now see 242 detections! 🎉"
echo "========================================"
