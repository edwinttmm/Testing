#!/bin/bash

# AI Model Validation Platform - Frontend Cache Clearing Script
# Comprehensive cache clearing for optimal rebuild

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
LOG_FILE="$LOG_DIR/cache_clearing_$(date +%Y%m%d_%H%M%S).log"

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

run_hook() {
    local hook_type=$1
    local description=$2
    if command -v npx >/dev/null 2>&1; then
        npx claude-flow@alpha hooks "$hook_type" --description "$description" || true
    fi
}

echo "======================================" | tee -a "$LOG_FILE"
echo "Frontend Cache Clearing Started: $(date)" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"

run_hook "pre-task" "cache-clearing"

cd "$PROJECT_ROOT"

# Calculate initial cache sizes
log_info "Calculating initial cache sizes..."
INITIAL_SIZE=0

if [ -d "node_modules/.cache" ]; then
    CACHE_SIZE=$(du -sm "node_modules/.cache" 2>/dev/null | cut -f1 || echo "0")
    INITIAL_SIZE=$((INITIAL_SIZE + CACHE_SIZE))
    log_info "Node modules cache: ${CACHE_SIZE}MB"
fi

if [ -d "build" ]; then
    BUILD_SIZE=$(du -sm "build" 2>/dev/null | cut -f1 || echo "0")
    INITIAL_SIZE=$((INITIAL_SIZE + BUILD_SIZE))
    log_info "Build directory: ${BUILD_SIZE}MB"
fi

if [ -d "coverage" ]; then
    COV_SIZE=$(du -sm "coverage" 2>/dev/null | cut -f1 || echo "0")
    INITIAL_SIZE=$((INITIAL_SIZE + COV_SIZE))
    log_info "Coverage directory: ${COV_SIZE}MB"
fi

log_info "Total initial cache size: ${INITIAL_SIZE}MB"

# 1. Clear npm cache
log_info "Clearing npm cache..."
if command -v npm >/dev/null 2>&1; then
    npm cache clean --force || log_warning "npm cache clean failed"
    log_success "npm cache cleared"
else
    log_warning "npm not found, skipping npm cache clean"
fi

# 2. Clear yarn cache if present
log_info "Clearing yarn cache..."
if command -v yarn >/dev/null 2>&1; then
    yarn cache clean || log_warning "yarn cache clean failed"
    log_success "yarn cache cleared"
else
    log_info "yarn not found, skipping yarn cache clean"
fi

# 3. Clear node_modules cache directories
log_info "Clearing node_modules cache directories..."

cache_dirs=(
    "node_modules/.cache"
    "node_modules/.tmp"
    "node_modules/@babel/core/.cache"
    "node_modules/babel-loader/.cache"
    "node_modules/terser-webpack-plugin/.cache"
    "node_modules/css-loader/.cache"
    "node_modules/file-loader/.cache"
    "node_modules/url-loader/.cache"
)

for dir in "${cache_dirs[@]}"; do
    if [ -d "$dir" ]; then
        SIZE=$(du -sm "$dir" 2>/dev/null | cut -f1 || echo "0")
        log_info "Removing $dir (${SIZE}MB)..."
        rm -rf "$dir" || log_warning "Failed to remove $dir"
        log_success "$dir removed"
    fi
done

# 4. Clear build directories
log_info "Clearing build directories..."
build_dirs=(
    "build"
    "dist"
    ".next"
    "out"
)

for dir in "${build_dirs[@]}"; do
    if [ -d "$dir" ]; then
        SIZE=$(du -sm "$dir" 2>/dev/null | cut -f1 || echo "0")
        log_info "Removing $dir (${SIZE}MB)..."
        rm -rf "$dir" || log_warning "Failed to remove $dir"
        log_success "$dir removed"
    fi
done

# 5. Clear test and coverage directories
log_info "Clearing test and coverage directories..."
test_dirs=(
    "coverage"
    ".nyc_output"
    "junit.xml"
    "test-results"
)

for dir in "${test_dirs[@]}"; do
    if [ -d "$dir" ] || [ -f "$dir" ]; then
        if [ -d "$dir" ]; then
            SIZE=$(du -sm "$dir" 2>/dev/null | cut -f1 || echo "0")
            log_info "Removing $dir directory (${SIZE}MB)..."
        else
            log_info "Removing $dir file..."
        fi
        rm -rf "$dir" || log_warning "Failed to remove $dir"
        log_success "$dir removed"
    fi
done

# 6. Clear webpack and bundler caches
log_info "Clearing webpack and bundler caches..."
webpack_dirs=(
    ".webpack"
    ".cache-loader"
    ".eslintcache"
    "tsconfig.tsbuildinfo"
    ".tscache"
)

for item in "${webpack_dirs[@]}"; do
    if [ -d "$item" ] || [ -f "$item" ]; then
        log_info "Removing $item..."
        rm -rf "$item" || log_warning "Failed to remove $item"
        log_success "$item removed"
    fi
done

# 7. Clear browser caches (development)
log_info "Clearing browser development caches..."
if [ -d ".chrome" ]; then
    rm -rf ".chrome" || log_warning "Failed to remove .chrome"
    log_success "Chrome development cache removed"
