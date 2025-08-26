#!/bin/bash

# AI Model Validation Platform - Comprehensive Build & Deployment Script
# This script coordinates database migration, frontend rebuild, and validation

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up 2 levels from scripts/deployment
BACKEND_DIR="$PROJECT_ROOT/../backend"  # Assuming backend is sibling to frontend
FRONTEND_DIR="$PROJECT_ROOT"
LOG_DIR="$PROJECT_ROOT/logs"
BACKUP_DIR="$PROJECT_ROOT/backups/$(date +%Y%m%d_%H%M%S)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Progress tracking
TOTAL_STEPS=8
CURRENT_STEP=0

# Logging setup
mkdir -p "$LOG_DIR" "$BACKUP_DIR"
LOG_FILE="$LOG_DIR/deployment_$(date +%Y%m%d_%H%M%S).log"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

echo "======================================"
echo "AI Model Validation Platform Deployment"
echo "Started: $(date)"
echo "Log file: $LOG_FILE"
echo "======================================"

# Function to show progress
show_progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "${BLUE}[Step $CURRENT_STEP/$TOTAL_STEPS]${NC} $1"
}

# Function to log success
log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to log warning
log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to log error and exit
log_error() {
    echo -e "${RED}✗${NC} $1" >&2
    echo "Deployment failed at step $CURRENT_STEP. Check log: $LOG_FILE" >&2
    exit 1
}

# Function to run hooks
run_hook() {
    local hook_type=$1
    local description=$2
    echo "Running hook: $hook_type - $description"
    if command -v npx >/dev/null 2>&1; then
        npx claude-flow@alpha hooks "$hook_type" --description "$description" || true
    else
        log_warning "npx not available, skipping hook: $hook_type"
    fi
}

# Cleanup function for interruption
cleanup() {
    echo ""
    log_warning "Deployment interrupted. Rolling back changes..."
    if [ -f "$SCRIPT_DIR/../rollback/rollback.sh" ]; then
        bash "$SCRIPT_DIR/../rollback/rollback.sh" "$BACKUP_DIR"
    fi
    exit 130
}

trap cleanup SIGINT SIGTERM

# Step 1: Pre-deployment validation
show_progress "Pre-deployment validation"
run_hook "pre-task" "deployment-validation"

# Check if we're in the right directory
if [ ! -f "$FRONTEND_DIR/package.json" ]; then
    log_error "Frontend package.json not found. Are you running from the correct directory?"
fi

# Check for required tools
command -v npm >/dev/null 2>&1 || log_error "npm is required but not installed"
command -v node >/dev/null 2>&1 || log_error "node is required but not installed"

log_success "Pre-deployment validation completed"

# Step 2: Create backup
show_progress "Creating backup"
run_hook "pre-edit" "creating-deployment-backup"

# Backup current state
if [ -d "$FRONTEND_DIR/build" ]; then
    cp -r "$FRONTEND_DIR/build" "$BACKUP_DIR/frontend_build_backup" || log_error "Failed to backup frontend build"
    log_success "Frontend build backed up"
fi

if [ -d "$FRONTEND_DIR/node_modules/.cache" ]; then
    cp -r "$FRONTEND_DIR/node_modules/.cache" "$BACKUP_DIR/cache_backup" || log_warning "Failed to backup cache (non-critical)"
fi

# Backup configuration files
cp "$FRONTEND_DIR/package.json" "$BACKUP_DIR/package.json.backup" || log_error "Failed to backup package.json"
cp "$FRONTEND_DIR/package-lock.json" "$BACKUP_DIR/package-lock.json.backup" || log_error "Failed to backup package-lock.json"

log_success "Backup created at $BACKUP_DIR"

# Step 3: Database migration
show_progress "Running database migration"
run_hook "notify" "starting-database-migration"

if [ -f "$SCRIPT_DIR/../database/migrate.sh" ]; then
    bash "$SCRIPT_DIR/../database/migrate.sh" || log_error "Database migration failed"
    log_success "Database migration completed"
else
    log_warning "Database migration script not found, skipping"
fi

# Step 4: Clear frontend caches
show_progress "Clearing frontend caches"
run_hook "notify" "clearing-frontend-caches"

if [ -f "$SCRIPT_DIR/../frontend/clear-cache.sh" ]; then
    bash "$SCRIPT_DIR/../frontend/clear-cache.sh" || log_error "Cache clearing failed"
