#!/bin/bash
#
# Test LabJack Bridge Connection
# Verifies that the bridge service is running and responding correctly
#

echo "🧪 Testing LabJack Bridge Connection"
echo "====================================="

# Get configuration from environment or use defaults
BRIDGE_HOST="${LABJACK_BRIDGE_HOST:-localhost}"
BRIDGE_PORT="${LABJACK_BRIDGE_PORT:-8080}"
BRIDGE_URL="http://${BRIDGE_HOST}:${BRIDGE_PORT}"

echo ""
echo "🔍 Testing bridge at: $BRIDGE_URL"
echo ""

# Test 1: Check if port is open
echo "1️⃣ Checking if port $BRIDGE_PORT is listening..."
if lsof -Pi :$BRIDGE_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✅ Port $BRIDGE_PORT is open"
    lsof -i :$BRIDGE_PORT | grep LISTEN
else
    echo "❌ Port $BRIDGE_PORT is NOT listening"
    echo ""
    echo "💡 Start the bridge service first:"
    echo "   ./scripts/start_labjack_bridge.sh"
    exit 1
fi

echo ""

# Test 2: Health check
echo "2️⃣ Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "${BRIDGE_URL}/health")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n 1)
HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Health check passed (HTTP $HTTP_CODE)"
    echo "$HEALTH_BODY" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_BODY"
else
    echo "❌ Health check failed (HTTP $HTTP_CODE)"
    echo "$HEALTH_BODY"
fi

echo ""

# Test 3: Status endpoint
echo "3️⃣ Testing status endpoint..."
STATUS_RESPONSE=$(curl -s -w "\n%{http_code}" "${BRIDGE_URL}/status")
HTTP_CODE=$(echo "$STATUS_RESPONSE" | tail -n 1)
STATUS_BODY=$(echo "$STATUS_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Status endpoint responded (HTTP $HTTP_CODE)"
    echo "$STATUS_BODY" | python3 -m json.tool 2>/dev/null || echo "$STATUS_BODY"
else
    echo "❌ Status endpoint failed (HTTP $HTTP_CODE)"
    echo "$STATUS_BODY"
fi

echo ""

# Test 4: Device info
echo "4️⃣ Testing device-info endpoint..."
INFO_RESPONSE=$(curl -s -w "\n%{http_code}" "${BRIDGE_URL}/device-info")
HTTP_CODE=$(echo "$INFO_RESPONSE" | tail -n 1)
INFO_BODY=$(echo "$INFO_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Device info retrieved (HTTP $HTTP_CODE)"
    echo "$INFO_BODY" | python3 -m json.tool 2>/dev/null || echo "$INFO_BODY"
else
    echo "❌ Device info failed (HTTP $HTTP_CODE)"
    echo "$INFO_BODY"
fi

echo ""
echo "====================================="
echo "✅ Bridge connection tests complete!"
echo ""
echo "🔗 Bridge URL: $BRIDGE_URL"
echo "📊 View logs: tail -f labjack_bridge_http.log"
echo ""
echo "💡 Next steps:"
echo "   1. Update backend .env with bridge URL"
echo "   2. Restart backend: uvicorn main:app --reload"
echo "   3. Run a test session in the frontend"
echo "====================================="
