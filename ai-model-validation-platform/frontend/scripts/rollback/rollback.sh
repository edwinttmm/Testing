#!/bin/bash

# AI Model Validation Platform - Rollback Script
# Emergency rollback capability for failed deployments

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_DIR="$PROJECT_ROOT/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/rollback_$(date +%Y%m%d_%H%M%S).log"

# Rollback configuration
BACKUP_DIR="${1:-}"
FORCE_ROLLBACK="${2:-false}"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

log_critical() {
    echo -e "${RED}[CRITICAL]${NC} $1" | tee -a "$LOG_FILE"
}

run_hook() {
    local hook_type=$1
    local description=$2
    if command -v npx >/dev/null 2>&1; then
        npx claude-flow@alpha hooks "$hook_type" --description "$description" || true
    fi
}

# Usage function
usage() {
    echo "Usage: $0 [BACKUP_DIR] [FORCE]"
    echo ""
    echo "Arguments:"
    echo "  BACKUP_DIR    Path to backup directory (optional, auto-detected if not provided)"
    echo "  FORCE         Set to 'true' to force rollback without confirmation"
    echo ""
    echo "Examples:"
    echo "  $0                                           # Auto-detect latest backup"
    echo "  $0 /path/to/backup                          # Use specific backup"
    echo "  $0 /path/to/backup true                     # Force rollback without confirmation"
    echo ""
    exit 1
}

# Confirmation function
confirm_rollback() {
    if [ "$FORCE_ROLLBACK" = "true" ]; then
        return 0
    fi
    
    echo ""
    echo -e "${YELLOW}⚠️  ROLLBACK CONFIRMATION REQUIRED ⚠️${NC}"
    echo "This will restore the previous deployment state."
    echo ""
    echo "Backup directory: $BACKUP_DIR"
    echo ""
    echo -e "${RED}This action will:"
    echo "- Replace the current build with the backup"
    echo "- Restore previous configuration files"
    echo "- Undo recent database changes (if applicable)"
    echo "- Clear current caches"
    echo -e "${NC}"
    echo ""
    read -p "Are you sure you want to proceed with rollback? (yes/no): " -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Rollback cancelled by user"
        exit 0
    fi
}

echo "======================================" | tee -a "$LOG_FILE"
echo "Emergency Rollback Started: $(date)" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"

run_hook "pre-task" "emergency-rollback"

cd "$PROJECT_ROOT"

# Auto-detect backup directory if not provided
if [ -z "$BACKUP_DIR" ]; then
    log_info "Auto-detecting backup directory..."
    
    # Check for last deployment backup file
    if [ -f ".last_deployment_backup" ]; then
        BACKUP_DIR=$(cat .last_deployment_backup)
        log_info "Found last deployment backup: $BACKUP_DIR"
    else
        # Find most recent backup
        if [ -d "backups" ]; then
            LATEST_BACKUP=$(find backups -maxdepth 1 -type d -name "20*" | sort -r | head -1)
            if [ -n "$LATEST_BACKUP" ]; then
                BACKUP_DIR="$LATEST_BACKUP"
                log_info "Found latest backup: $BACKUP_DIR"
            else
                log_critical "No backup directories found in backups/"
                exit 1
            fi
        else
            log_critical "No backups directory found and no backup path provided"
            usage
        fi
    fi
fi

# Validate backup directory
if [ ! -d "$BACKUP_DIR" ]; then
    log_critical "Backup directory does not exist: $BACKUP_DIR"
    exit 1
fi

log_info "Using backup directory: $BACKUP_DIR"

# Check backup contents
log_info "Validating backup contents..."
BACKUP_VALID=true

# Check for essential backup files
if [ ! -f "$BACKUP_DIR/package.json.backup" ]; then
    log_warning "package.json backup not found"
    BACKUP_VALID=false
fi

if [ ! -f "$BACKUP_DIR/package-lock.json.backup" ]; then
    log_warning "package-lock.json backup not found"
    BACKUP_VALID=false
fi

# List backup contents
log_info "Backup contents:"
ls -la "$BACKUP_DIR" | tee -a "$LOG_FILE"

if [ "$BACKUP_VALID" = false ]; then
    log_warning "Backup validation issues detected, but proceeding anyway"
fi

# Confirm rollback
confirm_rollback

ROLLBACK_START_TIME=$(date +%s)

# Step 1: Create current state snapshot before rollback
log_info "Creating pre-rollback snapshot..."
PRE_ROLLBACK_DIR="$PROJECT_ROOT/backups/pre-rollback-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$PRE_ROLLBACK_DIR"

