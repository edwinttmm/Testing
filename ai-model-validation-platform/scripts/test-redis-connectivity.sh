#!/bin/bash

# Redis Connectivity Testing Script
# Tests Redis authentication across all containers

set -e

echo "🔍 REDIS CONNECTIVITY TESTING"
echo "=============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REDIS_PASSWORD="${REDIS_PASSWORD:-secure_redis_password}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo -e "${BLUE}Configuration:${NC}"
echo "  Redis Host: ${REDIS_HOST}"
echo "  Redis Port: ${REDIS_PORT}"
echo "  Redis Password: ${REDIS_PASSWORD}"
echo ""

# Test 1: Redis container direct access
echo -e "${YELLOW}Test 1: Redis Container Direct Access${NC}"
echo "----------------------------------------"

if docker exec ai_validation_redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}✅ Redis accessible without authentication${NC}"
    echo -e "${YELLOW}⚠️  WARNING: Redis should require authentication in production${NC}"
elif docker exec ai_validation_redis redis-cli ping 2>&1 | grep -q "NOAUTH"; then
    echo -e "${YELLOW}ℹ️  Redis requires authentication (expected)${NC}"
    
    if docker exec ai_validation_redis redis-cli -a "${REDIS_PASSWORD}" ping 2>/dev/null | grep -q "PONG"; then
        echo -e "${GREEN}✅ Redis authentication successful${NC}"
    else
        echo -e "${RED}❌ Redis authentication failed${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Redis container not responding${NC}"
    exit 1
fi

echo ""

# Test 2: Redis configuration check
echo -e "${YELLOW}Test 2: Redis Configuration Check${NC}"
echo "--------------------------------"

AUTH_CONFIG=$(docker exec ai_validation_redis redis-cli -a "${REDIS_PASSWORD}" CONFIG GET requirepass 2>/dev/null | tail -1)
if [ "$AUTH_CONFIG" = "$REDIS_PASSWORD" ]; then
    echo -e "${GREEN}✅ Redis password configured correctly${NC}"
elif [ "$AUTH_CONFIG" = "" ]; then
    echo -e "${RED}❌ Redis has no password set${NC}"
else
    echo -e "${YELLOW}⚠️  Redis password mismatch${NC}"
    echo "  Expected: ${REDIS_PASSWORD}"
    echo "  Actual: ${AUTH_CONFIG}"
fi

echo ""

# Test 3: Backend container to Redis connectivity
echo -e "${YELLOW}Test 3: Backend Container to Redis${NC}"
echo "--------------------------------"

if docker exec ai_validation_backend python3 -c "
import redis
try:
    r = redis.Redis(host='${REDIS_HOST}', port=${REDIS_PORT}, password='${REDIS_PASSWORD}', decode_responses=True)
    result = r.ping()
    print('✅ Backend Redis connection successful')
except redis.exceptions.AuthenticationError:
    print('❌ Backend Redis authentication failed')
    exit(1)
except Exception as e:
    print(f'❌ Backend Redis connection error: {e}')
    exit(1)
" 2>/dev/null; then
    echo -e "${GREEN}✅ Backend can connect to Redis${NC}"
else
    echo -e "${RED}❌ Backend cannot connect to Redis${NC}"
fi

echo ""

# Test 4: CVAT container to Redis connectivity
echo -e "${YELLOW}Test 4: CVAT Container to Redis${NC}"
echo "-----------------------------"

if docker exec ai_validation_cvat redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -a "${REDIS_PASSWORD}" ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}✅ CVAT can connect to Redis with authentication${NC}"
else
    echo -e "${RED}❌ CVAT cannot connect to Redis${NC}"
    echo "Checking CVAT Redis environment variables:"
    docker exec ai_validation_cvat env | grep -i redis || echo "  No Redis environment variables found"
fi

echo ""

# Test 5: CVAT environment variables check
echo -e "${YELLOW}Test 5: CVAT Environment Variables${NC}"
echo "--------------------------------"

