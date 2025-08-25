#!/bin/bash

# AI Model Validation Platform - Comprehensive Health Check Script
# Production health monitoring for Vultr deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.vultr.yml}"
ENV_FILE="${ENV_FILE:-.env.vultr}"
EXTERNAL_IP="155.138.239.131"
HEALTH_CHECK_TIMEOUT=10
LOG_FILE="/var/log/ai-validation/health-check.log"

# Logging
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓ $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠ $1${NC}"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗ $1${NC}"; }
info() { echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] ℹ $1${NC}"; }

# Health check results
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Track individual checks
declare -A HEALTH_STATUS

# Helper function to record check result
record_check() {
    local check_name="$1"
    local status="$2"  # PASS, FAIL, WARN
    local message="$3"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    HEALTH_STATUS["$check_name"]="$status:$message"
    
    case "$status" in
        "PASS")
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
            log "$check_name: $message"
            ;;
        "FAIL")
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
            error "$check_name: $message"
            ;;
        "WARN")
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
            warn "$check_name: $message"
            ;;
    esac
}

# System health checks
check_system_resources() {
    info "Checking system resources..."
    
    # CPU usage
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
        record_check "CPU Usage" "WARN" "High CPU usage: ${CPU_USAGE}%"
    else
        record_check "CPU Usage" "PASS" "CPU usage: ${CPU_USAGE}%"
    fi
    
    # Memory usage
    MEMORY_INFO=$(free -m)
    MEMORY_USED=$(echo "$MEMORY_INFO" | awk 'NR==2{printf "%.1f", $3*100/$2}')
    if (( $(echo "$MEMORY_USED > 90" | bc -l) )); then
        record_check "Memory Usage" "WARN" "High memory usage: ${MEMORY_USED}%"
    else
        record_check "Memory Usage" "PASS" "Memory usage: ${MEMORY_USED}%"
    fi
    
    # Disk usage
    DISK_USAGE=$(df / | awk 'NR==2{print $5}' | sed 's/%//')
    if [[ $DISK_USAGE -gt 85 ]]; then
        record_check "Disk Usage" "WARN" "High disk usage: ${DISK_USAGE}%"
    else
        record_check "Disk Usage" "PASS" "Disk usage: ${DISK_USAGE}%"
    fi
    
    # Load average
    LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | cut -d',' -f1 | xargs)
    CPU_CORES=$(nproc)
    if (( $(echo "$LOAD_AVG > $CPU_CORES" | bc -l) )); then
        record_check "System Load" "WARN" "High load average: $LOAD_AVG (cores: $CPU_CORES)"
    else
        record_check "System Load" "PASS" "Load average: $LOAD_AVG (cores: $CPU_CORES)"
    fi
}

# Docker health checks
check_docker_services() {
    info "Checking Docker services..."
    
    cd "$PROJECT_ROOT"
    
    # Check if Docker is running
    if ! docker info &>/dev/null; then
        record_check "Docker Daemon" "FAIL" "Docker daemon is not running"
        return
    fi
    record_check "Docker Daemon" "PASS" "Docker daemon is running"
    
    # Check Docker Compose services
    local services=(postgres redis backend frontend nginx)
    if [[ -f "$COMPOSE_FILE" ]]; then
        for service in "${services[@]}"; do
            if docker-compose -f "$COMPOSE_FILE" ps -q "$service" | grep -q .; then
                local status=$(docker-compose -f "$COMPOSE_FILE" ps "$service" | tail -n +3 | awk '{print $4}')
                if [[ "$status" == "Up" ]]; then
                    record_check "Docker Service: $service" "PASS" "Service is running"
                else
                    record_check "Docker Service: $service" "FAIL" "Service status: $status"
                fi
            else
                record_check "Docker Service: $service" "FAIL" "Service not found or not running"
            fi
        done
    else
        record_check "Docker Compose File" "FAIL" "Compose file not found: $COMPOSE_FILE"
    fi
    
    # Check container resource usage
    local container_stats=$(docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}" | tail -n +2)
    if [[ -n "$container_stats" ]]; then
        record_check "Container Resources" "PASS" "All containers reporting resource usage"
    else
        record_check "Container Resources" "WARN" "No container resource data available"
    fi
}

