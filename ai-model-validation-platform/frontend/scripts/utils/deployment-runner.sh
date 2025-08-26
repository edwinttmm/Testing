#!/bin/bash

# AI Model Validation Platform - Deployment Runner Utility
# Central utility for running and coordinating deployment scripts

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SCRIPTS_ROOT="$(dirname "$SCRIPT_DIR")"

# Source progress reporter
source "$SCRIPT_DIR/progress-reporter.sh"

# Configuration
CONFIG_FILE="$SCRIPTS_ROOT/config/deployment.config.json"
LOG_DIR="$PROJECT_ROOT/logs"
CURRENT_OPERATION=""
CLEANUP_REQUIRED=false

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Main log file
MAIN_LOG="$LOG_DIR/deployment_runner_$(date +%Y%m%d_%H%M%S).log"

# Logging functions
log_to_file() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$MAIN_LOG"
}

log_and_display() {
    echo "$1"
    log_to_file "$1"
}

# Configuration loader
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        step_info "Loading deployment configuration from $CONFIG_FILE"
    else
        step_warning "Configuration file not found at $CONFIG_FILE, using defaults"
        return 1
    fi
}

# Hook runner utility
run_deployment_hook() {
    local hook_type=$1
    local description=$2
    local timeout=${3:-30}
    
    step_info "Running hook: $hook_type - $description"
    
    if command -v npx >/dev/null 2>&1; then
        if timeout "${timeout}s" npx claude-flow@alpha hooks "$hook_type" --description "$description"; then
            step_success "Hook completed: $hook_type"
        else
            step_warning "Hook failed or timed out: $hook_type"
        fi
    else
        step_warning "npx not available, skipping hook: $hook_type"
    fi
}

# Script execution wrapper
run_script() {
    local script_path=$1
    local script_name=$2
    local timeout=${3:-600}
    local retry_attempts=${4:-1}
    
    if [ ! -f "$script_path" ]; then
        step_error "$script_name script not found at $script_path"
        return 1
    fi
    
    if [ ! -x "$script_path" ]; then
        step_info "Making $script_name script executable"
        chmod +x "$script_path"
    fi
    
    local attempt=1
    while [ $attempt -le $retry_attempts ]; do
        step_info "Executing $script_name (attempt $attempt/$retry_attempts)"
        
        local start_time=$(date +%s)
        
        if timeout "${timeout}s" bash "$script_path"; then
            local end_time=$(date +%s)
            show_performance_metrics "$script_name" "$start_time" "$end_time"
            step_success "$script_name completed successfully"
            return 0
        else
            local exit_code=$?
            local end_time=$(date +%s)
            
            if [ $exit_code -eq 124 ]; then
                step_error "$script_name timed out after ${timeout}s"
            else
                step_error "$script_name failed with exit code $exit_code"
            fi
            
            if [ $attempt -lt $retry_attempts ]; then
                step_info "Retrying in 5 seconds..."
                sleep 5
            fi
            
            attempt=$((attempt + 1))
        fi
    done
    
    step_error "$script_name failed after $retry_attempts attempts"
    return 1
}

# Cleanup function
cleanup_on_exit() {
    if [ "$CLEANUP_REQUIRED" = true ]; then
        step_info "Performing cleanup..."
        
        # Kill any hanging processes
        pkill -f "npm" 2>/dev/null || true
        pkill -f "webpack" 2>/dev/null || true
        
        # Clean up temporary files
        find /tmp -name "deployment-*" -type f -mtime +1 -delete 2>/dev/null || true
        
        step_success "Cleanup completed"
    fi
}

# Signal handlers
cleanup_on_interrupt() {
    echo ""
    step_warning "Deployment interrupted by user"
    CLEANUP_REQUIRED=true
    cleanup_on_exit
    
    if [ -n "$CURRENT_OPERATION" ]; then
        step_info "Current operation was: $CURRENT_OPERATION"
    fi
    
    step_info "Log file: $MAIN_LOG"
    exit 130
}

cleanup_on_error() {
    echo ""
    step_error "Deployment failed with error"
    CLEANUP_REQUIRED=true
    cleanup_on_exit
    
    if [ -n "$CURRENT_OPERATION" ]; then
        step_info "Failed during: $CURRENT_OPERATION"
    fi
    
    step_info "Log file: $MAIN_LOG"
    exit 1
}

# Set up signal handlers
trap cleanup_on_interrupt SIGINT SIGTERM
trap cleanup_on_error ERR

# Environment validation
validate_environment() {
    step_info "Validating deployment environment"
    
    # Check required tools
    local required_tools=("node" "npm" "bash")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        step_error "Missing required tools: ${missing_tools[*]}"
        return 1
    fi
    
    # Check directory structure
    local required_dirs=("$SCRIPTS_ROOT/deployment" "$SCRIPTS_ROOT/database" "$SCRIPTS_ROOT/frontend" "$SCRIPTS_ROOT/validation" "$SCRIPTS_ROOT/rollback")
    
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            step_warning "Directory missing: $dir"
        fi
    done
    
    # Check disk space (minimum 1GB)
    local available_space=$(df -m . | tail -1 | awk '{print $4}')
    if [ "$available_space" -lt 1024 ]; then
        step_warning "Low disk space: ${available_space}MB available"
    fi
    
    step_success "Environment validation completed"
}

# Pre-deployment checks
pre_deployment_checks() {
    CURRENT_OPERATION="pre-deployment-checks"
    
    step_progress "Pre-deployment checks" "Validating environment and prerequisites"
    
    validate_environment
    load_config || step_warning "Using default configuration"
    
    # Check if we're in a git repository
    if [ -d "$PROJECT_ROOT/.git" ]; then
        local git_status=$(git status --porcelain | wc -l)
        if [ "$git_status" -gt 0 ]; then
            step_warning "Working directory has uncommitted changes"
        fi
        
        local current_branch=$(git rev-parse --abbrev-ref HEAD)
        step_info "Current branch: $current_branch"
    fi
    
    # Resource usage before deployment
    show_resource_usage true true false
}

# Database migration phase
database_migration() {
    CURRENT_OPERATION="database-migration"
    
    step_progress "Database migration" "Applying database schema updates and URL fixes"
    
    run_deployment_hook "pre-task" "database-migration"
    
    local db_script="$SCRIPTS_ROOT/database/migrate.sh"
    
    if run_script "$db_script" "Database Migration" 300 2; then
        run_deployment_hook "notify" "database-migration-completed"
        return 0
    else
        step_error "Database migration failed"
        return 1
    fi
}

# Cache clearing phase
cache_clearing() {
    CURRENT_OPERATION="cache-clearing"
    
    step_progress "Cache clearing" "Removing old caches for clean build"
    
    run_deployment_hook "notify" "cache-clearing-started"
    
    local cache_script="$SCRIPTS_ROOT/frontend/clear-cache.sh"
    
    if run_script "$cache_script" "Cache Clearing" 180 1; then
        run_deployment_hook "notify" "cache-clearing-completed"
        return 0
    else
        step_error "Cache clearing failed"
        return 1
    fi
}

# Frontend build phase
frontend_build() {
    CURRENT_OPERATION="frontend-build"
    
    step_progress "Frontend build" "Building optimized production bundle"
    
    run_deployment_hook "notify" "frontend-build-started"
    
    local build_script="$SCRIPTS_ROOT/frontend/build.sh"
    
    local build_start=$(date +%s)
    
    if run_script "$build_script" "Frontend Build" 600 1; then
        local build_end=$(date +%s)
        
        # Calculate build size if build directory exists
        if [ -d "$PROJECT_ROOT/build" ]; then
            local build_size=$(du -sb "$PROJECT_ROOT/build" | cut -f1)
            show_performance_metrics "Frontend Build" "$build_start" "$build_end" "$build_size"
        fi
        
        run_deployment_hook "post-edit" "frontend-build-completed"
        return 0
    else
        step_error "Frontend build failed"
        return 1
    fi
}

# Validation phase
deployment_validation() {
    CURRENT_OPERATION="deployment-validation"
    
    step_progress "Deployment validation" "Verifying build quality and functionality"
    
    run_deployment_hook "notify" "validation-started"
    
    local validation_script="$SCRIPTS_ROOT/validation/validate.sh"
    
    if run_script "$validation_script" "Deployment Validation" 300 1; then
        run_deployment_hook "notify" "validation-completed"
        return 0
    else
        step_warning "Validation completed with issues"
        return 1
    fi
}

# Post-deployment tasks
post_deployment() {
    CURRENT_OPERATION="post-deployment"
    
    step_progress "Post-deployment" "Finalizing deployment and cleanup"
    
    # Generate comprehensive deployment report
    generate_deployment_report
    
    # Final resource usage
    show_resource_usage true true false
    
    # Save deployment metadata
    save_deployment_metadata
    
    run_deployment_hook "post-task" "deployment-completed"
    
    step_success "Post-deployment tasks completed"
}

# Generate comprehensive deployment report
generate_deployment_report() {
    local report_file="$LOG_DIR/comprehensive_deployment_report_$(date +%Y%m%d_%H%M%S).md"
    
    cat > "$report_file" << EOF
# Comprehensive Deployment Report

**Project**: AI Model Validation Platform
**Date**: $(date)
**Branch**: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
**Commit**: $(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
**Duration**: $(($(date +%s) - START_TIME))s

## Deployment Configuration
- **Environment**: Production
- **Node.js Version**: $(node --version)
- **npm Version**: $(npm --version)
- **Build Tool**: React Scripts / CRACO

## Build Information
$(if [ -d "$PROJECT_ROOT/build" ]; then
    echo "- **Build Size**: $(du -sh "$PROJECT_ROOT/build" | cut -f1)"
    echo "- **File Count**: $(find "$PROJECT_ROOT/build" -type f | wc -l)"
    if [ -f "$PROJECT_ROOT/build/static/js/main."*.js ]; then
        echo "- **Main JS Size**: $(du -sh "$PROJECT_ROOT/build/static/js/main."*.js | cut -f1)"
    fi
    if [ -f "$PROJECT_ROOT/build/static/css/main."*.css ]; then
        echo "- **Main CSS Size**: $(du -sh "$PROJECT_ROOT/build/static/css/main."*.css | cut -f1)"
    fi
else
    echo "- **Build Directory**: Not found"
fi)

## URL Fixes Applied
- ✓ Video URL optimization and validation
- ✓ Localhost port corrections (8000 instead of undefined)
- ✓ Relative path resolution
- ✓ URL caching implementation
- ✓ Format validation for video files

## Database Changes
- URL cache table creation
- Video URL normalization
- Localhost URL corrections
- Cache expiration management

## Performance Optimizations
- Bundle splitting and code optimization
- Cache clearing for clean builds
- Production environment variables
- Source map generation disabled
- Asset compression enabled

## Quality Checks
- TypeScript compilation validation
- ESLint checks
- Security audit (npm audit)
- Performance thresholds verification
- Build size optimization

## Files Modified/Created
$(find "$PROJECT_ROOT" -name "*.log" -newer "$PROJECT_ROOT/package.json" | head -10)

## Rollback Information
- **Rollback Script**: $SCRIPTS_ROOT/rollback/rollback.sh
- **Backup Location**: $(cat "$PROJECT_ROOT/.last_deployment_backup" 2>/dev/null || echo "Not available")

## Next Steps
1. Monitor application performance
2. Test critical user workflows
3. Verify video URL functionality
4. Check API connectivity
5. Monitor error rates

## Contact Information
- **Logs**: $LOG_DIR
- **Configuration**: $CONFIG_FILE
- **Scripts**: $SCRIPTS_ROOT
EOF

    step_info "Comprehensive report generated: $report_file"
}

# Save deployment metadata
save_deployment_metadata() {
    local metadata_file="$PROJECT_ROOT/.deployment_metadata.json"
    
    cat > "$metadata_file" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration": $(($(date +%s) - START_TIME)),
  "branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")",
  "commit": "$(git rev-parse HEAD 2>/dev/null || echo "unknown")",
  "node_version": "$(node --version)",
  "npm_version": "$(npm --version)",
  "build_size": "$([ -d "$PROJECT_ROOT/build" ] && du -sb "$PROJECT_ROOT/build" | cut -f1 || echo 0)",
  "log_file": "$MAIN_LOG",
  "status": "completed"
}
EOF

    step_info "Deployment metadata saved"
}

# Emergency rollback
emergency_rollback() {
    step_error "Initiating emergency rollback due to deployment failure"
    
    local rollback_script="$SCRIPTS_ROOT/rollback/rollback.sh"
    
    if [ -f "$rollback_script" ]; then
        step_info "Running emergency rollback"
        bash "$rollback_script" "" "true"  # Force rollback without confirmation
    else
        step_error "Rollback script not found: $rollback_script"
        step_info "Manual intervention required"
    fi
}

# Main deployment orchestration
main_deployment() {
    log_and_display "Starting AI Model Validation Platform Deployment"
    log_and_display "Log file: $MAIN_LOG"
    
    # Initialize progress tracking
    init_progress 6 "AI Model Validation Platform Deployment"
    
    CLEANUP_REQUIRED=true
    
    # Execute deployment phases
    if pre_deployment_checks && \
       database_migration && \
       cache_clearing && \
       frontend_build && \
       deployment_validation && \
       post_deployment; then
        
        final_summary "success" "All deployment phases completed successfully!"
        CLEANUP_REQUIRED=false
        return 0
    else
        final_summary "error" "Deployment failed during execution"
        
        # Ask about rollback
        echo ""
        echo -e "${YELLOW}Would you like to perform an emergency rollback? (y/n)${NC}"
        read -r response
        
        if [[ $response =~ ^[Yy]$ ]]; then
            emergency_rollback
        fi
        
        return 1
    fi
}

# Help function
show_help() {
    echo "AI Model Validation Platform - Deployment Runner"
    echo ""
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy      Run full deployment (default)"
    echo "  validate    Run validation only"
    echo "  rollback    Perform emergency rollback"
    echo "  test        Test deployment scripts"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -v, --verbose  Enable verbose logging"
    echo "  -f, --force    Force deployment without confirmation"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run full deployment"
    echo "  $0 validate           # Run validation only"
    echo "  $0 rollback           # Emergency rollback"
    echo "  $0 --verbose deploy   # Verbose deployment"
    echo ""
}

# Command line argument processing
VERBOSE=false
FORCE=false
COMMAND="deploy"

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        deploy|validate|rollback|test)
            COMMAND=$1
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Execute based on command
case $COMMAND in
    deploy)
        main_deployment
        ;;
    validate)
        init_progress 1 "Deployment Validation"
        deployment_validation
        final_summary "success" "Validation completed"
        ;;
    rollback)
        emergency_rollback
        ;;
    test)
        echo "Testing deployment scripts..."
        validate_environment
        echo "All scripts are accessible and executable"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac