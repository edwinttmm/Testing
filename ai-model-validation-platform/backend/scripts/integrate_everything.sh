#!/bin/bash

################################################################################
# One-Click Integration Script
# Purpose: Complete backend integration in a single command
# Usage: ./integrate_everything.sh [--dry-run] [--skip-backup]
# Created: 2025-11-19
################################################################################

set -e  # Exit on any error
set -u  # Exit on undefined variable

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
DRY_RUN=false
SKIP_BACKUP=false
LOG_FILE="$BACKEND_DIR/integration_$(date +%Y%m%d_%H%M%S).log"

################################################################################
# Parse Arguments
################################################################################

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run       Show what would be done without making changes"
            echo "  --skip-backup   Skip backup creation (not recommended)"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

################################################################################
# Logging Functions
################################################################################

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${MAGENTA}[ℹ]${NC} $1" | tee -a "$LOG_FILE"
}

################################################################################
# Banner
################################################################################

show_banner() {
    cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   AI Model Validation Platform                                ║
║   Backend Integration - One-Click Setup                       ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo ""
    log_info "Started at: $(date)"
    log_info "Backend directory: $BACKEND_DIR"
    log_info "Log file: $LOG_FILE"
    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN MODE - No changes will be made"
    fi
    echo ""
}

################################################################################
# Pre-flight Checks
################################################################################

preflight_checks() {
    log_step "Running pre-flight checks..."

    local errors=0

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        ((errors++))
    else
        log_success "Python 3 found: $(python3 --version)"
    fi

    # Check backend directory
    if [ ! -f "$BACKEND_DIR/main.py" ]; then
        log_error "main.py not found - are you in the correct directory?"
        ((errors++))
    else
        log_success "main.py found"
    fi

    # Check virtual environment
    if [ ! -d "$BACKEND_DIR/venv" ]; then
        log_warning "Virtual environment not found"
        if [ "$DRY_RUN" = false ]; then
            log_info "Creating virtual environment..."
            python3 -m venv "$BACKEND_DIR/venv"
            log_success "Virtual environment created"
        fi
    else
        log_success "Virtual environment found"
    fi

    # Check git
    if command -v git &> /dev/null; then
        log_success "Git found: $(git --version)"
    else
        log_warning "Git not found - patches may not be applicable"
    fi

    if [ $errors -gt 0 ]; then
        log_error "$errors critical error(s) found - aborting"
        exit 1
    fi

    log_success "Pre-flight checks passed"
}

################################################################################
# Create Backup
################################################################################

create_backup() {
    if [ "$SKIP_BACKUP" = true ]; then
        log_warning "Skipping backup (--skip-backup flag set)"
        return
    fi

    log_step "Creating backup..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would create backup in backups/"
        return
    fi

    BACKUP_DIR="$BACKEND_DIR/backups/integration_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    # Backup main files
    log_info "Backing up main.py..."
    cp "$BACKEND_DIR/main.py" "$BACKUP_DIR/main.py.bak"

    # Backup database if exists
    if [ -f "$BACKEND_DIR/validation_platform.db" ]; then
        log_info "Backing up database..."
        cp "$BACKEND_DIR/validation_platform.db" "$BACKUP_DIR/validation_platform.db.bak"
    fi

    # Backup src directory
    log_info "Backing up src/ directory..."
    tar -czf "$BACKUP_DIR/src_backup.tar.gz" -C "$BACKEND_DIR" src/ 2>/dev/null || true

    # Save backup location
    echo "$BACKUP_DIR" > "$BACKEND_DIR/.last_backup"

    log_success "Backup created at: $BACKUP_DIR"
}

################################################################################
# Install Dependencies
################################################################################

install_dependencies() {
    log_step "Installing/verifying dependencies..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would install dependencies from requirements.txt"
        return
    fi

    cd "$BACKEND_DIR"
    source venv/bin/activate

    if [ -f "requirements.txt" ]; then
        log_info "Installing dependencies..."
        pip install -q -r requirements.txt
        log_success "Dependencies installed"
    else
        log_warning "requirements.txt not found"
    fi
}