# Network connectivity checks
check_network_connectivity() {
    info "Checking network connectivity..."
    
    # Internet connectivity
    if ping -c 1 8.8.8.8 &>/dev/null; then
        record_check "Internet Connectivity" "PASS" "Internet connection available"
    else
        record_check "Internet Connectivity" "FAIL" "No internet connectivity"
    fi
    
    # DNS resolution
    if nslookup google.com &>/dev/null; then
        record_check "DNS Resolution" "PASS" "DNS resolution working"
    else
        record_check "DNS Resolution" "FAIL" "DNS resolution failed"
    fi
    
    # External IP check
    CURRENT_IP=$(curl -s --connect-timeout 5 ifconfig.me || curl -s --connect-timeout 5 icanhazip.com || echo "unknown")
    if [[ "$CURRENT_IP" == "$EXTERNAL_IP" ]]; then
        record_check "External IP" "PASS" "External IP matches expected: $EXTERNAL_IP"
    else
        record_check "External IP" "WARN" "External IP mismatch: Expected $EXTERNAL_IP, Got $CURRENT_IP"
    fi
}

# Application health checks
check_application_health() {
    info "Checking application health endpoints..."
    
    # Backend API health
    if curl -f -s --connect-timeout "$HEALTH_CHECK_TIMEOUT" "http://localhost:8000/health" &>/dev/null; then
        local health_response=$(curl -s "http://localhost:8000/health")
        record_check "Backend Health" "PASS" "API health endpoint responding: $health_response"
    else
        record_check "Backend Health" "FAIL" "API health endpoint not responding"
    fi
    
    # Frontend health
    if curl -f -s --connect-timeout "$HEALTH_CHECK_TIMEOUT" "http://localhost:3000" &>/dev/null; then
        record_check "Frontend Health" "PASS" "Frontend responding"
    else
        record_check "Frontend Health" "FAIL" "Frontend not responding"
    fi
    
    # Nginx proxy health
    if curl -f -s --connect-timeout "$HEALTH_CHECK_TIMEOUT" "http://localhost/health" &>/dev/null; then
        record_check "Nginx Proxy" "PASS" "Nginx proxy responding"
    else
        record_check "Nginx Proxy" "FAIL" "Nginx proxy not responding"
    fi
    
    # HTTPS health
    if curl -f -s -k --connect-timeout "$HEALTH_CHECK_TIMEOUT" "https://localhost/health" &>/dev/null; then
        record_check "HTTPS Health" "PASS" "HTTPS endpoint responding"
    else
        record_check "HTTPS Health" "FAIL" "HTTPS endpoint not responding"
    fi
}

# Database health checks
check_database_health() {
    info "Checking database health..."
    
    # PostgreSQL health
    if docker exec ai_validation_postgres pg_isready -U postgres &>/dev/null; then
        # Check database connections
        local connections=$(docker exec ai_validation_postgres psql -U postgres -t -c "SELECT count(*) FROM pg_stat_activity;")
        record_check "PostgreSQL Health" "PASS" "Database ready, active connections: $(echo $connections | xargs)"
    else
        record_check "PostgreSQL Health" "FAIL" "Database not ready"
    fi
    
    # Redis health
    if docker exec ai_validation_redis redis-cli ping &>/dev/null; then
        local redis_info=$(docker exec ai_validation_redis redis-cli info memory | grep used_memory_human | cut -d':' -f2 | tr -d '\r')
        record_check "Redis Health" "PASS" "Redis responding, memory usage: $redis_info"
    else
        record_check "Redis Health" "FAIL" "Redis not responding"
    fi
    
    # Database performance check (optional)
    if docker exec ai_validation_postgres psql -U postgres -d vru_validation_prod -c "SELECT 1;" &>/dev/null; then
        record_check "Database Connectivity" "PASS" "Database connection successful"
    else
        record_check "Database Connectivity" "FAIL" "Cannot connect to application database"
    fi
}