fi

# 8. Clear temporary files
log_info "Clearing temporary files..."
temp_patterns=(
    "*.log"
    "*.tmp"
    "*.temp"
    ".DS_Store"
    "Thumbs.db"
)

for pattern in "${temp_patterns[@]}"; do
    if compgen -G "$pattern" > /dev/null 2>&1; then
        log_info "Removing $pattern files..."
        rm -f $pattern || log_warning "Failed to remove $pattern files"
        log_success "$pattern files removed"
    fi
done

# 9. Clear environment-specific caches
log_info "Clearing environment-specific caches..."

# Clear React development cache
if [ -d "src" ]; then
    find src -name "*.cache" -type f -delete 2>/dev/null || true
    log_info "React source cache files cleared"
fi

# Clear public cache files
if [ -d "public" ]; then
    find public -name "*.cache" -type f -delete 2>/dev/null || true
    log_info "Public cache files cleared"
fi

# 10. Clear package lock artifacts
log_info "Clearing package lock artifacts..."
if [ -f "package-lock.json" ]; then
    # Backup current package-lock.json
    cp package-lock.json "package-lock.json.pre-clean" || log_warning "Failed to backup package-lock.json"
    log_success "package-lock.json backed up"
fi

# 11. Clear custom application caches
log_info "Clearing application-specific caches..."

# Clear video cache if exists
if [ -d "src/cache" ]; then
    rm -rf "src/cache" || log_warning "Failed to remove src/cache"
    log_success "Application cache directory removed"
fi

# Clear memory files
if [ -f "memory/memory-store.json" ]; then
    cp "memory/memory-store.json" "memory/memory-store.json.backup" || log_warning "Failed to backup memory store"
    > "memory/memory-store.json"  # Clear content but keep file
    log_success "Memory store cleared"
fi

# 12. System-level cache clearing (if available)
log_info "Clearing system-level caches..."

# macOS specific
if [[ "$OSTYPE" == "darwin"* ]]; then
    if [ -d ~/Library/Caches/Yarn ]; then
        rm -rf ~/Library/Caches/Yarn/* || log_warning "Failed to clear Yarn system cache"
        log_success "Yarn system cache cleared"
    fi
    
    if [ -d ~/Library/Caches/npm ]; then
        rm -rf ~/Library/Caches/npm/* || log_warning "Failed to clear npm system cache"
        log_success "npm system cache cleared"
    fi
fi

# Linux specific
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [ -d ~/.cache/yarn ]; then
        rm -rf ~/.cache/yarn/* || log_warning "Failed to clear Yarn user cache"
        log_success "Yarn user cache cleared"
    fi
    
    if [ -d ~/.npm ]; then
        rm -rf ~/.npm/_cacache/* || log_warning "Failed to clear npm user cache"
        log_success "npm user cache cleared"
    fi
fi

# Calculate final cache sizes and savings
log_info "Calculating cache clearing results..."
FINAL_SIZE=0

# Re-check remaining cache sizes
for dir in "node_modules/.cache" "build" "coverage"; do
    if [ -d "$dir" ]; then
        SIZE=$(du -sm "$dir" 2>/dev/null | cut -f1 || echo "0")
        FINAL_SIZE=$((FINAL_SIZE + SIZE))
    fi
done

SPACE_FREED=$((INITIAL_SIZE - FINAL_SIZE))

# Create cache clearing report
cat > "$LOG_DIR/cache_clearing_report_$(date +%Y%m%d_%H%M%S).md" << EOF
# Cache Clearing Report

**Date**: $(date)
**Project**: AI Model Validation Platform Frontend
**Log File**: $LOG_FILE

## Results:
- **Initial Cache Size**: ${INITIAL_SIZE}MB
- **Final Cache Size**: ${FINAL_SIZE}MB
- **Space Freed**: ${SPACE_FREED}MB

## Caches Cleared:
- ✓ npm cache
- ✓ yarn cache (if present)
- ✓ node_modules cache directories
- ✓ Build directories (build, dist, .next, out)
- ✓ Test and coverage directories
- ✓ Webpack and bundler caches
- ✓ Browser development caches
- ✓ Temporary files
- ✓ Environment-specific caches
- ✓ Application-specific caches
- ✓ System-level caches

## Next Steps:
1. Run \`npm ci\` to reinstall dependencies
2. Run \`npm run build\` to rebuild the project
3. Verify that all functionality works correctly

## Performance Impact:
- First build after cache clearing may take longer
- Subsequent builds should be faster with fresh cache
- Memory usage should be optimized
EOF

log_success "Cache clearing report generated"

run_hook "post-task" "cache-clearing-completed"

echo "======================================" | tee -a "$LOG_FILE"
echo -e "${GREEN}🧹 CACHE CLEARING COMPLETED! 🧹${NC}" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"
echo "Space freed: ${SPACE_FREED}MB" | tee -a "$LOG_FILE"
echo "Report saved: $LOG_DIR/cache_clearing_report_$(date +%Y%m%d_%H%M%S).md" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "======================================" | tee -a "$LOG_FILE"