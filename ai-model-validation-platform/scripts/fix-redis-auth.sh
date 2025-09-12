#!/bin/bash

# Redis Authentication Fix Script for CVAT Integration
# Fixes critical Redis password configuration issues

set -e

echo "🔧 REDIS AUTHENTICATION FIX SCRIPT"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REDIS_PASSWORD="${REDIS_PASSWORD:-secure_redis_password_2024}"
BACKUP_DIR="./backup_$(date +%Y%m%d_%H%M%S)"

echo -e "${YELLOW}Step 1: Creating configuration backup...${NC}"
mkdir -p "$BACKUP_DIR"
cp docker-compose.yml "$BACKUP_DIR/"
cp .env* "$BACKUP_DIR/" 2>/dev/null || true

echo -e "${YELLOW}Step 2: Stopping containers...${NC}"
docker-compose down || true

echo -e "${YELLOW}Step 3: Fixing environment variables...${NC}"

# Create standardized environment file
cat > .env << EOF
# Redis Authentication Configuration - FIXED
REDIS_PASSWORD=${REDIS_PASSWORD}
VRU_REDIS_PASSWORD=${REDIS_PASSWORD}

# Database Configuration
POSTGRES_DB=vru_validation
POSTGRES_USER=postgres  
POSTGRES_PASSWORD=secure_password_change_me

# Application Configuration
AIVALIDATION_SECRET_KEY=GENERATE_SECURE_KEY_FOR_PRODUCTION
APP_ENV=development
NODE_ENV=development
EOF

echo -e "${GREEN}✅ Environment file created with standardized Redis password${NC}"

echo -e "${YELLOW}Step 4: Fixing docker-compose.yml CVAT configuration...${NC}"

# Create temporary file with fixed CVAT configuration
python3 << 'PYTHON_SCRIPT'
import yaml
import sys

# Read docker-compose.yml
try:
    with open('docker-compose.yml', 'r') as f:
        compose = yaml.safe_load(f)
    
    # Fix CVAT environment variables
    if 'services' in compose and 'cvat' in compose['services']:
        cvat_env = compose['services']['cvat']['environment']
        
        # Convert to dict format if it's a list
        if isinstance(cvat_env, list):
            env_dict = {}
            for item in cvat_env:
                if isinstance(item, str) and '=' in item:
                    key, value = item.split('=', 1)
                    env_dict[key] = value
                elif isinstance(item, dict):
                    env_dict.update(item)
            cvat_env = env_dict
        
        # Add missing Redis password
        cvat_env['CVAT_REDIS_PASSWORD'] = '${REDIS_PASSWORD:-secure_redis_password}'
        
        # Update the configuration
        compose['services']['cvat']['environment'] = cvat_env
        
        # Write back to file
        with open('docker-compose.yml', 'w') as f:
            yaml.dump(compose, f, default_flow_style=False, indent=2)
        
        print("✅ CVAT Redis password configuration added")
    else:
        print("⚠️  CVAT service not found in docker-compose.yml")

except Exception as e:
    print(f"❌ Error fixing docker-compose.yml: {e}")
    sys.exit(1)

PYTHON_SCRIPT

echo -e "${YELLOW}Step 5: Testing Redis authentication...${NC}"

# Start only Redis first
docker-compose up -d redis

# Wait for Redis to be ready
echo "Waiting for Redis to start..."
sleep 10

# Test Redis connectivity
echo "Testing Redis authentication..."
if docker exec ai_validation_redis redis-cli -a "${REDIS_PASSWORD}" ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}✅ Redis authentication working correctly${NC}"
else
    echo -e "${RED}❌ Redis authentication failed${NC}"
    echo "Trying without password..."
    if docker exec ai_validation_redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
        echo -e "${YELLOW}⚠️  Redis is running WITHOUT authentication${NC}"
        echo "Restarting Redis with password..."
        docker-compose restart redis
        sleep 10
    else
        echo -e "${RED}❌ Redis is not responding${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}Step 6: Starting all services...${NC}"
docker-compose up -d

echo -e "${YELLOW}Step 7: Waiting for services to initialize...${NC}"
sleep 30

echo -e "${YELLOW}Step 8: Verifying CVAT Redis connectivity...${NC}"

# Test CVAT to Redis connection
if docker exec ai_validation_cvat redis-cli -h redis -a "${REDIS_PASSWORD}" ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}✅ CVAT can connect to Redis with authentication${NC}"
else
    echo -e "${RED}❌ CVAT cannot connect to Redis${NC}"
    echo "Checking CVAT environment variables..."
    docker exec ai_validation_cvat env | grep -i redis || echo "No Redis environment variables found"
    exit 1
fi

echo -e "${YELLOW}Step 9: Checking RQ worker status...${NC}"

# Check RQ workers
sleep 10
docker exec ai_validation_cvat supervisorctl status | grep -E "rqworker|rqscheduler" || echo "No RQ workers found"

# Check for authentication errors in logs
echo "Checking recent logs for authentication errors..."
if docker logs ai_validation_cvat --since=2m 2>&1 | grep -i "authentication required" > /dev/null; then
    echo -e "${RED}❌ Still seeing authentication errors in logs${NC}"
    echo "Recent CVAT logs:"
    docker logs ai_validation_cvat --tail=20 2>&1 | grep -E "redis|auth|error" || true
else
    echo -e "${GREEN}✅ No authentication errors found in recent logs${NC}"
fi

echo -e "\n${GREEN}🎉 REDIS AUTHENTICATION FIX COMPLETED${NC}"
echo "========================================"
echo "✅ Redis password: ${REDIS_PASSWORD}"
echo "✅ CVAT Redis configuration updated"
echo "✅ All services restarted"
echo ""
echo "📝 Configuration backup saved to: ${BACKUP_DIR}"
echo ""
echo "🔍 To monitor RQ workers:"
echo "   docker exec ai_validation_cvat supervisorctl status"
echo ""
echo "🔍 To check Redis connectivity:"
echo "   docker exec ai_validation_cvat redis-cli -h redis -a '${REDIS_PASSWORD}' ping"
echo ""
echo "🔍 To view CVAT logs:"
echo "   docker logs ai_validation_cvat --follow"

# Final validation
echo -e "\n${YELLOW}Final Validation:${NC}"
echo "Redis Status: $(docker exec ai_validation_redis redis-cli -a "${REDIS_PASSWORD}" ping 2>/dev/null || echo 'FAILED')"
echo "CVAT Status: $(docker exec ai_validation_cvat supervisorctl status | grep runserver | awk '{print $2}' 2>/dev/null || echo 'UNKNOWN')"
echo "RQ Workers: $(docker exec ai_validation_cvat supervisorctl status | grep -c "RUNNING" 2>/dev/null || echo '0') running"