# SSL certificate checks
check_ssl_certificates() {
    info "Checking SSL certificates..."
    
    local cert_file="/etc/nginx/ssl/cert.pem"
    local key_file="/etc/nginx/ssl/private.key"
    
    # Check certificate files exist
    if [[ -f "$cert_file" && -f "$key_file" ]]; then
        record_check "SSL Files" "PASS" "SSL certificate files exist"
        
        # Check certificate validity
        local cert_expiry=$(openssl x509 -enddate -noout -in "$cert_file" | cut -d= -f2)
        local expiry_epoch=$(date -d "$cert_expiry" +%s)
        local current_epoch=$(date +%s)
        local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
        
        if [[ $days_until_expiry -lt 0 ]]; then
            record_check "SSL Certificate Expiry" "FAIL" "Certificate has expired"
        elif [[ $days_until_expiry -lt 7 ]]; then
            record_check "SSL Certificate Expiry" "WARN" "Certificate expires in $days_until_expiry days"
        else
            record_check "SSL Certificate Expiry" "PASS" "Certificate expires in $days_until_expiry days"
        fi
        
        # Test SSL connection
        if echo | openssl s_client -connect "localhost:443" -servername "$EXTERNAL_IP" &>/dev/null; then
            record_check "SSL Connection" "PASS" "SSL handshake successful"
        else
            record_check "SSL Connection" "FAIL" "SSL handshake failed"
        fi
    else
        record_check "SSL Files" "FAIL" "SSL certificate files not found"
    fi
}

# External access checks
check_external_access() {
    info "Checking external access..."
    
    # HTTP external access
    if curl -f -s --connect-timeout "$HEALTH_CHECK_TIMEOUT" "http://$EXTERNAL_IP/health" &>/dev/null; then
        record_check "External HTTP" "PASS" "External HTTP access working"
    else
        record_check "External HTTP" "FAIL" "External HTTP access failed"
    fi
    
    # HTTPS external access
    if curl -f -s -k --connect-timeout "$HEALTH_CHECK_TIMEOUT" "https://$EXTERNAL_IP/health" &>/dev/null; then
        record_check "External HTTPS" "PASS" "External HTTPS access working"
    else
        record_check "External HTTPS" "FAIL" "External HTTPS access failed"
    fi
    
    # API external access
    if curl -f -s --connect-timeout "$HEALTH_CHECK_TIMEOUT" "https://$EXTERNAL_IP/api/health" &>/dev/null; then
        record_check "External API" "PASS" "External API access working"
    else
        record_check "External API" "FAIL" "External API access failed"
    fi
}

# Security checks
check_security() {
    info "Checking security configuration..."
    
    # Firewall status
    if command -v ufw &>/dev/null; then
        local ufw_status=$(sudo ufw status | head -1)
        if [[ "$ufw_status" == *"active"* ]]; then
            record_check "Firewall Status" "PASS" "UFW firewall is active"
        else
            record_check "Firewall Status" "WARN" "UFW firewall is not active"
        fi
    else
        record_check "Firewall Status" "WARN" "UFW not installed"
    fi
    
    # Fail2Ban status
    if command -v fail2ban-client &>/dev/null; then
        if systemctl is-active --quiet fail2ban; then
            local jail_count=$(sudo fail2ban-client status | grep "Jail list:" | cut -d: -f2 | wc -w)
            record_check "Fail2Ban Status" "PASS" "Fail2Ban active with $jail_count jails"
        else
            record_check "Fail2Ban Status" "WARN" "Fail2Ban not running"
        fi
    else
        record_check "Fail2Ban Status" "WARN" "Fail2Ban not installed"
    fi
    
    # SSH security
    local ssh_config="/etc/ssh/sshd_config"
    if [[ -f "$ssh_config" ]]; then
        if grep -q "PermitRootLogin no" "$ssh_config"; then
            record_check "SSH Root Login" "PASS" "Root login disabled"
        else
            record_check "SSH Root Login" "WARN" "Root login may be enabled"
        fi
    fi
}

