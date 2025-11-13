#!/bin/bash
################################################################################
# HIL Backend Deployment Script
# Version: 1.0.0
# Description: Production-grade deployment with process management, health checks,
#              and automatic rollback on failure
################################################################################

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${BACKEND_DIR}/logs"
DEPLOYMENT_LOG="${LOG_DIR}/deployment_$(date +%Y%m%d_%H%M%S).log"
PID_FILE="${BACKEND_DIR}/backend.pid"
HEALTH_ENDPOINT="http://localhost:8000/health"
API_PORT=8000
MAX_WAIT_SECONDS=30
HEALTH_CHECK_RETRIES=10
HEALTH_CHECK_INTERVAL=3

# Backup configuration
BACKUP_DIR="${BACKEND_DIR}/backups"
BACKUP_DB="${BACKUP_DIR}/db_backup_$(date +%Y%m%d_%H%M%S).db"

# Process management
PROCESS_NAME="python3 main.py"
GRACEFUL_SHUTDOWN_TIMEOUT=15

################################################################################
# Logging Functions
################################################################################

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

log_info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1" | tee -a "$DEPLOYMENT_LOG"
}

################################################################################
# Pre-Flight Checks
################################################################################

pre_flight_checks() {
    log "Running pre-flight checks..."

    # Create necessary directories
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"

    # Check if we're in the correct directory
    if [ ! -f "${BACKEND_DIR}/main.py" ]; then
        log_error "main.py not found in ${BACKEND_DIR}"
        return 1
    fi

    # Check if requirements.txt exists
    if [ ! -f "${BACKEND_DIR}/requirements.txt" ]; then
        log_warning "requirements.txt not found"
    fi

    # Check Python version
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    log_info "Python version: ${PYTHON_VERSION}"

    # Check disk space (require at least 1GB free)
    AVAILABLE_SPACE=$(df -BG "${BACKEND_DIR}" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$AVAILABLE_SPACE" -lt 1 ]; then
        log_error "Insufficient disk space: ${AVAILABLE_SPACE}GB available"
        return 1
    fi
    log_info "Available disk space: ${AVAILABLE_SPACE}GB"

    # Validate Python syntax
    log_info "Validating Python syntax..."
    if ! python3 -m py_compile "${BACKEND_DIR}/main.py" 2>/dev/null; then
        log_error "Python syntax validation failed for main.py"
        return 1
    fi

    log "Pre-flight checks passed ✓"
    return 0
}

################################################################################
# Process Management Functions
################################################################################

get_backend_pids() {
    # Get PIDs of all backend processes
    pgrep -f "python3 main.py" || true
}

get_port_pids() {
    # Get PIDs using port 8000
    lsof -ti:${API_PORT} 2>/dev/null || true
}

stop_backend_gracefully() {
    log "Attempting graceful shutdown of backend processes..."

    local pids=$(get_backend_pids)

    if [ -z "$pids" ]; then
        log "No backend processes found"
        return 0
    fi

    log_info "Found backend PIDs: $pids"

    # Send SIGTERM for graceful shutdown
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Sending SIGTERM to PID $pid"
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done

    # Wait for graceful shutdown
    local wait_time=0
    while [ $wait_time -lt $GRACEFUL_SHUTDOWN_TIMEOUT ]; do
        pids=$(get_backend_pids)
        if [ -z "$pids" ]; then
            log "Graceful shutdown successful ✓"
            return 0
        fi
        sleep 1
        ((wait_time++))
    done

    # If still running, force kill
    pids=$(get_backend_pids)
    if [ -n "$pids" ]; then
        log_warning "Graceful shutdown timeout, forcing termination..."
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                log_info "Sending SIGKILL to PID $pid"
                kill -9 "$pid" 2>/dev/null || true
            fi
        done
        sleep 2
    fi

    # Final verification
    pids=$(get_backend_pids)
    if [ -n "$pids" ]; then
        log_error "Failed to stop backend processes: $pids"
        return 1
    fi

    log "All backend processes stopped ✓"
    return 0
}

release_port() {
    log "Ensuring port ${API_PORT} is released..."

    local port_pids=$(get_port_pids)

    if [ -z "$port_pids" ]; then
        log "Port ${API_PORT} is free ✓"
        return 0
    fi

    log_info "Port ${API_PORT} is in use by PIDs: $port_pids"

    # Kill processes using the port
    for pid in $port_pids; do
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Killing process $pid using port ${API_PORT}"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done

    # Wait for port to be released
    local wait_time=0
    while [ $wait_time -lt $MAX_WAIT_SECONDS ]; do
        port_pids=$(get_port_pids)
        if [ -z "$port_pids" ]; then
            log "Port ${API_PORT} released ✓"
            return 0
        fi
        sleep 1
        ((wait_time++))
    done

    log_error "Timeout waiting for port ${API_PORT} to be released"
    return 1
}

################################################################################
# Cache Management
################################################################################

clear_python_cache() {
    log "Clearing Python bytecode cache..."

    cd "$BACKEND_DIR"

    # Count cache files before cleanup
    local cache_count=$(find . -type f -name "*.pyc" 2>/dev/null | wc -l)
    local pycache_count=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)

    log_info "Found ${cache_count} .pyc files and ${pycache_count} __pycache__ directories"

    # Remove .pyc files
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

    # Remove __pycache__ directories
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    # Remove .pyo files (optimized bytecode)
    find . -type f -name "*.pyo" -delete 2>/dev/null || true

    # Verify cleanup
    cache_count=$(find . -type f -name "*.pyc" 2>/dev/null | wc -l)
    pycache_count=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)

    if [ "$cache_count" -eq 0 ] && [ "$pycache_count" -eq 0 ]; then
        log "Python cache cleared successfully ✓"
        return 0
    else
        log_warning "Some cache files may remain: ${cache_count} .pyc, ${pycache_count} __pycache__"
        return 0
    fi
}

################################################################################
# Database Backup
################################################################################

backup_database() {
    log "Creating database backup..."

    local db_file="${BACKEND_DIR}/dev_database.db"

    if [ ! -f "$db_file" ]; then
        log_warning "Database file not found: $db_file"
        return 0
    fi

    # Create backup
    cp "$db_file" "$BACKUP_DB"

    if [ -f "$BACKUP_DB" ]; then
        local backup_size=$(du -h "$BACKUP_DB" | awk '{print $1}')
        log "Database backup created: $BACKUP_DB (${backup_size}) ✓"

        # Keep only last 5 backups
        ls -t "${BACKUP_DIR}"/db_backup_*.db | tail -n +6 | xargs -r rm
        log_info "Old backups cleaned up (keeping last 5)"

        return 0
    else
        log_error "Failed to create database backup"
        return 1
    fi
}

################################################################################
# Backend Startup
################################################################################

start_backend() {
    log "Starting backend server..."

    cd "$BACKEND_DIR"

    # Start backend in background
    nohup python3 main.py > "${LOG_DIR}/backend_$(date +%Y%m%d_%H%M%S).log" 2>&1 &
    local pid=$!

    # Save PID
    echo "$pid" > "$PID_FILE"

    log_info "Backend started with PID: $pid"

    # Wait for startup
    sleep 5

    # Verify process is still running
    if ! kill -0 "$pid" 2>/dev/null; then
        log_error "Backend process died immediately after startup"
        return 1
    fi

    log "Backend process started successfully ✓"
    return 0
}

################################################################################
# Health Checks
################################################################################

wait_for_health() {
    log "Waiting for backend to become healthy..."

    local retry_count=0

    while [ $retry_count -lt $HEALTH_CHECK_RETRIES ]; do
        # Check if process is still running
        if [ -f "$PID_FILE" ]; then
            local pid=$(cat "$PID_FILE")
            if ! kill -0 "$pid" 2>/dev/null; then
                log_error "Backend process died during startup"
                return 1
            fi
        fi

        # Try health endpoint
        if curl -sf "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
            log "Backend health check passed ✓"
            return 0
        fi

        log_info "Health check attempt $((retry_count + 1))/${HEALTH_CHECK_RETRIES}..."
        sleep $HEALTH_CHECK_INTERVAL
        ((retry_count++))
    done

    log_error "Backend health check timeout after ${HEALTH_CHECK_RETRIES} attempts"
    return 1
}

