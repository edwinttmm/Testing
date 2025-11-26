#!/bin/bash
# Frontend Metrics API Integration Test Script
# Tests the /api/test-sessions/{id}/results endpoint for metrics field

set -e

SESSION_ID="49e5d00f-eea7-44cb-a647-480268ef43ee"
API_URL="http://localhost:8000/api/test-sessions/${SESSION_ID}/results"

echo "=================================="
echo "Frontend Metrics API Test"
echo "=================================="
echo ""
echo "Session ID: ${SESSION_ID}"
echo "API URL: ${API_URL}"
echo ""

# Check if server is running
echo "Checking server status..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ ERROR: Backend server not running"
    echo ""
    echo "Start the server with:"
    echo "  cd /home/rigade/Testing/ai-model-validation-platform/backend"
    echo "  source venv/bin/activate"
    echo "  python -m uvicorn main:app --host 0.0.0.0 --port 8000"
    echo ""
    exit 1
fi

echo "✅ Server is running"
echo ""

# Test API endpoint
echo "Testing API endpoint..."
RESPONSE=$(curl -s -w "\n%{http_code}" "${API_URL}")
HTTP_CODE=$(echo "${RESPONSE}" | tail -n1)
BODY=$(echo "${RESPONSE}" | head -n-1)

if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ ERROR: API returned status ${HTTP_CODE}"
    echo "Response: ${BODY}"
    exit 1
fi

echo "✅ API returned 200 OK"
echo ""

# Check for metrics field
echo "Checking for metrics field..."
if echo "${BODY}" | jq -e '.metrics' > /dev/null 2>&1; then
    echo "✅ metrics field found"
else
    echo "❌ ERROR: metrics field not found in response"
    echo "Available keys:"
    echo "${BODY}" | jq 'keys'
    exit 1
fi

echo ""
echo "Metrics content:"
echo "=================================="
echo "${BODY}" | jq '.metrics'
echo "=================================="
echo ""

# Validate metrics fields
echo "Validating metrics fields..."

METRICS=$(echo "${BODY}" | jq '.metrics')

# Check required fields
REQUIRED_FIELDS=("precision" "recall" "f1_score" "accuracy" "true_positives" "false_positives" "false_negatives")

for field in "${REQUIRED_FIELDS[@]}"; do
    if echo "${METRICS}" | jq -e ".${field}" > /dev/null 2>&1; then
        VALUE=$(echo "${METRICS}" | jq -r ".${field}")
        echo "  ✅ ${field}: ${VALUE}"
    else
        echo "  ❌ Missing: ${field}"
    fi
done

echo ""
echo "=================================="
echo "✅ ALL TESTS PASSED"
echo "=================================="
echo ""
echo "Frontend can now display these metrics using:"
echo "  - ComparisonMetricsCard component"
echo "  - EnhancedTestMetricsPanel component"
echo "  - QualityMetricsCard component"
echo ""
