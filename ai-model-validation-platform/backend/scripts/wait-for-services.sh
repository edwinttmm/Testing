#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WAIT_HOSTS=${WAIT_HOSTS:-"postgres:5432,redis:6379"}
WAIT_HOSTS_TIMEOUT=${WAIT_HOSTS_TIMEOUT:-300}
WAIT_SLEEP_INTERVAL=${WAIT_SLEEP_INTERVAL:-5}
WAIT_HOST_CONNECT_TIMEOUT=${WAIT_HOST_CONNECT_TIMEOUT:-30}

echo -e "${BLUE}🚀 Container Service Orchestration Started${NC}"
echo -e "${YELLOW}⏳ Waiting for services: $WAIT_HOSTS${NC}"
echo -e "${YELLOW}⏳ Timeout: ${WAIT_HOSTS_TIMEOUT}s, Interval: ${WAIT_SLEEP_INTERVAL}s${NC}"

# Function to check if a host:port is reachable
wait_for_host() {
    local host=$1
    local port=$2
    local timeout=$3
    
    echo -e "${YELLOW}🔍 Checking $host:$port...${NC}"
    
    if command -v nc >/dev/null 2>&1; then
        # Use netcat if available
        timeout $timeout bash -c "until nc -z $host $port; do sleep 1; done"
    elif command -v telnet >/dev/null 2>&1; then
        # Use telnet as fallback
        timeout $timeout bash -c "until echo quit | telnet $host $port 2>/dev/null | grep -q 'Connected'; do sleep 1; done"
    else
        # Use bash built-in TCP socket if no other tools available
        timeout $timeout bash -c "until echo >/dev/tcp/$host/$port; do sleep 1; done"
    fi
}

# Function to verify PostgreSQL is ready for connections
verify_postgres() {
    local host=$1
    local port=$2
    
    echo -e "${YELLOW}🔍 Verifying PostgreSQL readiness on $host:$port...${NC}"
    
    # Check if PostgreSQL accepts connections and can execute queries
    if command -v pg_isready >/dev/null 2>&1; then
        pg_isready -h $host -p $port -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-vru_validation}" -t 30
    else
        # Fallback to basic connection test
        wait_for_host $host $port 30
    fi
}

# Function to verify Redis is ready
verify_redis() {
    local host=$1
    local port=$2
    
    echo -e "${YELLOW}🔍 Verifying Redis readiness on $host:$port...${NC}"
    
    if command -v redis-cli >/dev/null 2>&1; then
        # Test Redis with a simple ping
        timeout 30 bash -c "until redis-cli -h $host -p $port ping | grep -q PONG; do sleep 1; done"
    else
        # Fallback to basic connection test
        wait_for_host $host $port 30
    fi
}

# Parse and wait for each host
start_time=$(date +%s)
IFS=',' read -ra HOST_LIST <<< "$WAIT_HOSTS"

for host_port in "${HOST_LIST[@]}"; do
    IFS=':' read -ra HOST_PORT <<< "$host_port"
    host=${HOST_PORT[0]}
    port=${HOST_PORT[1]}
    
    echo -e "${BLUE}📋 Processing service: $host:$port${NC}"
    
    # Check current time vs timeout
    current_time=$(date +%s)
    elapsed_time=$((current_time - start_time))
    
    if [ $elapsed_time -ge $WAIT_HOSTS_TIMEOUT ]; then
        echo -e "${RED}❌ Timeout reached waiting for services!${NC}"
        exit 1
    fi
    
    remaining_time=$((WAIT_HOSTS_TIMEOUT - elapsed_time))
    
    # Service-specific verification
    case $host in
        postgres)
            if ! verify_postgres $host $port; then
                echo -e "${RED}❌ PostgreSQL at $host:$port is not ready after timeout${NC}"
                exit 1
            fi
            ;;
        redis)
            if ! verify_redis $host $port; then
                echo -e "${RED}❌ Redis at $host:$port is not ready after timeout${NC}"
                exit 1
            fi
            ;;
        *)
            if ! wait_for_host $host $port $remaining_time; then
                echo -e "${RED}❌ Service $host:$port is not ready after timeout${NC}"
                exit 1
            fi
            ;;
    esac
    
    echo -e "${GREEN}✅ Service $host:$port is ready!${NC}"
    sleep $WAIT_SLEEP_INTERVAL
done

echo -e "${GREEN}🎉 All services are ready! Starting application...${NC}"

# Execute the main command
exec "$@"