run_smoke_tests() {
    log "Running smoke tests..."

    # Test 1: Health endpoint
    if ! curl -sf "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
        log_error "Smoke test failed: Health endpoint unreachable"
        return 1
    fi
    log_info "✓ Health endpoint responding"

    # Test 2: API root endpoint
    if ! curl -sf "http://localhost:8000/api/health" > /dev/null 2>&1; then
        log_warning "API health endpoint not responding (non-critical)"
    else
        log_info "✓ API health endpoint responding"
    fi

    # Test 3: Check for errors in logs
    local recent_log=$(ls -t "${LOG_DIR}"/backend_*.log | head -1)
    if [ -f "$recent_log" ]; then
        local error_count=$(grep -i "error\|exception\|traceback" "$recent_log" | wc -l)
        if [ "$error_count" -gt 5 ]; then
            log_warning "Found ${error_count} errors in startup logs"
        else
            log_info "✓ Minimal errors in startup logs (${error_count})"
        fi
    fi

    log "Smoke tests completed ✓"
    return 0
}

################################################################################
# Rollback
################################################################################

rollback_deployment() {
    log_error "Deployment failed, initiating rollback..."

    # Stop current backend
    stop_backend_gracefully

    # Restore database backup if exists
    if [ -f "$BACKUP_DB" ]; then
        local db_file="${BACKEND_DIR}/dev_database.db"
        cp "$BACKUP_DB" "$db_file"
        log "Database restored from backup ✓"
    fi

    log_error "Rollback completed. Please check logs: $DEPLOYMENT_LOG"
    return 1
}

################################################################################
# Main Deployment Flow
################################################################################

main() {
    log "=========================================="
    log "HIL Backend Deployment Started"
    log "=========================================="
    log "Deployment time: $(date)"
    log "Backend directory: ${BACKEND_DIR}"
    log "Log file: ${DEPLOYMENT_LOG}"
    log ""

    # Step 1: Pre-flight checks
    if ! pre_flight_checks; then
        log_error "Pre-flight checks failed"
        exit 1
    fi

    # Step 2: Create database backup
    if ! backup_database; then
        log_error "Database backup failed"
        exit 1
    fi

    # Step 3: Stop existing backend
    if ! stop_backend_gracefully; then
        log_error "Failed to stop existing backend"
        exit 1
    fi

    # Step 4: Release port
    if ! release_port; then
        log_error "Failed to release port ${API_PORT}"
        exit 1
    fi

    # Step 5: Clear Python cache
    if ! clear_python_cache; then
        log_warning "Cache cleanup had issues but continuing..."
    fi

    # Step 6: Start new backend
    if ! start_backend; then
        rollback_deployment
        exit 1
    fi

    # Step 7: Health checks
    if ! wait_for_health; then
        rollback_deployment
        exit 1
    fi

    # Step 8: Smoke tests
    if ! run_smoke_tests; then
        log_warning "Some smoke tests failed but deployment continuing..."
    fi

    # Success
    log ""
    log "=========================================="
    log "✅ Deployment Successful!"
    log "=========================================="
    log "Backend is running on port ${API_PORT}"
    log "PID: $(cat $PID_FILE 2>/dev/null || echo 'N/A')"
    log "Health endpoint: ${HEALTH_ENDPOINT}"
    log "Logs: ${LOG_DIR}"
    log ""
    log "To monitor logs: tail -f ${LOG_DIR}/backend_*.log"
    log "To check status: curl ${HEALTH_ENDPOINT}"
    log ""

    return 0
}

# Execute main function
main "$@"
exit $?