CVAT_REDIS_HOST=$(docker exec ai_validation_cvat env | grep "CVAT_REDIS_HOST" | cut -d'=' -f2 2>/dev/null || echo "")
CVAT_REDIS_PASSWORD=$(docker exec ai_validation_cvat env | grep "CVAT_REDIS_PASSWORD" | cut -d'=' -f2 2>/dev/null || echo "")

echo "  CVAT_REDIS_HOST: ${CVAT_REDIS_HOST:-NOT SET}"
echo "  CVAT_REDIS_PASSWORD: ${CVAT_REDIS_PASSWORD:-NOT SET}"

if [ -z "$CVAT_REDIS_HOST" ]; then
    echo -e "${RED}❌ CVAT_REDIS_HOST not set${NC}"
else
    echo -e "${GREEN}✅ CVAT_REDIS_HOST configured${NC}"
fi

if [ -z "$CVAT_REDIS_PASSWORD" ]; then
    echo -e "${RED}❌ CVAT_REDIS_PASSWORD not set - THIS IS THE PROBLEM${NC}"
else
    echo -e "${GREEN}✅ CVAT_REDIS_PASSWORD configured${NC}"
fi

echo ""

# Test 6: RQ Worker status check
echo -e "${YELLOW}Test 6: RQ Worker Status${NC}"
echo "----------------------"

RQ_STATUS=$(docker exec ai_validation_cvat supervisorctl status 2>/dev/null | grep -E "rqworker|rqscheduler" || echo "")
if [ -z "$RQ_STATUS" ]; then
    echo -e "${RED}❌ No RQ workers found${NC}"
else
    echo "RQ Worker Status:"
    echo "$RQ_STATUS" | while IFS= read -r line; do
        if echo "$line" | grep -q "RUNNING"; then
            echo -e "${GREEN}  ✅ $line${NC}"
        elif echo "$line" | grep -q "FATAL"; then
            echo -e "${RED}  ❌ $line${NC}"
        else
            echo -e "${YELLOW}  ⚠️  $line${NC}"
        fi
    done
fi

echo ""

# Test 7: Recent error logs check
echo -e "${YELLOW}Test 7: Recent Authentication Errors${NC}"
echo "-----------------------------------"

RECENT_ERRORS=$(docker logs ai_validation_cvat --since=5m 2>&1 | grep -i "authentication required\|noauth\|redis.*error" || echo "")
if [ -z "$RECENT_ERRORS" ]; then
    echo -e "${GREEN}✅ No recent authentication errors found${NC}"
else
    echo -e "${RED}❌ Recent authentication errors found:${NC}"
    echo "$RECENT_ERRORS" | head -5
fi

echo ""

# Summary
echo -e "${BLUE}📊 CONNECTIVITY TEST SUMMARY${NC}"
echo "============================="

# Count issues
ISSUES=0

# Redis basic connectivity
if ! docker exec ai_validation_redis redis-cli -a "${REDIS_PASSWORD}" ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${RED}❌ Redis authentication failing${NC}"
    ((ISSUES++))
fi

# CVAT Redis password missing
if [ -z "$CVAT_REDIS_PASSWORD" ]; then
    echo -e "${RED}❌ CVAT_REDIS_PASSWORD not configured${NC}"
    ((ISSUES++))
fi

# RQ workers failing
if docker exec ai_validation_cvat supervisorctl status 2>/dev/null | grep -q "FATAL"; then
    echo -e "${RED}❌ RQ workers failing${NC}"
    ((ISSUES++))
fi

echo ""
if [ "$ISSUES" -eq 0 ]; then
    echo -e "${GREEN}🎉 All Redis connectivity tests passed!${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Found ${ISSUES} connectivity issue(s)${NC}"
    echo ""
    echo -e "${YELLOW}🔧 RECOMMENDED FIXES:${NC}"
    echo "1. Run the Redis authentication fix script:"
    echo "   ./scripts/fix-redis-auth.sh"
    echo ""
    echo "2. Or manually add to docker-compose.yml CVAT section:"
    echo "   CVAT_REDIS_PASSWORD: \${REDIS_PASSWORD:-secure_redis_password}"
    echo ""
    echo "3. Restart containers:"
    echo "   docker-compose restart cvat"
    exit 1
fi