# Log file checks
check_logs() {
    info "Checking log files..."
    
    # Check log directory permissions
    local log_dir="/var/log/ai-validation"
    if [[ -d "$log_dir" ]]; then
        record_check "Log Directory" "PASS" "Log directory exists"
        
        # Check recent errors
        local error_count=0
        if [[ -f "$PROJECT_ROOT/logs/backend/error.log" ]]; then
            error_count=$(grep -c "ERROR" "$PROJECT_ROOT/logs/backend/error.log" 2>/dev/null || echo 0)
        fi
        
        if [[ $error_count -gt 100 ]]; then
            record_check "Application Errors" "WARN" "High error count in logs: $error_count"
        else
            record_check "Application Errors" "PASS" "Error count acceptable: $error_count"
        fi
    else
        record_check "Log Directory" "WARN" "Log directory not found"
    fi
    
    # Check disk space for logs
    local log_space=$(du -sh /var/log 2>/dev/null | cut -f1 || echo "unknown")
    record_check "Log Disk Usage" "PASS" "Log directory size: $log_space"
}

# Monitoring checks
check_monitoring() {
    info "Checking monitoring services..."
    
    # Prometheus
    if curl -f -s --connect-timeout "$HEALTH_CHECK_TIMEOUT" "http://localhost:9090/-/healthy" &>/dev/null; then
        record_check "Prometheus" "PASS" "Prometheus responding"
    else
        record_check "Prometheus" "WARN" "Prometheus not responding"
    fi
    
    # Grafana
    if curl -f -s --connect-timeout "$HEALTH_CHECK_TIMEOUT" "http://localhost:3001/api/health" &>/dev/null; then
        record_check "Grafana" "PASS" "Grafana responding"
    else
        record_check "Grafana" "WARN" "Grafana not responding"
    fi
    
    # Loki
    if curl -f -s --connect-timeout "$HEALTH_CHECK_TIMEOUT" "http://localhost:3100/ready" &>/dev/null; then
        record_check "Loki" "PASS" "Loki responding"
    else
        record_check "Loki" "WARN" "Loki not responding"
    fi
}