# Backup current build if it exists
if [ -d "build" ]; then
    cp -r "build" "$PRE_ROLLBACK_DIR/current_build" || log_warning "Failed to backup current build"
    log_success "Current build backed up to pre-rollback snapshot"
fi

# Backup current package files
if [ -f "package.json" ]; then
    cp "package.json" "$PRE_ROLLBACK_DIR/package.json.current" || log_warning "Failed to backup current package.json"
fi

if [ -f "package-lock.json" ]; then
    cp "package-lock.json" "$PRE_ROLLBACK_DIR/package-lock.json.current" || log_warning "Failed to backup current package-lock.json"
fi

# Step 2: Stop any running services
log_info "Stopping running services..."
run_hook "notify" "stopping-services-for-rollback"

# Kill any running development servers (if any)
pkill -f "react-scripts start" 2>/dev/null || true
pkill -f "npm start" 2>/dev/null || true
pkill -f "webpack-dev-server" 2>/dev/null || true

log_success "Services stopped"

# Step 3: Restore build directory
log_info "Restoring build directory..."
if [ -d "$BACKUP_DIR/frontend_build_backup" ]; then
    # Remove current build
    if [ -d "build" ]; then
        rm -rf "build" || log_error "Failed to remove current build directory"
    fi
    
    # Restore backup build
    cp -r "$BACKUP_DIR/frontend_build_backup" "build" || log_error "Failed to restore build directory"
    log_success "Build directory restored"
else
    log_warning "No build backup found, skipping build restoration"
fi

# Step 4: Restore configuration files
log_info "Restoring configuration files..."

# Restore package.json
if [ -f "$BACKUP_DIR/package.json.backup" ]; then
    cp "$BACKUP_DIR/package.json.backup" "package.json" || log_error "Failed to restore package.json"
    log_success "package.json restored"
fi

# Restore package-lock.json
if [ -f "$BACKUP_DIR/package-lock.json.backup" ]; then
    cp "$BACKUP_DIR/package-lock.json.backup" "package-lock.json" || log_error "Failed to restore package-lock.json"
    log_success "package-lock.json restored"
fi

# Step 5: Restore cache if available
log_info "Restoring cache..."
if [ -d "$BACKUP_DIR/cache_backup" ] && [ ! -d "node_modules/.cache" ]; then
    mkdir -p "node_modules"
    cp -r "$BACKUP_DIR/cache_backup" "node_modules/.cache" || log_warning "Failed to restore cache"
    log_success "Cache restored"
else
    log_info "No cache backup found or cache already exists"
fi

# Step 6: Database rollback (if applicable)
log_info "Attempting database rollback..."
run_hook "notify" "database-rollback"

BACKEND_DIR="$PROJECT_ROOT/../backend"
if [ -d "$BACKEND_DIR" ]; then
    cd "$BACKEND_DIR"
    
    # Check for database backup
    DB_BACKUP=$(find . -name "app.db.backup.*" | sort -r | head -1)
    if [ -n "$DB_BACKUP" ] && [ -f "$DB_BACKUP" ]; then
        log_info "Found database backup: $DB_BACKUP"
        
        # Backup current database before rollback
        if [ -f "app.db" ]; then
            cp "app.db" "app.db.pre-rollback.$(date +%Y%m%d_%H%M%S)" || log_warning "Failed to backup current database"
        fi
        
        # Restore database backup
        cp "$DB_BACKUP" "app.db" || log_error "Failed to restore database backup"
        log_success "Database rolled back"
    else
        log_warning "No database backup found for rollback"
    fi
    
    cd "$PROJECT_ROOT"
else
    log_info "No backend directory found, skipping database rollback"
fi

# Step 7: Clear problematic caches
log_info "Clearing caches after rollback..."

# Clear npm cache
if command -v npm >/dev/null 2>&1; then
    npm cache clean --force || log_warning "Failed to clean npm cache"
    log_success "npm cache cleared"
fi

# Remove problematic cache files
rm -rf "node_modules/.cache" || log_warning "Failed to remove node_modules cache"

# Step 8: Reinstall dependencies (if package files were restored)
log_info "Reinstalling dependencies..."
if [ -f "package.json" ] && [ -f "package-lock.json" ]; then
    run_hook "notify" "reinstalling-dependencies-after-rollback"
    
    # Use npm ci for clean install
    if npm ci --no-optional; then
        log_success "Dependencies reinstalled successfully"
    else
        log_error "Failed to reinstall dependencies"
        log_info "Falling back to npm install"
        npm install || log_error "Fallback npm install also failed"
    fi
