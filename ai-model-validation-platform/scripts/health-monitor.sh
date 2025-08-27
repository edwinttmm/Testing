#!/bin/bash

# =====================================================
# AI Model Validation Platform - Health Monitor
# Comprehensive system monitoring and alerting
# =====================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_DIR}/logs/health-monitor.log"
ALERT_FILE="${PROJECT_DIR}/logs/alerts.log"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
ALERT_THRESHOLD="${ALERT_THRESHOLD:-3}"
ENVIRONMENT="${ENVIRONMENT:-development}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters for consecutive failures
declare -A failure_count

log_info() { 
    local msg="[$(date -Iseconds)] [INFO] $1"
    echo -e "${BLUE}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_success() { 
    local msg="[$(date -Iseconds)] [SUCCESS] $1"
    echo -e "${GREEN}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_warning() { 
    local msg="[$(date -Iseconds)] [WARNING] $1"
    echo -e "${YELLOW}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
    echo "$msg" >> "$ALERT_FILE"
}

log_error() { 
    local msg="[$(date -Iseconds)] [ERROR] $1"
    echo -e "${RED}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
    echo "$msg" >> "$ALERT_FILE"
}

# Initialize log files
initialize_logs() {
    mkdir -p "$(dirname "$LOG_FILE")"
    mkdir -p "$(dirname "$ALERT_FILE")"
    
    if [[ ! -f "$LOG_FILE" ]]; then
        echo "[$(date -Iseconds)] Health monitor started for environment: $ENVIRONMENT" > "$LOG_FILE"
    fi
}

# Check Docker services
check_docker_services() {
    local compose_file="${PROJECT_DIR}/docker-compose.unified.yml"
    local env_file="${PROJECT_DIR}/.env.${ENVIRONMENT}"
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file not found: $env_file"
        return 1
    fi
    
    log_info "Checking Docker services..."
    
    # Check if services are running
    local services=$(docker compose --env-file "$env_file" -f "$compose_file" ps --services 2>/dev/null || echo "")
    
    if [[ -z "$services" ]]; then
        log_error "No Docker services found or Docker Compose not available"
        return 1
    fi
    
    local failed_services=()
    
    for service in $services; do
        local status=$(docker compose --env-file "$env_file" -f "$compose_file" ps "$service" --format "table {{.State}}" | tail -n +2 | head -1)
        
        if [[ "$status" == "running" ]]; then
            log_success "Service $service: running"
            failure_count["$service"]=0
        else
            log_error "Service $service: $status"
            failure_count["$service"]=$((${failure_count["$service"]:-0} + 1))
            failed_services+=("$service")
            
            # Try to restart service if it fails multiple times
            if [[ ${failure_count["$service"]} -ge $ALERT_THRESHOLD ]]; then
                log_warning "Attempting to restart $service (failed ${failure_count["$service"]} times)"
                docker compose --env-file "$env_file" -f "$compose_file" restart "$service" || true
            fi
        fi
    done
    
    if [[ ${#failed_services[@]} -gt 0 ]]; then
        return 1
    fi
    
    return 0
}

# Check service endpoints
check_endpoints() {
    log_info "Checking service endpoints..."
    
    local endpoints=(
        "backend:http://localhost:8000/health:Backend API"
        "frontend:http://localhost:3000:Frontend"
        "docs:http://localhost:8000/docs:API Documentation"
    )
    
    if [[ "$ENVIRONMENT" == "production" || "$ENVIRONMENT" == "staging" ]]; then
        endpoints+=(
            "cvat:http://localhost:8080:CVAT"
            "prometheus:http://localhost:9090:Prometheus"
        )
    fi
    
    local failed_endpoints=()
    
    for endpoint_info in "${endpoints[@]}"; do
        IFS=':' read -r service_name url description <<< "$endpoint_info"
        
        if curl -f -s --max-time 10 "$url" >/dev/null 2>&1; then
            log_success "$description: accessible"
            failure_count["endpoint_$service_name"]=0
        else
            log_error "$description: not accessible at $url"
            failure_count["endpoint_$service_name"]=$((${failure_count["endpoint_$service_name"]:-0} + 1))
            failed_endpoints+=("$description")
        fi
    done
    
    if [[ ${#failed_endpoints[@]} -gt 0 ]]; then
        return 1
    fi
    
    return 0
}

# Check database connectivity
check_database() {
    log_info "Checking database connectivity..."
    
    if [[ "$ENVIRONMENT" == "production" || "$ENVIRONMENT" == "staging" ]]; then
        # Check PostgreSQL
        local compose_file="${PROJECT_DIR}/docker-compose.unified.yml"
        local env_file="${PROJECT_DIR}/.env.${ENVIRONMENT}"
        
        if docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
            log_success "PostgreSQL: connected"
            failure_count["postgres"]=0
        else
            log_error "PostgreSQL: connection failed"
            failure_count["postgres"]=$((${failure_count["postgres"]:-0} + 1))
            return 1
        fi
        
        # Check database size
        local db_size=$(docker compose --env-file "$env_file" -f "$compose_file" exec -T postgres \
            psql -U postgres -d vru_validation -t -c "SELECT pg_size_pretty(pg_database_size('vru_validation'));" 2>/dev/null | xargs || echo "unknown")
        log_info "PostgreSQL database size: $db_size"
        
    else
        # Check SQLite
        local sqlite_files=(
            "${PROJECT_DIR}/backend/dev_database.db"
            "${PROJECT_DIR}/backend/ai_validation.db"
        )
        
        for db_file in "${sqlite_files[@]}"; do
            if [[ -f "$db_file" ]]; then
                if sqlite3 "$db_file" "SELECT 1;" >/dev/null 2>&1; then
                    local size=$(du -sh "$db_file" | cut -f1)
                    log_success "SQLite $(basename "$db_file"): accessible (size: $size)"
                    failure_count["sqlite_$(basename "$db_file")"]=0
                else
                    log_error "SQLite $(basename "$db_file"): corrupted or inaccessible"
                    failure_count["sqlite_$(basename "$db_file")"]=$((${failure_count["sqlite_$(basename "$db_file")"]:-0} + 1))
                    return 1
                fi
            fi
        done
    fi
    
    # Check Redis
    local compose_file="${PROJECT_DIR}/docker-compose.unified.yml"
    local env_file="${PROJECT_DIR}/.env.${ENVIRONMENT}"
    
    if docker compose --env-file "$env_file" -f "$compose_file" exec -T redis redis-cli ping >/dev/null 2>&1; then
        log_success "Redis: connected"
        failure_count["redis"]=0
        
        # Check Redis info
        local redis_memory=$(docker compose --env-file "$env_file" -f "$compose_file" exec -T redis \
            redis-cli info memory | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r' || echo "unknown")
        log_info "Redis memory usage: $redis_memory"
    else
        log_error "Redis: connection failed"
        failure_count["redis"]=$((${failure_count["redis"]:-0} + 1))
        return 1
    fi
    
    return 0
}

# Check system resources
check_system_resources() {
    log_info "Checking system resources..."
    
    # Check disk space
    local disk_usage=$(df "$PROJECT_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 90 ]]; then
        log_error "Disk usage critical: ${disk_usage}%"
        return 1
    elif [[ $disk_usage -gt 80 ]]; then
        log_warning "Disk usage high: ${disk_usage}%"
    else
        log_success "Disk usage normal: ${disk_usage}%"
    fi
    
    # Check memory usage
    local memory_info=$(free | grep ^Mem)
    local total_memory=$(echo $memory_info | awk '{print $2}')
    local used_memory=$(echo $memory_info | awk '{print $3}')
    local memory_percent=$((used_memory * 100 / total_memory))
    
    if [[ $memory_percent -gt 90 ]]; then
        log_error "Memory usage critical: ${memory_percent}%"
        return 1
    elif [[ $memory_percent -gt 80 ]]; then
        log_warning "Memory usage high: ${memory_percent}%"
    else
        log_success "Memory usage normal: ${memory_percent}%"
    fi
    
    # Check load average
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cpu_count=$(nproc)
    local load_percent=$(echo "$load_avg * 100 / $cpu_count" | bc -l | cut -d. -f1)
    
    if [[ $load_percent -gt 80 ]]; then
        log_warning "System load high: ${load_avg} (${load_percent}%)"
    else
        log_success "System load normal: ${load_avg}"
    fi
    
    return 0
}

# Check log file sizes
check_log_files() {
    log_info "Checking log file sizes..."
    
    local log_dirs=(
        "${PROJECT_DIR}/logs"
        "${PROJECT_DIR}/backend/logs"
        "${PROJECT_DIR}/frontend/logs"
    )
    
    for log_dir in "${log_dirs[@]}"; do
        if [[ -d "$log_dir" ]]; then
            local log_size=$(du -sh "$log_dir" 2>/dev/null | cut -f1 || echo "0")
            log_info "Log directory $(basename "$log_dir"): $log_size"
            
            # Check for very large log files
            find "$log_dir" -name "*.log" -size +100M -exec ls -lh {} \; | while read -r large_file; do
                log_warning "Large log file found: $large_file"
            done
        fi
    done
    
    return 0
}

# Check Docker resource usage
check_docker_resources() {
    log_info "Checking Docker resource usage..."
    
    # Check Docker system usage
    local docker_info=$(docker system df --format "table {{.Type}}\t{{.TotalCount}}\t{{.Size}}" 2>/dev/null || echo "")
    
    if [[ -n "$docker_info" ]]; then
        echo "Docker Resource Usage:"
        echo "$docker_info"
    fi
    
    # Check container resource usage
    local compose_file="${PROJECT_DIR}/docker-compose.unified.yml"
    local env_file="${PROJECT_DIR}/.env.${ENVIRONMENT}"
    
    if docker compose --env-file "$env_file" -f "$compose_file" ps -q >/dev/null 2>&1; then
        local containers=$(docker compose --env-file "$env_file" -f "$compose_file" ps -q)
        
        for container in $containers; do
            if [[ -n "$container" ]]; then
                local stats=$(docker stats "$container" --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | tail -1)
                log_info "Container stats: $stats"
            fi
        done
    fi
    
    return 0
}

# Send alert notification
send_alert() {
    local severity="$1"
    local message="$2"
    
    local alert_message="[$severity] AI Model Validation Platform ($ENVIRONMENT): $message"
    
    # Log alert
    echo "[$(date -Iseconds)] $alert_message" >> "$ALERT_FILE"
    
    # Send webhook notification
    if [[ -n "${WEBHOOK_URL:-}" ]]; then
        local emoji="⚠️"
        if [[ "$severity" == "CRITICAL" ]]; then
            emoji="🚨"
        elif [[ "$severity" == "INFO" ]]; then
            emoji="ℹ️"
        fi
        
        curl -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"$emoji $alert_message\"}" \
            >/dev/null 2>&1 || true
    fi
    
    # Send email notification
    if [[ -n "${ALERT_EMAIL:-}" ]] && command -v mail >/dev/null; then
        echo "$alert_message" | mail -s "AI Model Validation Platform Alert" "$ALERT_EMAIL" 2>/dev/null || true
    fi
}

# Generate health report
generate_health_report() {
    local report_file="${PROJECT_DIR}/logs/health-report-$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
AI Model Validation Platform - Health Report
===========================================

Generated: $(date -Iseconds)
Environment: $ENVIRONMENT
Host: $(hostname)

System Information:
------------------
OS: $(uname -a)
Uptime: $(uptime)
Load Average: $(uptime | awk -F'load average:' '{print $2}')
Memory: $(free -h | grep ^Mem)
Disk Space: $(df -h "$PROJECT_DIR")

Docker Information:
------------------
$(docker --version 2>/dev/null || echo "Docker not available")
$(docker compose version 2>/dev/null || echo "Docker Compose not available")

Service Status:
--------------
$(docker compose --env-file "${PROJECT_DIR}/.env.${ENVIRONMENT}" -f "${PROJECT_DIR}/docker-compose.unified.yml" ps 2>/dev/null || echo "Services not available")

Recent Alerts:
--------------
$(tail -20 "$ALERT_FILE" 2>/dev/null || echo "No recent alerts")

Log File Sizes:
--------------
$(find "${PROJECT_DIR}/logs" -name "*.log" -exec ls -lh {} \; 2>/dev/null | head -10)

EOF

    log_info "Health report generated: $report_file"
}

# Main health check function
perform_health_check() {
    local start_time=$(date +%s)
    local checks_passed=0
    local checks_failed=0
    
    log_info "Starting health check for environment: $ENVIRONMENT"
    
    # Run health checks
    if check_docker_services; then
        ((checks_passed++))
    else
        ((checks_failed++))
        send_alert "CRITICAL" "Docker services health check failed"
    fi
    
    if check_endpoints; then
        ((checks_passed++))
    else
        ((checks_failed++))
        send_alert "CRITICAL" "Service endpoints health check failed"
    fi
    
    if check_database; then
        ((checks_passed++))
    else
        ((checks_failed++))
        send_alert "CRITICAL" "Database connectivity check failed"
    fi
    
    if check_system_resources; then
        ((checks_passed++))
    else
        ((checks_failed++))
        send_alert "WARNING" "System resources check failed"
    fi
    
    if check_log_files; then
        ((checks_passed++))
    else
        ((checks_failed++))
    fi
    
    if check_docker_resources; then
        ((checks_passed++))
    else
        ((checks_failed++))
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Summary
    if [[ $checks_failed -eq 0 ]]; then
        log_success "All health checks passed ($checks_passed/$((checks_passed + checks_failed))) in ${duration}s"
        send_alert "INFO" "All health checks passed"
    else
        log_error "Health check completed with failures: $checks_failed failed, $checks_passed passed in ${duration}s"
    fi
    
    # Generate health report periodically
    local current_hour=$(date +%H)
    if [[ "$current_hour" == "06" ]] && [[ ! -f "${PROJECT_DIR}/logs/.report_generated_today" ]]; then
        generate_health_report
        touch "${PROJECT_DIR}/logs/.report_generated_today"
    elif [[ "$current_hour" == "07" ]]; then
        rm -f "${PROJECT_DIR}/logs/.report_generated_today"
    fi
}

# Continuous monitoring mode
continuous_monitoring() {
    log_info "Starting continuous monitoring (interval: ${CHECK_INTERVAL}s)"
    
    # Trap signals for graceful shutdown
    trap 'log_info "Stopping health monitor..."; exit 0' SIGINT SIGTERM
    
    while true; do
        perform_health_check
        sleep "$CHECK_INTERVAL"
    done
}

# Usage information
usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV      Environment to monitor (default: development)"
    echo "  -i, --interval SECONDS     Check interval in seconds (default: 30)"
    echo "  -t, --threshold COUNT      Alert threshold for consecutive failures (default: 3)"
    echo "  -c, --continuous          Run in continuous monitoring mode"
    echo "  -r, --report              Generate health report only"
    echo "  -h, --help                Show this help"
    echo ""
    echo "Environment Variables:"
    echo "  WEBHOOK_URL               Webhook URL for notifications"
    echo "  ALERT_EMAIL               Email address for alerts"
    echo "  CHECK_INTERVAL            Check interval in seconds"
    echo "  ALERT_THRESHOLD           Alert threshold count"
    echo ""
}

# Parse command line arguments
CONTINUOUS=false
REPORT_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -i|--interval)
            CHECK_INTERVAL="$2"
            shift 2
            ;;
        -t|--threshold)
            ALERT_THRESHOLD="$2"
            shift 2
            ;;
        -c|--continuous)
            CONTINUOUS=true
            shift
            ;;
        -r|--report)
            REPORT_ONLY=true
            shift
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

# Initialize logs
initialize_logs

# Run based on mode
if [[ "$REPORT_ONLY" == "true" ]]; then
    generate_health_report
elif [[ "$CONTINUOUS" == "true" ]]; then
    continuous_monitoring
else
    perform_health_check
fi