# Backup system checks
check_backup_system() {
    info "Checking backup system..."
    
    local backup_dir="/var/backups/ai-validation"
    if [[ -d "$backup_dir" ]]; then
        local latest_backup=$(ls -t "$backup_dir"/*manifest*.json 2>/dev/null | head -1 || echo "")
        if [[ -n "$latest_backup" ]]; then
            local backup_age=$(stat -c %Y "$latest_backup")
            local current_time=$(date +%s)
            local age_hours=$(( (current_time - backup_age) / 3600 ))
            
            if [[ $age_hours -lt 25 ]]; then  # Within 25 hours (daily backup)
                record_check "Backup Recency" "PASS" "Latest backup is $age_hours hours old"
            else
                record_check "Backup Recency" "WARN" "Latest backup is $age_hours hours old"
            fi
        else
            record_check "Backup Recency" "WARN" "No backup manifests found"
        fi
        
        record_check "Backup Directory" "PASS" "Backup directory exists"
    else
        record_check "Backup Directory" "WARN" "Backup directory not found"
    fi
    
    # Check backup script
    if [[ -f "/usr/local/bin/backup-ai-validation.sh" ]]; then
        record_check "Backup Script" "PASS" "Backup script installed"
    else
        record_check "Backup Script" "WARN" "Backup script not found"
    fi
}

# Performance benchmarks
check_performance() {
    info "Checking performance metrics..."
    
    # Response time check
    local start_time=$(date +%s.%N)
    if curl -f -s --connect-timeout "$HEALTH_CHECK_TIMEOUT" "http://localhost:8000/health" &>/dev/null; then
        local end_time=$(date +%s.%N)
        local response_time=$(echo "$end_time - $start_time" | bc -l)
        local response_ms=$(echo "$response_time * 1000" | bc -l | cut -d. -f1)
        
        if [[ $response_ms -lt 1000 ]]; then
            record_check "API Response Time" "PASS" "Response time: ${response_ms}ms"
        else
            record_check "API Response Time" "WARN" "Slow response time: ${response_ms}ms"
        fi
    else
        record_check "API Response Time" "FAIL" "API not responding for performance test"
    fi
    
    # Database query performance
    local db_start=$(date +%s.%N)
    if docker exec ai_validation_postgres psql -U postgres -d vru_validation_prod -c "SELECT COUNT(*) FROM information_schema.tables;" &>/dev/null; then
        local db_end=$(date +%s.%N)
        local db_time=$(echo "$db_end - $db_start" | bc -l)
        local db_ms=$(echo "$db_time * 1000" | bc -l | cut -d. -f1)
        
        if [[ $db_ms -lt 500 ]]; then
            record_check "Database Query Time" "PASS" "Query time: ${db_ms}ms"
        else
            record_check "Database Query Time" "WARN" "Slow query time: ${db_ms}ms"
        fi
    else
        record_check "Database Query Time" "FAIL" "Database query failed"
    fi
}

# Generate health report
generate_report() {
    echo ""
    log "Health Check Summary"
    echo "=================================="
    echo "Date: $(date)"
    echo "Server: $(hostname) ($EXTERNAL_IP)"
    echo "Total Checks: $TOTAL_CHECKS"
    echo "Passed: $PASSED_CHECKS"
    echo "Warnings: $WARNING_CHECKS"
    echo "Failed: $FAILED_CHECKS"
    echo ""
    
    # Overall status
    if [[ $FAILED_CHECKS -eq 0 ]]; then
        if [[ $WARNING_CHECKS -eq 0 ]]; then
            log "Overall Status: HEALTHY ✓"
            OVERALL_STATUS="HEALTHY"
        else
            warn "Overall Status: WARNING ⚠"
            OVERALL_STATUS="WARNING"
        fi
    else
        error "Overall Status: CRITICAL ✗"
        OVERALL_STATUS="CRITICAL"
    fi
    
    echo ""
    echo "Detailed Results:"
    echo "=================="
    
    # Sort and display results
    for check in $(printf '%s\n' "${!HEALTH_STATUS[@]}" | sort); do
        local status_info="${HEALTH_STATUS[$check]}"
        local status="${status_info%%:*}"
        local message="${status_info#*:}"
        
        case "$status" in
            "PASS") echo -e "${GREEN}✓ $check: $message${NC}" ;;
            "WARN") echo -e "${YELLOW}⚠ $check: $message${NC}" ;;
            "FAIL") echo -e "${RED}✗ $check: $message${NC}" ;;
        esac
    done
    
    echo ""
    echo "Next Steps:"
    if [[ $FAILED_CHECKS -gt 0 ]]; then
        echo "- Address failed checks immediately"
        echo "- Review logs for detailed error information"
        echo "- Consider running: ./scripts/startup.sh --restart"
    fi
    
    if [[ $WARNING_CHECKS -gt 0 ]]; then
        echo "- Review warnings and consider optimization"
        echo "- Monitor trends over time"
    fi
    
    echo "- Check monitoring dashboards: https://$EXTERNAL_IP/grafana/"
    echo "- Review logs: docker-compose -f $COMPOSE_FILE logs -f"
    echo "=================================="
    
    # Log to file
    {
        echo "$(date): Health check completed - Status: $OVERALL_STATUS, Passed: $PASSED_CHECKS, Warnings: $WARNING_CHECKS, Failed: $FAILED_CHECKS"
        for check in $(printf '%s\n' "${!HEALTH_STATUS[@]}" | sort); do
            echo "$(date): $check - ${HEALTH_STATUS[$check]}"
        done
    } >> "$LOG_FILE" 2>/dev/null || true
}

# Send notifications
send_notifications() {
    local status="$1"
    
    # Email notification (if configured)
    if [[ -n "${HEALTH_CHECK_EMAIL:-}" ]] && command -v mail &>/dev/null; then
        local subject="AI Validation Platform Health Check - $status"
        local body="Health check completed with status: $status
        
Passed: $PASSED_CHECKS
Warnings: $WARNING_CHECKS  
Failed: $FAILED_CHECKS
Total: $TOTAL_CHECKS

Server: $(hostname) ($EXTERNAL_IP)
Time: $(date)

For detailed results, check: $LOG_FILE"
        
        echo "$body" | mail -s "$subject" "$HEALTH_CHECK_EMAIL" || true
    fi
    
    # Slack notification (if configured)
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        local color
        case "$status" in
            "HEALTHY") color="good" ;;
            "WARNING") color="warning" ;;
            "CRITICAL") color="danger" ;;
        esac
        
        local payload="{
            \"attachments\": [{
                \"color\": \"$color\",
                \"title\": \"AI Validation Platform Health Check\",
                \"fields\": [
                    {\"title\": \"Status\", \"value\": \"$status\", \"short\": true},
                    {\"title\": \"Server\", \"value\": \"$(hostname) ($EXTERNAL_IP)\", \"short\": true},
                    {\"title\": \"Passed\", \"value\": \"$PASSED_CHECKS\", \"short\": true},
                    {\"title\": \"Warnings\", \"value\": \"$WARNING_CHECKS\", \"short\": true},
                    {\"title\": \"Failed\", \"value\": \"$FAILED_CHECKS\", \"short\": true},
                    {\"title\": \"Total\", \"value\": \"$TOTAL_CHECKS\", \"short\": true}
                ],
                \"footer\": \"Health Check\",
                \"ts\": $(date +%s)
            }]
        }"
        
        curl -X POST -H 'Content-type: application/json' \
            --data "$payload" \
            "$SLACK_WEBHOOK_URL" &>/dev/null || true
    fi
}

# Main function
main() {
    info "Starting comprehensive health check for AI Model Validation Platform..."
    info "Server: $(hostname) (External IP: $EXTERNAL_IP)"
    echo ""
    
    # Load environment if available
    if [[ -f "$PROJECT_ROOT/$ENV_FILE" ]]; then
        source "$PROJECT_ROOT/$ENV_FILE"
    fi
    
    # Run all health checks
    check_system_resources
    check_docker_services
    check_network_connectivity
    check_application_health
    check_database_health
    check_ssl_certificates
    check_external_access
    check_security
    check_logs
    check_monitoring
    check_backup_system
    check_performance
    
    # Generate and display report
    generate_report
    
    # Send notifications
    send_notifications "$OVERALL_STATUS"
    
    # Exit with appropriate code
    if [[ $FAILED_CHECKS -gt 0 ]]; then
        exit 1
    elif [[ $WARNING_CHECKS -gt 0 ]]; then
        exit 2
    else
        exit 0
    fi
}

# Help function
show_help() {
    echo "AI Model Validation Platform - Health Check Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -q, --quick             Quick health check (basic services only)"
    echo "  -v, --verbose           Verbose output"
    echo "  --no-external           Skip external access checks"
    echo "  --no-performance        Skip performance benchmarks"
    echo "  --timeout SECONDS       Health check timeout (default: 10)"
    echo ""
    echo "Environment Variables:"
    echo "  HEALTH_CHECK_EMAIL      Email for notifications"
    echo "  SLACK_WEBHOOK_URL       Slack webhook for notifications"
    echo ""
    echo "Examples:"
    echo "  $0                      # Full health check"
    echo "  $0 --quick             # Quick check only"
    echo "  $0 --timeout 30        # Extended timeout"
    echo ""
    echo "Exit Codes:"
    echo "  0 - All checks passed"
    echo "  1 - Critical failures detected"
    echo "  2 - Warnings detected"
}

# Parse command line arguments
QUICK_CHECK=false
VERBOSE=false
SKIP_EXTERNAL=false
SKIP_PERFORMANCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -q|--quick)
            QUICK_CHECK=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --no-external)
            SKIP_EXTERNAL=true
            shift
            ;;
        --no-performance)
            SKIP_PERFORMANCE=true
            shift
            ;;
        --timeout)
            HEALTH_CHECK_TIMEOUT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Quick check mode
if [[ "$QUICK_CHECK" == "true" ]]; then
    info "Running quick health check..."
    check_docker_services
    check_application_health
    check_database_health
    generate_report
    exit $?
fi

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi