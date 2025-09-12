#!/bin/bash

# Process Monitor for Frontend Development
# Monitors process health and provides recovery mechanisms

FRONTEND_DIR="/home/rigade/Testing/ai-model-validation-platform/frontend"
LOG_FILE="$FRONTEND_DIR/logs/process-monitor.log"
PID_FILE="$FRONTEND_DIR/logs/frontend.pid"

# Ensure logs directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to check if frontend is running
is_frontend_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to check port availability
is_port_free() {
    local port=$1
    ! netstat -tulpn 2>/dev/null | grep -q ":$port "
}

# Function to start frontend with recovery
start_frontend() {
    log "Starting frontend development server..."
    
    cd "$FRONTEND_DIR" || exit 1
    
    # Run cleanup first
    ./scripts/process-cleanup.sh
    
    # Set environment variables
    export ESLINT_NO_DEV_ERRORS=true
    export TSC_COMPILE_ON_ERROR=true
    export SKIP_PREFLIGHT_CHECK=true
    export GENERATE_SOURCEMAP=false
    export FAST_REFRESH=false
    
    # Start in background and capture PID
    nohup npm start > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    
    log "Frontend started with PID: $pid"
    
    # Wait for startup
    local retries=0
    while [ $retries -lt 30 ]; do
        if is_port_free 3000; then
            sleep 2
            ((retries++))
        else
            log "✅ Frontend successfully started on port 3000"
            return 0
        fi
    done
    
    log "❌ Frontend failed to start within 60 seconds"
    return 1
}

# Function to stop frontend
stop_frontend() {
    log "Stopping frontend..."
    
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid"
            sleep 5
            if ps -p "$pid" > /dev/null 2>&1; then
                kill -9 "$pid"
            fi
        fi
        rm -f "$PID_FILE"
    fi
    
    # Run full cleanup
    ./scripts/process-cleanup.sh
    
    log "Frontend stopped"
}

# Function to restart frontend
restart_frontend() {
    log "Restarting frontend..."
    stop_frontend
    sleep 3
    start_frontend
}

# Function to check frontend health
health_check() {
    if is_frontend_running; then
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            log "✅ Frontend is healthy"
            return 0
        else
            log "⚠️  Frontend process running but not responding"
            return 1
        fi
    else
        log "❌ Frontend is not running"
        return 1
    fi
}

# Main command handling
case "${1:-status}" in
    start)
        if is_frontend_running; then
            log "Frontend is already running"
        else
            start_frontend
        fi
        ;;
    stop)
        stop_frontend
        ;;
    restart)
        restart_frontend
        ;;
    status)
        if is_frontend_running; then
            echo "Frontend is running (PID: $(cat "$PID_FILE"))"
        else
            echo "Frontend is not running"
        fi
        ;;
    health)
        health_check
        ;;
    monitor)
        log "Starting continuous monitoring..."
        while true; do
            if ! health_check; then
                log "Frontend unhealthy, attempting restart..."
                restart_frontend
            fi
            sleep 30
        done
        ;;
    cleanup)
        ./scripts/process-cleanup.sh
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|health|monitor|cleanup}"
        exit 1
        ;;
esac