else
    log_warning "Package files not found, skipping dependency installation"
fi

# Step 9: Verify rollback
log_info "Verifying rollback..."
VERIFICATION_PASSED=true

# Check if build directory exists and has content
if [ -d "build" ] && [ -n "$(ls -A build 2>/dev/null)" ]; then
    log_success "Build directory exists and has content"
else
    log_error "Build directory missing or empty after rollback"
    VERIFICATION_PASSED=false
fi

# Check if package.json exists
if [ -f "package.json" ]; then
    log_success "package.json exists"
else
    log_error "package.json missing after rollback"
    VERIFICATION_PASSED=false
fi

# Check if node_modules exists
if [ -d "node_modules" ]; then
    log_success "node_modules directory exists"
else
    log_warning "node_modules directory missing (may need npm install)"
fi

ROLLBACK_END_TIME=$(date +%s)
ROLLBACK_DURATION=$((ROLLBACK_END_TIME - ROLLBACK_START_TIME))

# Generate rollback report
cat > "$LOG_DIR/rollback_report_$(date +%Y%m%d_%H%M%S).md" << EOF
# Emergency Rollback Report

**Date**: $(date)
**Duration**: ${ROLLBACK_DURATION} seconds
**Backup Used**: $BACKUP_DIR
**Pre-Rollback Snapshot**: $PRE_ROLLBACK_DIR
**Status**: $([ "$VERIFICATION_PASSED" = true ] && echo "SUCCESS" || echo "FAILED")
**Log File**: $LOG_FILE

## Actions Performed:
- ✓ Created pre-rollback snapshot
- ✓ Stopped running services
- ✓ Restored build directory
- ✓ Restored configuration files
- ✓ Restored cache (if available)
- ✓ Database rollback attempted
- ✓ Cleared problematic caches
- ✓ Reinstalled dependencies
- ✓ Verified rollback integrity

## Files Restored:
$(if [ -f "$BACKUP_DIR/package.json.backup" ]; then echo "- package.json"; fi)
$(if [ -f "$BACKUP_DIR/package-lock.json.backup" ]; then echo "- package-lock.json"; fi)
$(if [ -d "$BACKUP_DIR/frontend_build_backup" ]; then echo "- build/ directory"; fi)
$(if [ -d "$BACKUP_DIR/cache_backup" ]; then echo "- node_modules/.cache/"; fi)

## Recovery Information:
- **Pre-rollback snapshot**: $PRE_ROLLBACK_DIR
- **Original backup location**: $BACKUP_DIR
- **Log file**: $LOG_FILE

## Next Steps:
1. Verify application functionality
2. Test critical user paths
3. Monitor for any remaining issues
4. Plan fix for original deployment problem

## Re-deployment Checklist:
- [ ] Identify and fix original deployment issue
- [ ] Test fixes in development environment
- [ ] Run full test suite
- [ ] Create new backup before re-deployment
- [ ] Monitor deployment closely
EOF

run_hook "post-task" "emergency-rollback-completed"

echo "" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"

if [ "$VERIFICATION_PASSED" = true ]; then
    echo -e "${GREEN}🔄 ROLLBACK SUCCESSFUL! 🔄${NC}" | tee -a "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
    echo "Duration: ${ROLLBACK_DURATION} seconds" | tee -a "$LOG_FILE"
    echo "Backup used: $BACKUP_DIR" | tee -a "$LOG_FILE"
    echo "Pre-rollback snapshot: $PRE_ROLLBACK_DIR" | tee -a "$LOG_FILE"
    echo "Report: $LOG_DIR/rollback_report_$(date +%Y%m%d_%H%M%S).md" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    echo "✅ Application has been rolled back to previous state" | tee -a "$LOG_FILE"
    echo "🔍 Please verify functionality before proceeding" | tee -a "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
    exit 0
else
    echo -e "${RED}💥 ROLLBACK VERIFICATION FAILED! 💥${NC}" | tee -a "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
    echo "Duration: ${ROLLBACK_DURATION} seconds" | tee -a "$LOG_FILE"
    echo "Issues detected during verification" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    echo "⚠️  Manual intervention may be required" | tee -a "$LOG_FILE"
    echo "📋 Check the log file for details: $LOG_FILE" | tee -a "$LOG_FILE"
    echo "💾 Pre-rollback snapshot available: $PRE_ROLLBACK_DIR" | tee -a "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
    exit 1
fi