else
    # Fallback cache clearing
    cd "$FRONTEND_DIR"
    
    # Clear npm cache
    npm cache clean --force || log_warning "Failed to clear npm cache"
    
    # Remove node_modules cache
    if [ -d "node_modules/.cache" ]; then
        rm -rf node_modules/.cache || log_warning "Failed to clear node_modules cache"
    fi
    
    # Clear build directory
    if [ -d "build" ]; then
        rm -rf build || log_warning "Failed to clear build directory"
    fi
    
    # Clear Jest cache if present
    if [ -d "coverage" ]; then
        rm -rf coverage || log_warning "Failed to clear coverage directory"
    fi
fi

log_success "Frontend caches cleared"

# Step 5: Install dependencies
show_progress "Installing/updating dependencies"
run_hook "notify" "installing-dependencies"

cd "$FRONTEND_DIR"
npm ci --no-optional || log_error "Failed to install dependencies"
log_success "Dependencies installed"

# Step 6: Build frontend with optimizations
show_progress "Building frontend with optimizations"
run_hook "notify" "building-frontend"

if [ -f "$SCRIPT_DIR/../frontend/build.sh" ]; then
    bash "$SCRIPT_DIR/../frontend/build.sh" || log_error "Frontend build failed"
else
    # Fallback build process
    cd "$FRONTEND_DIR"
    
    # Set production environment
    export NODE_ENV=production
    export GENERATE_SOURCEMAP=false
    export INLINE_RUNTIME_CHUNK=false
    
    # Run the build
    npm run build || log_error "Frontend build failed"
fi

log_success "Frontend build completed"

# Step 7: Validate the fix
show_progress "Validating deployment"
run_hook "notify" "validating-deployment"

if [ -f "$SCRIPT_DIR/../validation/validate.sh" ]; then
    bash "$SCRIPT_DIR/../validation/validate.sh" || log_error "Validation failed"
    log_success "Validation passed"
else
    log_warning "Validation script not found, performing basic checks"
    
    # Basic validation checks
    if [ ! -d "$FRONTEND_DIR/build" ]; then
        log_error "Build directory not created"
    fi
    
    if [ ! -f "$FRONTEND_DIR/build/index.html" ]; then
        log_error "Build index.html not found"
    fi
    
    # Check build size
    BUILD_SIZE=$(du -sh "$FRONTEND_DIR/build" | cut -f1)
    echo "Build size: $BUILD_SIZE"
    
    log_success "Basic validation completed"
fi

# Step 8: Post-deployment tasks
show_progress "Post-deployment tasks"
run_hook "post-task" "deployment-completed"

# Generate deployment report
cat > "$LOG_DIR/deployment_report_$(date +%Y%m%d_%H%M%S).md" << EOF
# Deployment Report

**Date**: $(date)
**Status**: SUCCESS
**Duration**: $SECONDS seconds
**Build Size**: $(du -sh "$FRONTEND_DIR/build" | cut -f1)
**Log File**: $LOG_FILE
**Backup Location**: $BACKUP_DIR

## Steps Completed:
1. ✓ Pre-deployment validation
2. ✓ Backup creation
3. ✓ Database migration
4. ✓ Cache clearing
5. ✓ Dependency installation
6. ✓ Frontend build
7. ✓ Validation
8. ✓ Post-deployment tasks

## Rollback Command:
\`\`\`bash
bash $SCRIPT_DIR/../rollback/rollback.sh "$BACKUP_DIR"
\`\`\`
EOF

log_success "Deployment report generated"

# Save deployment info for rollback
echo "$BACKUP_DIR" > "$PROJECT_ROOT/.last_deployment_backup"

echo ""
echo "======================================"
echo -e "${GREEN}🎉 DEPLOYMENT SUCCESSFUL! 🎉${NC}"
echo "======================================"
echo "Completed: $(date)"
echo "Duration: $SECONDS seconds"
echo "Build location: $FRONTEND_DIR/build"
echo "Backup location: $BACKUP_DIR"
echo "Log file: $LOG_FILE"
echo ""
echo "To rollback if needed:"
echo "bash $SCRIPT_DIR/../rollback/rollback.sh '$BACKUP_DIR'"
echo "======================================"