#!/bin/bash
################################################################################
# HIL Backend Pre-Deployment Validation Script
# Version: 1.0.0
# Description: Comprehensive pre-deployment checks to prevent failed deployments
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
MIN_DISK_SPACE_GB=1
MIN_MEMORY_MB=512
REQUIRED_PYTHON_VERSION="3.8"

# Results tracking
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

################################################################################
# Utility Functions
################################################################################

log_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

log_fail() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((CHECKS_WARNING++))
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

################################################################################
# System Checks
################################################################################

check_disk_space() {
    log_info "Checking disk space..."

    local available_gb=$(df -BG "$BACKEND_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')

    if [ "$available_gb" -lt "$MIN_DISK_SPACE_GB" ]; then
        log_fail "Insufficient disk space: ${available_gb}GB available (minimum: ${MIN_DISK_SPACE_GB}GB)"
        return 1
    else
        log_pass "Sufficient disk space: ${available_gb}GB available"
        return 0
    fi
}

check_memory() {
    log_info "Checking available memory..."

    local available_mb=$(free -m | awk 'NR==2 {print $7}')

    if [ "$available_mb" -lt "$MIN_MEMORY_MB" ]; then
        log_warn "Low available memory: ${available_mb}MB (recommended: ${MIN_MEMORY_MB}MB+)"
        return 0
    else
        log_pass "Sufficient memory: ${available_mb}MB available"
        return 0
    fi
}

check_cpu_load() {
    log_info "Checking CPU load..."

    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cpu_count=$(nproc)

    log_info "Load average: ${load_avg}, CPU cores: ${cpu_count}"
    log_pass "CPU load check completed"
    return 0
}

################################################################################
# Python Environment Checks
################################################################################

check_python_version() {
    log_info "Checking Python version..."

    if ! command -v python3 &> /dev/null; then
        log_fail "Python 3 not found in PATH"
        return 1
    fi

    local python_version=$(python3 --version 2>&1 | awk '{print $2}')
    local major_minor=$(echo "$python_version" | cut -d'.' -f1,2)

    if [ "$(printf '%s\n' "$REQUIRED_PYTHON_VERSION" "$major_minor" | sort -V | head -n1)" != "$REQUIRED_PYTHON_VERSION" ]; then
        log_fail "Python version ${python_version} is below minimum ${REQUIRED_PYTHON_VERSION}"
        return 1
    else
        log_pass "Python version ${python_version} OK"
        return 0
    fi
}

check_python_packages() {
    log_info "Checking required Python packages..."

    cd "$BACKEND_DIR"

    if [ ! -f "requirements.txt" ]; then
        log_warn "requirements.txt not found"
        return 0
    fi

    local missing_packages=()

    # Check critical packages
    local critical_packages=("fastapi" "uvicorn" "sqlalchemy" "pydantic")

    for package in "${critical_packages[@]}"; do
        if ! python3 -c "import $package" 2>/dev/null; then
            missing_packages+=("$package")
        fi
    done

    if [ ${#missing_packages[@]} -gt 0 ]; then
        log_fail "Missing critical packages: ${missing_packages[*]}"
        log_info "Run: pip install -r requirements.txt"
        return 1
    else
        log_pass "All critical Python packages installed"
        return 0
    fi
}

check_python_syntax() {
    log_info "Validating Python syntax..."

    cd "$BACKEND_DIR"

    local python_files=("main.py" "config.py" "database.py" "models.py")
    local syntax_errors=0

    for file in "${python_files[@]}"; do
        if [ -f "$file" ]; then
            if ! python3 -m py_compile "$file" 2>/dev/null; then
                log_fail "Syntax error in $file"
                ((syntax_errors++))
            fi
        fi
    done

    if [ $syntax_errors -eq 0 ]; then
        log_pass "Python syntax validation passed"
        return 0
    else
        log_fail "Found ${syntax_errors} file(s) with syntax errors"
        return 1
    fi
}

################################################################################
# File Structure Checks
################################################################################

check_required_files() {
    log_info "Checking required files..."

    cd "$BACKEND_DIR"

    local required_files=("main.py" "config.py" "database.py" "models.py" "schemas.py")
    local missing_files=()

    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done

    if [ ${#missing_files[@]} -gt 0 ]; then
        log_fail "Missing required files: ${missing_files[*]}"
        return 1
    else
        log_pass "All required files present"
        return 0
    fi
}

check_directory_structure() {
    log_info "Checking directory structure..."

    cd "$BACKEND_DIR"

    local required_dirs=("services" "routers" "api")
    local missing_dirs=()

    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            missing_dirs+=("$dir")
        fi
    done

    if [ ${#missing_dirs[@]} -gt 0 ]; then
        log_warn "Missing directories: ${missing_dirs[*]}"
        return 0
    else
        log_pass "Directory structure OK"
        return 0
    fi
}

check_permissions() {
    log_info "Checking file permissions..."

    cd "$BACKEND_DIR"

    # Check if main.py is readable
    if [ ! -r "main.py" ]; then
        log_fail "main.py is not readable"
        return 1
    fi

    # Check if logs directory is writable
    if [ ! -d "logs" ]; then
        mkdir -p logs 2>/dev/null || {
            log_fail "Cannot create logs directory"
            return 1
        }
    fi

    if [ ! -w "logs" ]; then
        log_fail "logs directory is not writable"
        return 1
    fi

    log_pass "File permissions OK"
    return 0
}

################################################################################
# Database Checks
################################################################################

check_database_accessible() {
    log_info "Checking database accessibility..."

    cd "$BACKEND_DIR"

    local db_file="dev_database.db"

    if [ ! -f "$db_file" ]; then
        log_warn "Database file not found (will be created on first run)"
        return 0
    fi

    # Check if database is locked
    if lsof "$db_file" &> /dev/null; then
        log_warn "Database file is currently in use"
        return 0
    fi

    # Check if database is readable/writable
    if [ ! -r "$db_file" ] || [ ! -w "$db_file" ]; then
        log_fail "Database file permissions issue"
        return 1
    fi

    log_pass "Database accessible"
    return 0
}

check_database_integrity() {
    log_info "Checking database integrity..."

    cd "$BACKEND_DIR"

    local db_file="dev_database.db"

    if [ ! -f "$db_file" ]; then
        log_info "Database does not exist yet (OK for fresh install)"
        return 0
    fi

    # Try to open database and check integrity
    if command -v sqlite3 &> /dev/null; then
        if sqlite3 "$db_file" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_pass "Database integrity check passed"
            return 0
        else
            log_fail "Database integrity check failed"
            return 1
        fi
    else
        log_warn "sqlite3 not available, skipping integrity check"
        return 0
    fi
}

################################################################################
# Network Checks
################################################################################

check_port_available() {
    log_info "Checking if port 8000 is available..."

    if lsof -ti:8000 &> /dev/null; then
        local pid=$(lsof -ti:8000)
        local process=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
        log_warn "Port 8000 is currently in use by PID $pid ($process)"
        log_info "Deployment script will handle port release"
        return 0
    else
        log_pass "Port 8000 is available"
        return 0
    fi
}

check_network_connectivity() {
    log_info "Checking network connectivity..."

    # Check if localhost is reachable
    if ping -c 1 localhost &> /dev/null; then
        log_pass "Localhost is reachable"
        return 0
    else
        log_fail "Cannot reach localhost"
        return 1
    fi
}

################################################################################
# Configuration Checks
################################################################################

check_environment_variables() {
    log_info "Checking environment variables..."

    # Check for .env file
    if [ -f "${BACKEND_DIR}/.env" ]; then
        log_pass ".env file found"
    else
        log_warn ".env file not found (may use defaults)"
    fi

    return 0
}

check_config_files() {
    log_info "Checking configuration files..."

    cd "$BACKEND_DIR"

    if [ -f "config.py" ]; then
        # Validate config.py syntax
        if python3 -c "import config" 2>/dev/null; then
            log_pass "config.py is valid"
            return 0
        else
            log_fail "config.py has errors"
            return 1
        fi
    else
        log_fail "config.py not found"
        return 1
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    echo "=========================================="
    echo "HIL Backend Pre-Deployment Checks"
    echo "=========================================="
    echo "Time: $(date)"
    echo "Backend: ${BACKEND_DIR}"
    echo ""

    # Run all checks
    check_disk_space || true
    check_memory || true
    check_cpu_load || true
    echo ""

    check_python_version || true
    check_python_packages || true
    check_python_syntax || true
    echo ""

    check_required_files || true
    check_directory_structure || true
    check_permissions || true
    echo ""

    check_database_accessible || true
    check_database_integrity || true
    echo ""

    check_port_available || true
    check_network_connectivity || true
    echo ""

    check_environment_variables || true
    check_config_files || true
    echo ""

    # Summary
    echo "=========================================="
    echo "Pre-Deployment Check Summary"
    echo "=========================================="
    echo -e "${GREEN}Passed:${NC} ${CHECKS_PASSED}"
    echo -e "${YELLOW}Warnings:${NC} ${CHECKS_WARNING}"
    echo -e "${RED}Failed:${NC} ${CHECKS_FAILED}"
    echo ""

    if [ $CHECKS_FAILED -gt 0 ]; then
        echo -e "${RED}❌ Pre-deployment checks FAILED${NC}"
        echo "Please fix the issues above before deploying"
        exit 1
    elif [ $CHECKS_WARNING -gt 0 ]; then
        echo -e "${YELLOW}⚠ Pre-deployment checks passed with warnings${NC}"
        echo "Review warnings before proceeding with deployment"
        exit 0
    else
        echo -e "${GREEN}✅ All pre-deployment checks PASSED${NC}"
        echo "System is ready for deployment"
        exit 0
    fi
}

main "$@"
