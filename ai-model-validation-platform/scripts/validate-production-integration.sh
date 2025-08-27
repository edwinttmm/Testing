#!/bin/bash

# Production Integration Validation Script
# Validates frontend-backend integration for external IP access

set -e

PRODUCTION_IP="155.138.239.131"
BACKEND_PORT="8000"
FRONTEND_PORT="3000"

echo "🚀 Production Integration Validation for IP: ${PRODUCTION_IP}"
echo "============================================================"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "pass" ]; then
        echo -e "${GREEN}✅ PASS${NC} - $message"
    elif [ "$status" = "fail" ]; then
        echo -e "${RED}❌ FAIL${NC} - $message"
    else
        echo -e "${YELLOW}⚠️  WARN${NC} - $message"
    fi
}

# 1. Validate Configuration Files
echo -e "\n📋 CONFIGURATION VALIDATION"
echo "------------------------------------------------------------"

# Check backend CORS configuration
if grep -q "155.138.239.131:3000" /home/user/Testing/ai-model-validation-platform/backend/config.py; then
    print_status "pass" "Backend CORS includes production IP"
else
    print_status "fail" "Backend CORS missing production IP"
fi

# Check frontend environment variables
if grep -q "REACT_APP_API_URL=http://155.138.239.131:8000" /home/user/Testing/ai-model-validation-platform/frontend/.env; then
    print_status "pass" "Frontend .env configured for production API"
else
    print_status "fail" "Frontend .env missing production API URL"
fi

# Check frontend production environment
if grep -q "REACT_APP_API_URL=http://155.138.239.131:8000" /home/user/Testing/ai-model-validation-platform/frontend/.env.production; then
    print_status "pass" "Frontend .env.production configured correctly"
else
    print_status "fail" "Frontend .env.production missing production configuration"
fi

# 2. Network Connectivity Tests
echo -e "\n🌐 NETWORK CONNECTIVITY TESTS"
echo "------------------------------------------------------------"

# Test backend accessibility
echo "Testing backend connectivity..."
if timeout 10 curl -f -s "http://${PRODUCTION_IP}:${BACKEND_PORT}/health" > /dev/null 2>&1; then
    print_status "pass" "Backend accessible on http://${PRODUCTION_IP}:${BACKEND_PORT}"
else
    print_status "fail" "Backend NOT accessible on http://${PRODUCTION_IP}:${BACKEND_PORT}"
    echo "         Note: Backend may not be running or not bound to external interface"
fi

# Test CORS preflight
echo "Testing CORS preflight..."
CORS_RESPONSE=$(timeout 10 curl -s -o /dev/null -w "%{http_code}" \
    -X OPTIONS \
    -H "Origin: http://${PRODUCTION_IP}:${FRONTEND_PORT}" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: Content-Type" \
    "http://${PRODUCTION_IP}:${BACKEND_PORT}/api/projects" 2>/dev/null || echo "timeout")

if [ "$CORS_RESPONSE" = "200" ] || [ "$CORS_RESPONSE" = "204" ]; then
    print_status "pass" "CORS preflight successful (HTTP $CORS_RESPONSE)"
elif [ "$CORS_RESPONSE" = "timeout" ]; then
    print_status "fail" "CORS preflight timed out"
else
    print_status "warn" "CORS preflight returned HTTP $CORS_RESPONSE"
fi

# 3. Configuration Summary
echo -e "\n📊 CONFIGURATION SUMMARY"
echo "------------------------------------------------------------"
echo "Backend URL:    http://${PRODUCTION_IP}:${BACKEND_PORT}"
echo "Frontend URL:   http://${PRODUCTION_IP}:${FRONTEND_PORT}"
echo "WebSocket URL:  ws://${PRODUCTION_IP}:${BACKEND_PORT}"

# 4. Deployment Instructions
echo -e "\n🚀 DEPLOYMENT INSTRUCTIONS"
echo "------------------------------------------------------------"
echo "1. Start Backend (ensure external binding):"
echo "   cd /home/user/Testing/ai-model-validation-platform/backend"
echo "   uvicorn main:app --host 0.0.0.0 --port ${BACKEND_PORT} --reload"
echo ""
echo "2. Start Frontend (ensure external binding):"
echo "   cd /home/user/Testing/ai-model-validation-platform/frontend"
echo "   REACT_APP_API_URL=http://${PRODUCTION_IP}:${BACKEND_PORT} npm start"
echo ""
echo "3. Access Application:"
echo "   Frontend: http://${PRODUCTION_IP}:${FRONTEND_PORT}"
echo "   Backend:  http://${PRODUCTION_IP}:${BACKEND_PORT}"

# 5. Troubleshooting
echo -e "\n🔧 TROUBLESHOOTING"
echo "------------------------------------------------------------"
echo "If backend is not accessible:"
echo "• Check if uvicorn is running: ps aux | grep uvicorn"
echo "• Check if port is listening: netstat -tlnp | grep :${BACKEND_PORT}"
echo "• Ensure --host 0.0.0.0 flag is used (not just localhost)"
echo "• Check firewall rules: ufw status"
echo ""
echo "If CORS errors occur:"
echo "• Verify CORS origins in backend/config.py"
echo "• Check browser DevTools Network tab for preflight requests"
echo "• Ensure both HTTP and HTTPS origins are included if needed"

echo -e "\n✅ Production integration validation complete!"