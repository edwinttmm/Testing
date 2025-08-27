#!/bin/bash

# =====================================================
# AI Model Validation Platform - Backup System
# Automated backup for databases, volumes, and configurations
# =====================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
ENVIRONMENT="${ENVIRONMENT:-development}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Create backup directory
create_backup_directory() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_path="${BACKUP_DIR}/${ENVIRONMENT}_${timestamp}"
    
    mkdir -p "$backup_path"
    echo "$backup_path"
}

# Backup SQLite databases
backup_sqlite() {
    local backup_path="$1"
    log_info "Backing up SQLite databases..."
    
    local sqlite_files=(
        "${PROJECT_DIR}/backend/dev_database.db"
        "${PROJECT_DIR}/backend/ai_validation.db"
        "${PROJECT_DIR}/backend/test_database.db"
        "${PROJECT_DIR}/backend/fallback_database.db"
    )
    
    mkdir -p "${backup_path}/sqlite"
    
    for db_file in "${sqlite_files[@]}"; do
        if [[ -f "$db_file" ]]; then
            local filename=$(basename "$db_file")
            log_info "Backing up SQLite: $filename"
            
            # Use SQLite VACUUM INTO for consistent backup
            sqlite3 "$db_file" "VACUUM INTO '${backup_path}/sqlite/${filename}.backup'"
            
            # Also create a regular copy
            cp "$db_file" "${backup_path}/sqlite/${filename}.copy"
            
            # Create schema dump
            sqlite3 "$db_file" ".schema" > "${backup_path}/sqlite/${filename}.schema.sql"
            
            log_success "SQLite backup complete: $filename"
        fi
    done
}

# Backup PostgreSQL database
backup_postgresql() {
    local backup_path="$1"
    log_info "Backing up PostgreSQL database..."
    
    mkdir -p "${backup_path}/postgresql"
    
    # Check if PostgreSQL container is running
    if docker compose -f "${PROJECT_DIR}/docker-compose.unified.yml" ps postgres | grep -q "Up"; then
        local timestamp=$(date +"%Y%m%d_%H%M%S")
        
        # Database dump
        log_info "Creating PostgreSQL database dump..."
        docker compose -f "${PROJECT_DIR}/docker-compose.unified.yml" exec -T postgres \
            pg_dump -U postgres -d vru_validation \
            > "${backup_path}/postgresql/database_${timestamp}.sql"
        
        # Schema only dump
        log_info "Creating PostgreSQL schema dump..."
        docker compose -f "${PROJECT_DIR}/docker-compose.unified.yml" exec -T postgres \
            pg_dump -U postgres -d vru_validation --schema-only \
            > "${backup_path}/postgresql/schema_${timestamp}.sql"
        
        # Data only dump
        log_info "Creating PostgreSQL data dump..."
        docker compose -f "${PROJECT_DIR}/docker-compose.unified.yml" exec -T postgres \
            pg_dump -U postgres -d vru_validation --data-only \
            > "${backup_path}/postgresql/data_${timestamp}.sql"
        
        # Custom format backup (for faster restore)
        log_info "Creating PostgreSQL custom format backup..."
        docker compose -f "${PROJECT_DIR}/docker-compose.unified.yml" exec -T postgres \
            pg_dump -U postgres -d vru_validation -Fc \
            > "${backup_path}/postgresql/database_${timestamp}.backup"
        
        log_success "PostgreSQL backup complete"
    else
        log_warning "PostgreSQL container not running, skipping database backup"
    fi
}

# Backup Docker volumes
backup_volumes() {
    local backup_path="$1"
    log_info "Backing up Docker volumes..."
    
    mkdir -p "${backup_path}/volumes"
    
    local volumes=(
        "ai_validation_postgres_data"
        "ai_validation_redis_data"
        "ai_validation_uploaded_videos"
        "ai_validation_cvat_data"
        "ai_validation_cvat_keys"
        "ai_validation_cvat_logs"
    )
    
    for volume in "${volumes[@]}"; do
        if docker volume ls | grep -q "$volume"; then
            log_info "Backing up volume: $volume"
            
            # Create tar backup of volume
            docker run --rm \
                -v "$volume:/data:ro" \
                -v "${backup_path}/volumes:/backup" \
                alpine:latest \
                tar -czf "/backup/${volume}_$(date +%Y%m%d_%H%M%S).tar.gz" -C /data .
            
            log_success "Volume backup complete: $volume"
        else
            log_warning "Volume not found: $volume"
        fi
    done
}

# Backup configuration files
backup_configurations() {
    local backup_path="$1"
    log_info "Backing up configuration files..."
    
    mkdir -p "${backup_path}/config"
    
    local config_files=(
        "${PROJECT_DIR}/.env*"
        "${PROJECT_DIR}/docker-compose*.yml"
        "${PROJECT_DIR}/backend/requirements*.txt"
        "${PROJECT_DIR}/frontend/package*.json"
        "${PROJECT_DIR}/scripts"
        "${PROJECT_DIR}/database"
    )
    
    for pattern in "${config_files[@]}"; do
        if ls $pattern 1> /dev/null 2>&1; then
            cp -r $pattern "${backup_path}/config/" 2>/dev/null || true
        fi
    done
    
    # Export Docker Compose configuration
    if [[ -f "${PROJECT_DIR}/docker-compose.unified.yml" ]]; then
        docker compose -f "${PROJECT_DIR}/docker-compose.unified.yml" config \
            > "${backup_path}/config/resolved-compose.yml" 2>/dev/null || true
    fi
    
    log_success "Configuration backup complete"
}

# Backup application data
backup_application_data() {
    local backup_path="$1"
    log_info "Backing up application data..."
    
    mkdir -p "${backup_path}/data"
    
    local data_dirs=(
        "${PROJECT_DIR}/backend/uploads"
        "${PROJECT_DIR}/backend/models"
        "${PROJECT_DIR}/backend/logs"
        "${PROJECT_DIR}/backend/exports"
        "${PROJECT_DIR}/backend/screenshots"
        "${PROJECT_DIR}/frontend/build"
        "${PROJECT_DIR}/logs"
    )
    
    for dir in "${data_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            local dirname=$(basename "$dir")
            log_info "Backing up data directory: $dirname"
            
            tar -czf "${backup_path}/data/${dirname}_$(date +%Y%m%d_%H%M%S).tar.gz" \
                -C "$(dirname "$dir")" "$dirname"
            
            log_success "Data backup complete: $dirname"
        fi
    done
}

# Create backup manifest
create_manifest() {
    local backup_path="$1"
    log_info "Creating backup manifest..."
    
    cat > "${backup_path}/MANIFEST.txt" << EOF
AI Model Validation Platform - Backup Manifest
===============================================

Backup Date: $(date -Iseconds)
Environment: $ENVIRONMENT
Backup Path: $backup_path
Host: $(hostname)
User: $(whoami)

Contents:
---------
$(find "$backup_path" -type f -exec ls -la {} \; | head -20)

$(if [[ $(find "$backup_path" -type f | wc -l) -gt 20 ]]; then
    echo "... and $(($(find "$backup_path" -type f | wc -l) - 20)) more files"
fi)

Total Size: $(du -sh "$backup_path" | cut -f1)

Docker Status:
--------------
$(docker compose -f "${PROJECT_DIR}/docker-compose.unified.yml" ps 2>/dev/null || echo "Docker Compose not available")

System Info:
------------
Disk Space: $(df -h "$backup_path" | tail -1)
Memory: $(free -h | grep ^Mem | awk '{print $3 "/" $2}')
Load: $(uptime | awk -F'load average:' '{print $2}')

EOF

    log_success "Backup manifest created"
}

# Compress backup
compress_backup() {
    local backup_path="$1"
    log_info "Compressing backup..."
    
    local backup_name=$(basename "$backup_path")
    local compressed_file="${BACKUP_DIR}/${backup_name}.tar.gz"
    
    tar -czf "$compressed_file" -C "$(dirname "$backup_path")" "$backup_name"
    
    # Remove uncompressed backup
    rm -rf "$backup_path"
    
    log_success "Backup compressed: $compressed_file"
    echo "$compressed_file"
}

# Clean old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups (retention: ${RETENTION_DAYS} days)..."
    
    find "$BACKUP_DIR" -name "${ENVIRONMENT}_*.tar.gz" -mtime +$RETENTION_DAYS -delete
    
    local remaining=$(find "$BACKUP_DIR" -name "${ENVIRONMENT}_*.tar.gz" | wc -l)
    log_success "Cleanup complete. Remaining backups: $remaining"
}

# Verify backup integrity
verify_backup() {
    local compressed_file="$1"
    log_info "Verifying backup integrity..."
    
    if tar -tzf "$compressed_file" >/dev/null 2>&1; then
        local file_count=$(tar -tzf "$compressed_file" | wc -l)
        local size=$(du -sh "$compressed_file" | cut -f1)
        
        log_success "Backup verification passed"
        log_info "Files: $file_count, Size: $size"
        
        return 0
    else
        log_error "Backup verification failed!"
        return 1
    fi
}

# Send backup notification
send_notification() {
    local status="$1"
    local backup_file="$2"
    
    if [[ -n "${WEBHOOK_URL:-}" ]]; then
        local message
        if [[ "$status" == "success" ]]; then
            message="✅ Backup completed successfully for environment: $ENVIRONMENT"
        else
            message="❌ Backup failed for environment: $ENVIRONMENT"
        fi
        
        curl -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"$message\"}" \
            >/dev/null 2>&1 || true
    fi
    
    # Log to system log
    logger "AI Model Validation Platform backup $status: $backup_file"
}

# Main backup function
main() {
    local start_time=$(date +%s)
    
    log_info "Starting backup for environment: $ENVIRONMENT"
    
    # Create backup directory
    local backup_path=$(create_backup_directory)
    
    try {
        # Run backup operations
        backup_sqlite "$backup_path"
        backup_postgresql "$backup_path"
        backup_volumes "$backup_path"
        backup_configurations "$backup_path"
        backup_application_data "$backup_path"
        create_manifest "$backup_path"
        
        # Compress and verify
        local compressed_file=$(compress_backup "$backup_path")
        verify_backup "$compressed_file"
        
        # Cleanup old backups
        cleanup_old_backups
        
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        log_success "Backup completed successfully in ${duration} seconds"
        log_info "Backup file: $compressed_file"
        
        send_notification "success" "$compressed_file"
        
    } catch {
        log_error "Backup failed!"
        send_notification "failure" "$backup_path"
        exit 1
    }
}

# Error handling
try() {
    "$@"
}

catch() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        "$@"
    fi
    return $exit_code
}

# Usage information
usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Environment to backup (development|staging|production)"
    echo "  -r, --retention DAYS     Retention period in days (default: 7)"
    echo "  -d, --directory DIR      Backup directory (default: ./backups)"
    echo "  -h, --help              Show this help"
    echo ""
    echo "Environment Variables:"
    echo "  BACKUP_DIR              Backup directory"
    echo "  RETENTION_DAYS          Retention period"
    echo "  WEBHOOK_URL             Webhook URL for notifications"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        -d|--directory)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Run main function
main