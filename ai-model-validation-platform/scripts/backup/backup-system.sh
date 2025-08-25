#!/bin/bash

# AI Model Validation Platform - Comprehensive Backup System
# Automated backup solution for Vultr production deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_BASE_DIR="${BACKUP_DIR:-/var/backups/ai-validation}"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${RETENTION_DAYS:-7}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.vultr.yml}"
ENV_FILE="${ENV_FILE:-.env.vultr}"

# Logging
LOG_FILE="$BACKUP_BASE_DIR/backup_$DATE.log"
mkdir -p "$BACKUP_BASE_DIR"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"; exit 1; }
info() { echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"; }

# Configuration validation
validate_config() {
    log "Validating backup configuration..."
    
    # Check if running as root/sudo
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run with sudo privileges"
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi
    
    # Check if services are running
    cd "$PROJECT_ROOT"
    if ! docker-compose -f "$COMPOSE_FILE" ps -q postgres | grep -q .; then
        error "PostgreSQL container is not running"
    fi
    
    if ! docker-compose -f "$COMPOSE_FILE" ps -q redis | grep -q .; then
        warn "Redis container is not running, skipping Redis backup"
    fi
    
    # Create backup directories
    mkdir -p "$BACKUP_BASE_DIR"/{databases,volumes,configs,logs,ssl}
    
    # Check available disk space (require at least 5GB free)
    AVAILABLE_SPACE=$(df "$BACKUP_BASE_DIR" | awk 'NR==2{print $4}')
    REQUIRED_SPACE=5242880  # 5GB in KB
    if [[ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]]; then
        error "Insufficient disk space. Required: 5GB, Available: $(($AVAILABLE_SPACE/1024/1024))GB"
    fi
    
    log "Configuration validation completed"
}

# Database backup
backup_databases() {
    log "Backing up databases..."
    
    # PostgreSQL backup
    info "Backing up PostgreSQL database..."
    docker exec ai_validation_postgres pg_dumpall -U postgres > "$BACKUP_BASE_DIR/databases/postgres_full_$DATE.sql"
    
    # Individual database backup for main app
    docker exec ai_validation_postgres pg_dump -U postgres -d vru_validation_prod > "$BACKUP_BASE_DIR/databases/postgres_app_$DATE.sql"
    
    # CVAT database backup (if running)
    if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps -q cvat_db | grep -q .; then
        info "Backing up CVAT database..."
        docker exec ai_validation_cvat_db pg_dump -U cvat_user -d cvat > "$BACKUP_BASE_DIR/databases/cvat_$DATE.sql"
    fi
    
    # Compress database backups
    info "Compressing database backups..."
    gzip "$BACKUP_BASE_DIR/databases"/*.sql
    
    log "Database backup completed"
}

# Redis backup
backup_redis() {
    log "Backing up Redis..."
    
    if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps -q redis | grep -q .; then
        # Create Redis dump
        docker exec ai_validation_redis redis-cli --rdb /data/backup_$DATE.rdb
        
        # Copy dump file
        docker cp ai_validation_redis:/data/backup_$DATE.rdb "$BACKUP_BASE_DIR/databases/redis_$DATE.rdb"
        
        # Compress Redis backup
        gzip "$BACKUP_BASE_DIR/databases/redis_$DATE.rdb"
        
        # Clean up temporary file
        docker exec ai_validation_redis rm -f /data/backup_$DATE.rdb
        
        log "Redis backup completed"
    else
        warn "Redis container not running, skipping backup"
    fi
}

# Volume backup
backup_volumes() {
    log "Backing up Docker volumes..."
    
    # Get list of volumes
    VOLUMES=$(docker volume ls --filter "name=ai-model-validation-platform" --format "{{.Name}}")
    
    for volume in $VOLUMES; do
        info "Backing up volume: $volume"
        
        # Create temporary container to access volume
        docker run --rm \
            -v "$volume:/data" \
            -v "$BACKUP_BASE_DIR/volumes:/backup" \
            ubuntu:20.04 \
            tar czf "/backup/${volume}_$DATE.tar.gz" -C /data .
    done
    
    # Backup uploaded files separately for easier access
    info "Backing up uploaded files..."
    docker run --rm \
        -v ai-model-validation-platform_uploaded_videos:/data \
        -v "$BACKUP_BASE_DIR/volumes:/backup" \
        ubuntu:20.04 \
        tar czf "/backup/uploaded_files_$DATE.tar.gz" -C /data .
    
    log "Volume backup completed"
}

# Configuration backup
backup_configs() {
    log "Backing up configuration files..."
    
    cd "$PROJECT_ROOT"
    
    # Application configuration
    info "Backing up application configuration..."
    tar czf "$BACKUP_BASE_DIR/configs/app_config_$DATE.tar.gz" \
        --exclude="node_modules" \
        --exclude=".git" \
        --exclude="logs" \
        --exclude="uploads" \
        --exclude="*.pyc" \
        --exclude="__pycache__" \
        .
    
    # SSL certificates
    if [[ -d "/etc/nginx/ssl" ]]; then
        info "Backing up SSL certificates..."
        tar czf "$BACKUP_BASE_DIR/ssl/ssl_certs_$DATE.tar.gz" -C /etc/nginx/ssl .
    fi
    
    # System configuration
    info "Backing up system configuration..."
    mkdir -p "$BACKUP_BASE_DIR/configs/system"
    
    # Nginx configuration
    if [[ -d "/etc/nginx" ]]; then
        tar czf "$BACKUP_BASE_DIR/configs/system/nginx_$DATE.tar.gz" -C /etc/nginx .
    fi
    
    # Docker configuration
    if [[ -d "/etc/docker" ]]; then
        tar czf "$BACKUP_BASE_DIR/configs/system/docker_$DATE.tar.gz" -C /etc/docker .
    fi
    
    # Cron jobs
    crontab -l > "$BACKUP_BASE_DIR/configs/system/crontab_$DATE.txt" 2>/dev/null || echo "No crontab found"
    
    # UFW firewall rules
    if command -v ufw &> /dev/null; then
        ufw status verbose > "$BACKUP_BASE_DIR/configs/system/ufw_rules_$DATE.txt"
    fi
    
    log "Configuration backup completed"
}

# Log backup
backup_logs() {
    log "Backing up logs..."
    
    # Application logs
    if [[ -d "$PROJECT_ROOT/logs" ]]; then
        tar czf "$BACKUP_BASE_DIR/logs/app_logs_$DATE.tar.gz" -C "$PROJECT_ROOT" logs/
    fi
    
    # System logs (last 7 days)
    info "Backing up system logs..."
    find /var/log -name "*.log" -mtime -7 -type f | \
        tar czf "$BACKUP_BASE_DIR/logs/system_logs_$DATE.tar.gz" --files-from=-
    
    # Docker logs
    info "Backing up Docker container logs..."
    mkdir -p "$BACKUP_BASE_DIR/logs/docker"
    
    # Get container logs
    CONTAINERS=$(docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps --services)
    for container in $CONTAINERS; do
        if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps -q "$container" | grep -q .; then
            docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" logs --no-color "$container" > \
                "$BACKUP_BASE_DIR/logs/docker/${container}_$DATE.log" 2>/dev/null || true
        fi
    done
    
    # Compress Docker logs
    tar czf "$BACKUP_BASE_DIR/logs/docker_logs_$DATE.tar.gz" -C "$BACKUP_BASE_DIR/logs" docker/
    rm -rf "$BACKUP_BASE_DIR/logs/docker"
    
    log "Log backup completed"
}

# Monitoring data backup
backup_monitoring() {
    log "Backing up monitoring data..."
    
    # Prometheus data
    if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps -q prometheus | grep -q .; then
        info "Backing up Prometheus data..."
        docker run --rm \
            -v ai-model-validation-platform_prometheus_data:/data \
            -v "$BACKUP_BASE_DIR/volumes:/backup" \
            ubuntu:20.04 \
            tar czf "/backup/prometheus_data_$DATE.tar.gz" -C /data .
    fi
    
    # Grafana data
    if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps -q grafana | grep -q .; then
        info "Backing up Grafana data..."
        docker run --rm \
            -v ai-model-validation-platform_grafana_data:/data \
            -v "$BACKUP_BASE_DIR/volumes:/backup" \
            ubuntu:20.04 \
            tar czf "/backup/grafana_data_$DATE.tar.gz" -C /data .
    fi
    
    # Loki data
    if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps -q loki | grep -q .; then
        info "Backing up Loki data..."
        docker run --rm \
            -v ai-model-validation-platform_loki_data:/data \
            -v "$BACKUP_BASE_DIR/volumes:/backup" \
            ubuntu:20.04 \
            tar czf "/backup/loki_data_$DATE.tar.gz" -C /data .
    fi
    
    log "Monitoring data backup completed"
}

# Create backup manifest
create_manifest() {
    log "Creating backup manifest..."
    
    MANIFEST_FILE="$BACKUP_BASE_DIR/backup_manifest_$DATE.json"
    
    cat > "$MANIFEST_FILE" << EOF
{
  "backup_info": {
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "date": "$DATE",
    "hostname": "$(hostname)",
    "external_ip": "$(curl -s ifconfig.me || echo 'unknown')",
    "backup_version": "1.0",
    "retention_days": $RETENTION_DAYS
  },
  "system_info": {
    "os": "$(lsb_release -d 2>/dev/null | cut -f2 || echo 'unknown')",
    "kernel": "$(uname -r)",
    "architecture": "$(uname -m)",
    "docker_version": "$(docker --version 2>/dev/null || echo 'unknown')",
    "compose_version": "$(docker-compose --version 2>/dev/null || echo 'unknown')"
  },
  "backup_contents": {
    "databases": [
      $(ls "$BACKUP_BASE_DIR/databases"/*_$DATE.* 2>/dev/null | sed 's|.*/||' | sed 's/^/"/' | sed 's/$/"/' | paste -sd ',' || echo '')
    ],
    "volumes": [
      $(ls "$BACKUP_BASE_DIR/volumes"/*_$DATE.* 2>/dev/null | sed 's|.*/||' | sed 's/^/"/' | sed 's/$/"/' | paste -sd ',' || echo '')
    ],
    "configs": [
      $(ls "$BACKUP_BASE_DIR/configs"/*_$DATE.* 2>/dev/null | sed 's|.*/||' | sed 's/^/"/' | sed 's/$/"/' | paste -sd ',' || echo '')
    ],
    "logs": [
      $(ls "$BACKUP_BASE_DIR/logs"/*_$DATE.* 2>/dev/null | sed 's|.*/||' | sed 's/^/"/' | sed 's/$/"/' | paste -sd ',' || echo '')
    ],
    "ssl": [
      $(ls "$BACKUP_BASE_DIR/ssl"/*_$DATE.* 2>/dev/null | sed 's|.*/||' | sed 's/^/"/' | sed 's/$/"/' | paste -sd ',' || echo '')
    ]
  },
  "backup_stats": {
    "total_size_bytes": $(du -sb "$BACKUP_BASE_DIR" | cut -f1),
    "file_count": $(find "$BACKUP_BASE_DIR" -name "*_$DATE.*" -type f | wc -l),
    "duration_seconds": $SECONDS
  }
}
EOF
    
    log "Backup manifest created: $MANIFEST_FILE"
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups (retention: $RETENTION_DAYS days)..."
    
    # Remove old backup files
    find "$BACKUP_BASE_DIR" -name "*_????????_??????.*" -type f -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_BASE_DIR" -name "backup_????????_??????.log" -type f -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_BASE_DIR" -name "backup_manifest_????????_??????.json" -type f -mtime +$RETENTION_DAYS -delete
    
    # Remove empty directories
    find "$BACKUP_BASE_DIR" -type d -empty -delete
    
    log "Cleanup completed"
}

# Verify backup integrity
verify_backup() {
    log "Verifying backup integrity..."
    
    # Check database backups
    for db_backup in "$BACKUP_BASE_DIR/databases"/*_$DATE.sql.gz; do
        if [[ -f "$db_backup" ]]; then
            info "Verifying $db_backup..."
            if gzip -t "$db_backup"; then
                log "✓ Database backup verified: $db_backup"
            else
                error "✗ Database backup corrupted: $db_backup"
            fi
        fi
    done
    
    # Check volume backups
    for vol_backup in "$BACKUP_BASE_DIR/volumes"/*_$DATE.tar.gz; do
        if [[ -f "$vol_backup" ]]; then
            info "Verifying $vol_backup..."
            if tar -tzf "$vol_backup" >/dev/null 2>&1; then
                log "✓ Volume backup verified: $vol_backup"
            else
                error "✗ Volume backup corrupted: $vol_backup"
            fi
        fi
    done
    
    log "Backup verification completed"
}

# Send backup notification
send_notification() {
    local status="$1"
    local message="$2"
    
    # Email notification (if configured)
    if [[ -n "${BACKUP_EMAIL:-}" ]] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "AI Validation Platform Backup - $status" "$BACKUP_EMAIL"
    fi
    
    # Slack notification (if configured)
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"AI Validation Platform Backup - $status: $message\"}" \
            "$SLACK_WEBHOOK_URL" || true
    fi
    
    # Log notification
    log "Notification sent: $status - $message"
}

# Display backup summary
display_summary() {
    log "Backup Summary"
    echo "=================================="
    echo "Backup Date: $DATE"
    echo "Backup Location: $BACKUP_BASE_DIR"
    echo "Retention Period: $RETENTION_DAYS days"
    echo ""
    
    echo "Backup Contents:"
    echo "- Databases: $(ls "$BACKUP_BASE_DIR/databases"/*_$DATE.* 2>/dev/null | wc -l) files"
    echo "- Volumes: $(ls "$BACKUP_BASE_DIR/volumes"/*_$DATE.* 2>/dev/null | wc -l) files"
    echo "- Configurations: $(ls "$BACKUP_BASE_DIR/configs"/*_$DATE.* 2>/dev/null | wc -l) files"
    echo "- Logs: $(ls "$BACKUP_BASE_DIR/logs"/*_$DATE.* 2>/dev/null | wc -l) files"
    echo "- SSL Certificates: $(ls "$BACKUP_BASE_DIR/ssl"/*_$DATE.* 2>/dev/null | wc -l) files"
    echo ""
    
    echo "Backup Size: $(du -sh "$BACKUP_BASE_DIR" | cut -f1)"
    echo "Duration: $(($SECONDS / 60)) minutes"
    echo "Log File: $LOG_FILE"
    echo ""
    
    echo "Latest Backups:"
    find "$BACKUP_BASE_DIR" -name "*_$DATE.*" -type f -exec ls -lh {} \; | head -10
    
    echo "=================================="
}

# Restore function (for reference)
show_restore_help() {
    echo "Restore Instructions:"
    echo "=================================="
    echo "To restore from backup $DATE:"
    echo ""
    echo "1. Stop services:"
    echo "   cd $PROJECT_ROOT"
    echo "   docker-compose -f $COMPOSE_FILE down -v"
    echo ""
    echo "2. Restore databases:"
    echo "   # Start only database services"
    echo "   docker-compose -f $COMPOSE_FILE up -d postgres redis"
    echo "   # Restore PostgreSQL"
    echo "   zcat $BACKUP_BASE_DIR/databases/postgres_app_$DATE.sql.gz | docker exec -i ai_validation_postgres psql -U postgres"
    echo "   # Restore Redis"
    echo "   zcat $BACKUP_BASE_DIR/databases/redis_$DATE.rdb.gz > /tmp/redis_restore.rdb"
    echo "   docker cp /tmp/redis_restore.rdb ai_validation_redis:/data/dump.rdb"
    echo ""
    echo "3. Restore volumes:"
    echo "   docker run --rm -v ai-model-validation-platform_uploaded_videos:/data -v $BACKUP_BASE_DIR/volumes:/backup ubuntu:20.04 tar xzf /backup/uploaded_files_$DATE.tar.gz -C /data"
    echo ""
    echo "4. Restore configurations:"
    echo "   tar xzf $BACKUP_BASE_DIR/configs/app_config_$DATE.tar.gz -C $PROJECT_ROOT"
    echo ""
    echo "5. Restart services:"
    echo "   docker-compose -f $COMPOSE_FILE up -d"
    echo "=================================="
}

# Main backup function
main() {
    log "Starting comprehensive backup of AI Model Validation Platform..."
    
    validate_config
    backup_databases
    backup_redis
    backup_volumes
    backup_configs
    backup_logs
    backup_monitoring
    create_manifest
    verify_backup
    cleanup_old_backups
    display_summary
    
    local backup_message="Backup completed successfully on $(hostname) at $(date)"
    send_notification "SUCCESS" "$backup_message"
    
    log "Backup completed successfully!"
    log "Total duration: $(($SECONDS / 60)) minutes"
}

# Error handling
trap 'error "Backup failed at line $LINENO"' ERR

# Help function
show_help() {
    echo "AI Model Validation Platform - Backup System"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -d, --dir DIR           Backup directory (default: /var/backups/ai-validation)"
    echo "  -r, --retention DAYS    Retention period in days (default: 7)"
    echo "  -v, --verify-only       Only verify existing backups"
    echo "  --databases-only        Backup only databases"
    echo "  --configs-only          Backup only configurations"
    echo "  --volumes-only          Backup only volumes"
    echo "  --restore-help          Show restore instructions"
    echo ""
    echo "Environment Variables:"
    echo "  BACKUP_DIR              Override backup directory"
    echo "  RETENTION_DAYS          Override retention period"
    echo "  BACKUP_EMAIL            Email for notifications"
    echo "  SLACK_WEBHOOK_URL       Slack webhook for notifications"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Full backup"
    echo "  $0 --databases-only                  # Database backup only"
    echo "  $0 -d /custom/backup/path            # Custom backup location"
    echo "  $0 -r 14                             # 14-day retention"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--dir)
            BACKUP_BASE_DIR="$2"
            shift 2
            ;;
        -r|--retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        -v|--verify-only)
            DATE=$(ls "$BACKUP_BASE_DIR" | grep -o '[0-9]\{8\}_[0-9]\{6\}' | sort -r | head -1)
            if [[ -n "$DATE" ]]; then
                verify_backup
            else
                error "No backups found to verify"
            fi
            exit 0
            ;;
        --databases-only)
            validate_config
            backup_databases
            backup_redis
            create_manifest
            verify_backup
            exit 0
            ;;
        --configs-only)
            validate_config
            backup_configs
            create_manifest
            exit 0
            ;;
        --volumes-only)
            validate_config
            backup_volumes
            create_manifest
            exit 0
            ;;
        --restore-help)
            show_restore_help
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi