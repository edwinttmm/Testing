#!/bin/bash
################################################################################
# HIL Backend Rollback Script
# Version: 1.0.0
# Description: Emergency rollback procedure for failed deployments
################################################################################

set -e
set -o pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKEND_DIR}/backups"
LOG_DIR="${BACKEND_DIR}/logs"
ROLLBACK_LOG="${LOG_DIR}/rollback_$(date +%Y%m%d_%H%M%S).log"

################################################################################
# Logging Functions
################################################################################

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$ROLLBACK_LOG"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$ROLLBACK_LOG"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$ROLLBACK_LOG"
}

log_info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1" | tee -a "$ROLLBACK_LOG"
}

################################################################################
# Rollback Functions
################################################################################

stop_current_backend() {
    log "Stopping current backend process..."

    local pids=$(pgrep -f "python3 main.py" || true)

    if [ -z "$pids" ]; then
        log "No backend processes running"
        return 0
    fi

    for pid in $pids; do
        log_info "Killing process $pid"
        kill -9 "$pid" 2>/dev/null || true
    done

    sleep 2

    # Verify stopped
    pids=$(pgrep -f "python3 main.py" || true)
    if [ -n "$pids" ]; then
        log_error "Failed to stop backend processes: $pids"
        return 1
    fi

    log "Backend stopped successfully ✓"
    return 0
}

restore_database_backup() {
    log "Restoring database from backup..."

    if [ ! -d "$BACKUP_DIR" ]; then
        log_warning "Backup directory not found: $BACKUP_DIR"
        return 0
    fi

    # Find most recent backup
    local latest_backup=$(ls -t "${BACKUP_DIR}"/db_backup_*.db 2>/dev/null | head -1)

    if [ -z "$latest_backup" ]; then
        log_warning "No database backup found"
        return 0
    fi

    log_info "Found backup: $latest_backup"

    local db_file="${BACKEND_DIR}/dev_database.db"

    # Backup current database before restoring
    if [ -f "$db_file" ]; then
        cp "$db_file" "${db_file}.pre-rollback"
        log_info "Current database backed up to ${db_file}.pre-rollback"
    fi

    # Restore backup
    cp "$latest_backup" "$db_file"

    if [ $? -eq 0 ]; then
        log "Database restored from backup ✓"
        return 0
    else
        log_error "Failed to restore database backup"
        return 1
    fi
}

clear_python_cache() {
    log "Clearing Python cache..."

    cd "$BACKEND_DIR"

    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    log "Python cache cleared ✓"
    return 0
}

verify_previous_version() {
    log "Verifying previous version files..."

    cd "$BACKEND_DIR"

    if [ ! -f "main.py" ]; then
        log_error "main.py not found - cannot verify previous version"
        return 1
    fi

    if python3 -m py_compile "main.py" 2>/dev/null; then
        log "Previous version files validated ✓"
        return 0
    else
        log_error "Previous version has syntax errors"
        return 1
    fi
}

restart_backend() {
    log "Restarting backend with previous version..."

    cd "$BACKEND_DIR"

    # Start backend
    nohup python3 main.py > "${LOG_DIR}/rollback_backend_$(date +%Y%m%d_%H%M%S).log" 2>&1 &
    local pid=$!

    log_info "Backend started with PID: $pid"

    # Wait for startup
    sleep 5

    # Verify running
    if kill -0 "$pid" 2>/dev/null; then
        log "Backend restarted successfully ✓"

        # Try health check
        if curl -sf "http://localhost:8000/health" > /dev/null 2>&1; then
            log "Health check passed ✓"
        else
            log_warning "Health check failed but process is running"
        fi

        return 0
    else
        log_error "Backend failed to restart"
        return 1
    fi
}

create_incident_report() {
    log "Creating incident report..."

    local report_file="${LOG_DIR}/incident_report_$(date +%Y%m%d_%H%M%S).txt"

    cat > "$report_file" <<EOF
================================================================================
HIL BACKEND ROLLBACK INCIDENT REPORT
================================================================================
Date: $(date)
User: $(whoami)
Host: $(hostname)

SUMMARY
-------
Deployment failed and rollback procedure was executed.

ACTIONS TAKEN
-------------
1. Current backend process stopped
2. Database restored from backup
3. Python cache cleared
4. Previous version restarted

SYSTEM STATE
------------
Backup directory: ${BACKUP_DIR}
Rollback log: ${ROLLBACK_LOG}
Backend directory: ${BACKEND_DIR}

NEXT STEPS
----------
1. Review deployment logs: ${LOG_DIR}/deployment_*.log
2. Review rollback logs: ${ROLLBACK_LOG}
3. Check backend logs: ${LOG_DIR}/rollback_backend_*.log
4. Investigate root cause of deployment failure
5. Fix issues before attempting re-deployment

CONTACT
-------
For support, review documentation or contact system administrator.

================================================================================
EOF

    log "Incident report created: $report_file"
    return 0
}

################################################################################
# Main Rollback Procedure
################################################################################

main() {
    mkdir -p "$LOG_DIR"

    echo "=========================================="
    echo "HIL Backend Emergency Rollback"
    echo "=========================================="
    log "Rollback initiated by: $(whoami)"
    log "Timestamp: $(date)"
    log ""

    # Confirm rollback
    if [ -t 0 ]; then  # If running interactively
        echo -e "${RED}WARNING: This will rollback to the previous version${NC}"
        read -p "Are you sure you want to proceed? (yes/no): " confirmation

        if [ "$confirmation" != "yes" ]; then
            log "Rollback cancelled by user"
            exit 0
        fi
    fi

    log "Starting rollback procedure..."

    # Step 1: Stop current backend
    if ! stop_current_backend; then
        log_error "Failed to stop current backend"
        exit 1
    fi

    # Step 2: Restore database backup
    if ! restore_database_backup; then
        log_warning "Database restore had issues but continuing..."
    fi

    # Step 3: Clear Python cache
    clear_python_cache

    # Step 4: Verify previous version
    if ! verify_previous_version; then
        log_error "Cannot verify previous version - manual intervention required"
        exit 1
    fi

    # Step 5: Restart backend
    if ! restart_backend; then
        log_error "Failed to restart backend - manual intervention required"
        create_incident_report
        exit 1
    fi

    # Step 6: Create incident report
    create_incident_report

    log ""
    log "=========================================="
    log "✅ Rollback completed successfully"
    log "=========================================="
    log "Backend has been rolled back to previous version"
    log "Incident report: ${LOG_DIR}/incident_report_*.txt"
    log ""
    log "Please review logs and investigate the deployment failure"
    log "before attempting to deploy again."

    return 0
}

main "$@"
exit $?
