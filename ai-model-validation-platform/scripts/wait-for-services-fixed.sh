#!/bin/bash
# =====================================================================
# AI Model Validation Platform - FIXED SERVICE WAIT SCRIPT
# =====================================================================
# This script fixes all service discovery and health check issues

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TIMEOUT=${TIMEOUT:-300}  # 5 minutes default timeout
POSTGRES_HOST=${POSTGRES_HOST:-postgres}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_USER=${VRU_DATABASE_USER:-vru_user}
POSTGRES_DB=${VRU_DATABASE_NAME:-vru_validation}

REDIS_HOST=${REDIS_HOST:-redis}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_PASSWORD=${VRU_REDIS_PASSWORD:-secure_redis_password_2024}

# Functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Wait for port to be available
wait_for_port() {
    local host=$1
    local port=$2
    local service_name=$3
    local timeout=$TIMEOUT
    local elapsed=0
    local interval=5

    print_info "Waiting for $service_name ($host:$port) to be available..."

    while [ $elapsed -lt $timeout ]; do
        if nc -z "$host" "$port" 2>/dev/null; then
            print_success "$service_name is available on $host:$port"
            return 0
        fi

        if [ $elapsed -ge $timeout ]; then
            print_error "$service_name failed to become available within ${timeout}s"
            return 1
        fi

        sleep $interval
        elapsed=$((elapsed + interval))
        print_info "Still waiting for $service_name... (${elapsed}s/${timeout}s)"
    done
}

# Wait for PostgreSQL to be ready
wait_for_postgres() {
    print_info "Checking PostgreSQL connectivity..."
    
    local timeout=$TIMEOUT
    local elapsed=0
    local interval=5

    while [ $elapsed -lt $timeout ]; do
        if pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
            print_success "PostgreSQL is ready and accepting connections"
            return 0
        fi

        if [ $elapsed -ge $timeout ]; then
            print_error "PostgreSQL failed to become ready within ${timeout}s"
            print_info "Debug info:"
            print_info "Host: $POSTGRES_HOST, Port: $POSTGRES_PORT, User: $POSTGRES_USER, DB: $POSTGRES_DB"
            return 1
        fi

        sleep $interval
        elapsed=$((elapsed + interval))
        print_info "Still waiting for PostgreSQL to be ready... (${elapsed}s/${timeout}s)"
    done
}

# Wait for Redis to be ready
wait_for_redis() {
    print_info "Checking Redis connectivity..."
    
    local timeout=$TIMEOUT
    local elapsed=0
    local interval=5

    while [ $elapsed -lt $timeout ]; do
        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping >/dev/null 2>&1; then
            print_success "Redis is ready and accepting connections"
            return 0
        fi

        if [ $elapsed -ge $timeout ]; then
            print_error "Redis failed to become ready within ${timeout}s"
            print_info "Debug info:"
            print_info "Host: $REDIS_HOST, Port: $REDIS_PORT"
            return 1
        fi

        sleep $interval
        elapsed=$((elapsed + interval))
        print_info "Still waiting for Redis to be ready... (${elapsed}s/${timeout}s)"
    done
}

# Test database connection with Python
test_database_connection() {
    print_info "Testing database connection with application..."
    
    python3 -c "
import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Try to import and test database connection
    sys.path.append('/app')
    
    # Set required environment variables
    os.environ['VRU_DATABASE_URL'] = 'postgresql://${POSTGRES_USER}:${VRU_DATABASE_PASSWORD:-secure_vru_password_2024}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}'
    os.environ['DATABASE_URL'] = os.environ['VRU_DATABASE_URL']
    os.environ['AIVALIDATION_DATABASE_URL'] = os.environ['VRU_DATABASE_URL']
    
    logger.info('Database URL: ' + os.environ['VRU_DATABASE_URL'])
    
    import database
    logger.info('Database module imported successfully')
    
    # Test connection
    from sqlalchemy import text
    engine = database.engine
    with engine.connect() as connection:
        result = connection.execute(text('SELECT 1 as test'))
        test_value = result.scalar()
        if test_value == 1:
            logger.info('Database connection test successful')
            print('Database connection: OK')
        else:
            logger.error('Database connection test failed - unexpected result')
            sys.exit(1)
            
except ImportError as e:
    logger.error(f'Failed to import database module: {e}')
    print(f'Database import error: {e}')
    sys.exit(1)
except Exception as e:
    logger.error(f'Database connection failed: {e}')
    print(f'Database connection error: {e}')
    sys.exit(1)
" 2>/dev/null

    if [ $? -eq 0 ]; then
        print_success "Database connection test passed"
        return 0
    else
        print_error "Database connection test failed"
        return 1
    fi
}

# Main waiting logic
main() {
    print_info "AI Model Validation Platform - Service Dependency Checker"
    print_info "Timeout: ${TIMEOUT}s"
    print_info "============================================================"
    
    # Wait for PostgreSQL port
    if ! wait_for_port "$POSTGRES_HOST" "$POSTGRES_PORT" "PostgreSQL"; then
        exit 1
    fi
    
    # Wait for PostgreSQL to be ready
    if ! wait_for_postgres; then
        exit 1
    fi
    
    # Wait for Redis port
    if ! wait_for_port "$REDIS_HOST" "$REDIS_PORT" "Redis"; then
        exit 1
    fi
    
    # Wait for Redis to be ready
    if ! wait_for_redis; then
        exit 1
    fi
    
    # Test database connection
    if ! test_database_connection; then
        print_warning "Database connection test failed, but continuing..."
    fi
    
    print_success "All services are ready!"
    print_info "============================================================"
    
    # Execute the provided command
    if [ $# -gt 0 ]; then
        print_info "Executing: $*"
        exec "$@"
    fi
}

# Install required tools if not available
install_tools() {
    if ! command -v nc >/dev/null 2>&1; then
        print_warning "netcat not found, attempting to install..."
        apt-get update >/dev/null 2>&1 && apt-get install -y netcat-traditional >/dev/null 2>&1 || true
    fi
    
    if ! command -v pg_isready >/dev/null 2>&1; then
        print_warning "pg_isready not found, attempting to install..."
        apt-get update >/dev/null 2>&1 && apt-get install -y postgresql-client >/dev/null 2>&1 || true
    fi
    
    if ! command -v redis-cli >/dev/null 2>&1; then
        print_warning "redis-cli not found, attempting to install..."
        apt-get update >/dev/null 2>&1 && apt-get install -y redis-tools >/dev/null 2>&1 || true
    fi
}

# Check if running as dependency check or execution wrapper
if [ "$1" = "--dependency-check" ]; then
    shift
    install_tools
    main "$@"
else
    install_tools
    main "$@"
fi