################################################################################
# Apply Patches
################################################################################

apply_patches() {
    log_step "Applying integration patches..."

    PATCHES_DIR="$BACKEND_DIR/patches"

    if [ ! -d "$PATCHES_DIR" ] || [ -z "$(ls -A $PATCHES_DIR 2>/dev/null)" ]; then
        log_warning "No patches found in $PATCHES_DIR"
        log_warning "This script will be populated with specific patches after agent findings"
        return
    fi

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would apply patches from $PATCHES_DIR"
        return
    fi

    cd "$BACKEND_DIR"

    for patch_file in "$PATCHES_DIR"/*.patch; do
        if [ -f "$patch_file" ]; then
            log_info "Applying $(basename $patch_file)..."
            if git apply "$patch_file" 2>&1 | tee -a "$LOG_FILE"; then
                log_success "Applied $(basename $patch_file)"
            else
                log_error "Failed to apply $(basename $patch_file)"
                log_warning "You may need to apply this patch manually"
            fi
        fi
    done
}

################################################################################
# Run Database Migrations
################################################################################

run_migrations() {
    log_step "Running database migrations..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run database migrations"
        return
    fi

    cd "$BACKEND_DIR"
    source venv/bin/activate

    # Check if Alembic is available
    if command -v alembic &> /dev/null; then
        log_info "Running Alembic migrations..."
        alembic upgrade head 2>&1 | tee -a "$LOG_FILE" || {
            log_warning "Alembic migration failed or not configured"
        }
    else
        log_warning "Alembic not found - skipping migrations"
        log_info "Will be populated with specific migration steps after agent findings"
    fi
}

################################################################################
# Fix Router Registrations
################################################################################

fix_routers() {
    log_step "Fixing router registrations..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would fix router registrations in main.py"
        return
    fi

    log_warning "Router fixes not yet defined - waiting for agent findings"
    log_info "This section will be populated with specific router registration fixes"
}

################################################################################
# Update Service Initializations
################################################################################

update_services() {
    log_step "Updating service initializations..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would update service initializations"
        return
    fi

    log_warning "Service updates not yet defined - waiting for agent findings"
    log_info "This section will be populated with specific service initialization fixes"
}

################################################################################
# Run Verification
################################################################################

run_verification() {
    log_step "Running integration verification..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run verification script"
        return
    fi

    if [ -f "$SCRIPT_DIR/verify_integration.py" ]; then
        log_info "Running verification script..."
        python3 "$SCRIPT_DIR/verify_integration.py" | tee -a "$LOG_FILE" || {
            log_warning "Verification script reported issues"
            return 1
        }
    else
        log_warning "Verification script not found"
    fi
}

################################################################################
# Test Backend Start
################################################################################

test_backend_start() {
    log_step "Testing backend startup..."

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would test backend startup"
        return
    fi

    cd "$BACKEND_DIR"
    source venv/bin/activate

    log_info "Starting backend server for 10 seconds..."

    # Start backend in background
    timeout 10s python3 main.py > /tmp/backend_test_start.log 2>&1 &
    BACKEND_PID=$!

    sleep 3

    # Check if process is still running
    if ps -p $BACKEND_PID > /dev/null; then
        log_success "Backend started successfully"
        kill $BACKEND_PID 2>/dev/null || true
        return 0
    else
        log_error "Backend failed to start"
        log_info "Check logs at /tmp/backend_test_start.log"
        cat /tmp/backend_test_start.log | tail -20
        return 1
    fi
}

################################################################################
# Generate Summary Report
################################################################################

generate_summary() {
    log_step "Generating integration summary..."

    SUMMARY_FILE="$BACKEND_DIR/INTEGRATION_SUMMARY.md"

    cat > "$SUMMARY_FILE" << EOF
# Integration Summary

**Date**: $(date)
**Log File**: $LOG_FILE
**Backup Location**: $(cat $BACKEND_DIR/.last_backup 2>/dev/null || echo "N/A")

## Changes Applied

### Patches Applied
$(if [ -d "$BACKEND_DIR/patches" ]; then ls -1 "$BACKEND_DIR/patches/"*.patch 2>/dev/null | sed 's/^/- /' || echo "- None"; else echo "- None"; fi)

### Database Migrations
- Migration status: $(alembic current 2>/dev/null || echo "N/A")

### Router Registrations
- Status: See verification report

### Service Initializations
- Status: See verification report

## Verification Results

See detailed verification results in:
- \`integration_verification_results.json\`
- Log file: \`$LOG_FILE\`

## Next Steps

1. **Start Backend**:
   \`\`\`bash
   cd $BACKEND_DIR
   source venv/bin/activate
   python3 main.py
   \`\`\`

2. **Test Endpoints**:
   \`\`\`bash
   curl http://localhost:8000/api/health
   # Test other endpoints as needed
   \`\`\`

3. **Update Frontend**:
   - See \`docs/FRONTEND_REQUIREMENTS.md\` for frontend changes

4. **Deploy**:
   - Follow \`DEPLOYMENT_INTEGRATION_CHECKLIST.md\`

## Rollback Instructions

If you need to rollback:

\`\`\`bash
BACKUP_DIR="$(cat $BACKEND_DIR/.last_backup)"
cp \$BACKUP_DIR/main.py.bak ./main.py
cp \$BACKUP_DIR/validation_platform.db.bak ./validation_platform.db
tar -xzf \$BACKUP_DIR/src_backup.tar.gz
\`\`\`

Then restart the backend.

## Support

- Integration documentation: \`INTEGRATION_FIXES.md\`
- Deployment checklist: \`DEPLOYMENT_INTEGRATION_CHECKLIST.md\`
- Architecture docs: \`docs/architecture_design_document.md\`

EOF

    log_success "Summary saved to: $SUMMARY_FILE"
}

################################################################################
# Main Execution
################################################################################

main() {
    show_banner

    # Execute all steps
    preflight_checks
    echo ""

    create_backup
    echo ""

    install_dependencies
    echo ""

    apply_patches
    echo ""

    run_migrations
    echo ""

    fix_routers
    echo ""

    update_services
    echo ""

    run_verification
    VERIFICATION_STATUS=$?
    echo ""

    if [ "$DRY_RUN" = false ] && [ $VERIFICATION_STATUS -eq 0 ]; then
        test_backend_start
        echo ""
    fi

    generate_summary
    echo ""

    # Final status
    echo ""
    log "╔═══════════════════════════════════════════════════════════════╗"
    if [ $VERIFICATION_STATUS -eq 0 ]; then
        log_success "Integration completed successfully!"
    else
        log_warning "Integration completed with warnings"
        log_info "Review the verification report for details"
    fi
    log "╚═══════════════════════════════════════════════════════════════╝"
    echo ""

    log_info "Summary: $BACKEND_DIR/INTEGRATION_SUMMARY.md"
    log_info "Log file: $LOG_FILE"
    if [ "$SKIP_BACKUP" = false ]; then
        log_info "Backup: $(cat $BACKEND_DIR/.last_backup 2>/dev/null || echo 'N/A')"
    fi
    echo ""

    log "Next steps:"
    log "1. Review integration summary"
    log "2. Start backend: python3 main.py"
    log "3. Test endpoints manually"
    log "4. Update frontend (see docs/FRONTEND_REQUIREMENTS.md)"
    log "5. Deploy using checklist (DEPLOYMENT_INTEGRATION_CHECKLIST.md)"
}

# Error handler
trap 'log_error "Script failed at line $LINENO"; exit 1' ERR

# Run main
main "$@"
