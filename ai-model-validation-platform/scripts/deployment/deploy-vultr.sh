#!/bin/bash

# AI Model Validation Platform - Vultr Production Deployment Script
# This script automates the complete deployment process for Vultr server
# External IP: 155.138.239.131

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
VULTR_IP="155.138.239.131"
COMPOSE_FILE="docker-compose.vultr.yml"
ENV_FILE=".env.vultr"

# Logging
LOG_FILE="/var/log/vultr-deployment.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root. Use sudo only when necessary."
    fi
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check if running on correct server
    CURRENT_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "unknown")
    if [[ "$CURRENT_IP" != "$VULTR_IP" ]]; then
        warn "Current external IP ($CURRENT_IP) doesn't match expected Vultr IP ($VULTR_IP)"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            error "Deployment cancelled"
        fi
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
    fi
    
    # Check available disk space (minimum 10GB)
    AVAILABLE_SPACE=$(df / | awk 'NR==2{print $4}')
    REQUIRED_SPACE=10485760  # 10GB in KB
    if [[ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]]; then
        error "Insufficient disk space. Required: 10GB, Available: $(($AVAILABLE_SPACE/1024/1024))GB"
    fi
    
    # Check available memory (minimum 2GB)
    AVAILABLE_MEMORY=$(free -m | awk 'NR==2{print $7}')
    REQUIRED_MEMORY=2048
    if [[ $AVAILABLE_MEMORY -lt $REQUIRED_MEMORY ]]; then
        warn "Low available memory. Required: 2GB, Available: ${AVAILABLE_MEMORY}MB"
    fi
    
    log "System requirements check completed"
}

# Setup firewall
setup_firewall() {
    log "Configuring firewall..."
    
    # Install UFW if not present
    if ! command -v ufw &> /dev/null; then
        info "Installing UFW..."
        sudo apt update
        sudo apt install -y ufw
    fi
    
    # Reset UFW to default
    sudo ufw --force reset
    
    # Set default policies
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    
    # Allow SSH (be careful not to lock yourself out)
    sudo ufw allow ssh
    sudo ufw allow 22/tcp
    
    # Allow HTTP and HTTPS
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    
    # Allow specific monitoring ports (from localhost only)
    sudo ufw allow from 127.0.0.1 to any port 9090  # Prometheus
    sudo ufw allow from 127.0.0.1 to any port 3001  # Grafana
    sudo ufw allow from 127.0.0.1 to any port 3100  # Loki
    
    # Allow Docker subnet
    sudo ufw allow from 172.21.0.0/16
    
    # Rate limiting for SSH
    sudo ufw limit ssh
    
    # Enable firewall
    sudo ufw --force enable
    
    # Display status
    sudo ufw status verbose
    
    log "Firewall configuration completed"
}

# Install dependencies
install_dependencies() {
    log "Installing system dependencies..."
    
    # Update system
    sudo apt update && sudo apt upgrade -y
    
    # Install required packages
    sudo apt install -y \
        curl \
        wget \
        git \
        unzip \
        htop \
        tree \
        jq \
        certbot \
        python3-certbot-nginx \
        logrotate \
        fail2ban \
        cron \
        rsync \
        openssl
    
    # Install Docker if not present
    if ! command -v docker &> /dev/null; then
        info "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
    fi
    
    # Install Docker Compose if not present
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        info "Installing Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi
    
    log "Dependencies installation completed"
}

# Setup SSL certificates
setup_ssl() {
    log "Setting up SSL certificates..."
    
    # Create SSL directory
    sudo mkdir -p /etc/nginx/ssl
    
    # Check if domain is configured
    if grep -q "your-domain.com" "$PROJECT_ROOT/$ENV_FILE"; then
        warn "Domain not configured in $ENV_FILE. Using self-signed certificates."
        
        # Generate self-signed certificate
        info "Generating self-signed certificate..."
        sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout /etc/nginx/ssl/private.key \
            -out /etc/nginx/ssl/cert.pem \
            -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=$VULTR_IP"
    else
        # Get domain from environment file
        DOMAIN=$(grep "DOMAIN_NAME=" "$PROJECT_ROOT/$ENV_FILE" | cut -d'=' -f2)
        EMAIL=$(grep "SSL_EMAIL=" "$PROJECT_ROOT/$ENV_FILE" | cut -d'=' -f2)
        
        if [[ -n "$DOMAIN" && "$DOMAIN" != "your-domain.com" ]]; then
            info "Setting up Let's Encrypt certificate for $DOMAIN..."
            
            # Get Let's Encrypt certificate
            sudo certbot certonly --standalone \
                --email "$EMAIL" \
                --agree-tos \
                --no-eff-email \
                -d "$DOMAIN"
            
            # Copy certificates to nginx directory
            sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" /etc/nginx/ssl/cert.pem
            sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" /etc/nginx/ssl/private.key
            
            # Setup auto-renewal
            echo "0 12 * * * /usr/bin/certbot renew --quiet" | sudo tee -a /etc/crontab
        else
            error "Please configure DOMAIN_NAME and SSL_EMAIL in $ENV_FILE"
        fi
    fi
    
    # Generate DH parameters
    if [[ ! -f /etc/nginx/ssl/dhparam.pem ]]; then
        info "Generating DH parameters (this may take several minutes)..."
        sudo openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048
    fi
    
    # Set proper permissions
    sudo chmod 600 /etc/nginx/ssl/private.key
    sudo chmod 644 /etc/nginx/ssl/cert.pem /etc/nginx/ssl/dhparam.pem
    
    log "SSL certificates setup completed"
}

# Prepare environment
prepare_environment() {
    log "Preparing deployment environment..."
    
    cd "$PROJECT_ROOT"
    
    # Check if environment file exists
    if [[ ! -f "$ENV_FILE" ]]; then
        error "Environment file $ENV_FILE not found. Please create it first."
    fi
    
    # Validate required environment variables
    REQUIRED_VARS=(
        "POSTGRES_PASSWORD"
        "REDIS_PASSWORD"
        "AIVALIDATION_SECRET_KEY"
        "CVAT_POSTGRES_PASSWORD"
        "GRAFANA_PASSWORD"
    )
    
    for var in "${REQUIRED_VARS[@]}"; do
        if ! grep -q "^$var=" "$ENV_FILE" || grep -q "change_me\|GENERATE\|your-" "$ENV_FILE"; then
            error "Please configure $var in $ENV_FILE with a secure value"
        fi
    done
    
    # Create required directories
    sudo mkdir -p /var/log/ai-validation/{nginx,postgres,redis,backend,frontend}
    sudo mkdir -p /var/www/html /var/www/certbot /var/www/uploads
    
    # Set permissions
    sudo chown -R $USER:$USER "$PROJECT_ROOT"
    sudo chown -R www-data:www-data /var/www
    sudo chown -R $USER:$USER /var/log/ai-validation
    
    # Create log rotation configuration
    sudo tee /etc/logrotate.d/ai-validation > /dev/null <<EOF
/var/log/ai-validation/*/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    postrotate
        docker kill -s USR1 ai_validation_nginx 2>/dev/null || true
    endscript
}
EOF
    
    log "Environment preparation completed"
}

# Build Docker images
build_images() {
    log "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Create production Dockerfiles if they don't exist
    if [[ ! -f "backend/Dockerfile.prod" ]]; then
        info "Creating production Dockerfile for backend..."
        cp "backend/Dockerfile" "backend/Dockerfile.prod"
        # Add production optimizations to Dockerfile.prod
        cat >> "backend/Dockerfile.prod" <<EOF

# Production optimizations
RUN pip install --no-cache-dir gunicorn
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
EOF
    fi
    
    if [[ ! -f "frontend/Dockerfile.prod" ]]; then
        info "Creating production Dockerfile for frontend..."
        cat > "frontend/Dockerfile.prod" <<EOF
# Multi-stage build for React frontend
FROM node:18-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Production server
FROM nginx:1.25-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
EOF
    fi
    
    # Build images with no cache for production
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache
    
    log "Docker images built successfully"
}

# Deploy services
deploy_services() {
    log "Deploying services..."
    
    cd "$PROJECT_ROOT"
    
    # Stop existing services if running
    if docker-compose -f "$COMPOSE_FILE" ps -q | grep -q .; then
        info "Stopping existing services..."
        docker-compose -f "$COMPOSE_FILE" down --remove-orphans
    fi
    
    # Remove old volumes if needed (be careful with data loss)
    # docker-compose -f "$COMPOSE_FILE" down -v
    
    # Pull latest images
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull
    
    # Start services
    info "Starting services..."
    docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    
    # Wait for services to be healthy
    info "Waiting for services to be healthy..."
    sleep 30
    
    # Check service status
    docker-compose -f "$COMPOSE_FILE" ps
    
    log "Services deployment completed"
}

# Setup monitoring
setup_monitoring() {
    log "Setting up monitoring..."
    
    # Create monitoring configuration files
    mkdir -p "$PROJECT_ROOT/scripts/monitoring"
    
    # Copy configuration files to containers
    if docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps prometheus | grep -q Up; then
        info "Monitoring services are running"
    else
        warn "Monitoring services are not running properly"
    fi
    
    log "Monitoring setup completed"
}

# Run health checks
run_health_checks() {
    log "Running health checks..."
    
    # Check services
    SERVICES=(
        "http://localhost:80/health"
        "https://localhost:443/health"
        "http://localhost:8000/health"
        "http://localhost:3000"
    )
    
    for service in "${SERVICES[@]}"; do
        info "Checking $service..."
        if curl -f -s --connect-timeout 10 "$service" > /dev/null; then
            log "✓ $service is healthy"
        else
            warn "✗ $service is not responding"
        fi
    done
    
    # Check external access
    info "Checking external access..."
    EXTERNAL_IP=$(curl -s ifconfig.me || echo "unknown")
    if [[ "$EXTERNAL_IP" == "$VULTR_IP" ]]; then
        log "✓ External IP matches: $EXTERNAL_IP"
    else
        warn "✗ External IP mismatch: Expected $VULTR_IP, Got $EXTERNAL_IP"
    fi
    
    log "Health checks completed"
}

# Setup backup
setup_backup() {
    log "Setting up backup system..."
    
    # Create backup script
    sudo tee /usr/local/bin/backup-ai-validation.sh > /dev/null <<EOF
#!/bin/bash
# AI Validation Platform Backup Script

BACKUP_DIR="/var/backups/ai-validation"
DATE=\$(date +%Y%m%d_%H%M%S)
PROJECT_ROOT="$PROJECT_ROOT"

mkdir -p "\$BACKUP_DIR"

# Backup databases
docker exec ai_validation_postgres pg_dump -U postgres vru_validation_prod > "\$BACKUP_DIR/postgres_\$DATE.sql"
docker exec ai_validation_redis redis-cli --rdb /data/backup.rdb
docker cp ai_validation_redis:/data/backup.rdb "\$BACKUP_DIR/redis_\$DATE.rdb"

# Backup volumes
docker run --rm -v ai-model-validation-platform_uploaded_videos:/data -v \$BACKUP_DIR:/backup ubuntu tar czf /backup/uploads_\$DATE.tar.gz -C /data .

# Backup configuration
cp -r "\$PROJECT_ROOT" "\$BACKUP_DIR/config_\$DATE/"

# Clean old backups (keep 7 days)
find "\$BACKUP_DIR" -name "*.sql" -mtime +7 -delete
find "\$BACKUP_DIR" -name "*.rdb" -mtime +7 -delete
find "\$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
find "\$BACKUP_DIR" -name "config_*" -mtime +7 -exec rm -rf {} +

echo "Backup completed: \$DATE"
EOF
    
    sudo chmod +x /usr/local/bin/backup-ai-validation.sh
    
    # Add to cron
    echo "0 2 * * * /usr/local/bin/backup-ai-validation.sh" | sudo tee -a /etc/crontab
    
    log "Backup system setup completed"
}

# Display summary
display_summary() {
    log "Deployment Summary"
    echo "=================================="
    echo "External IP: $VULTR_IP"
    echo "Application URL: https://$VULTR_IP (or your domain)"
    echo "Monitoring: https://$VULTR_IP/grafana"
    echo "CVAT: https://$VULTR_IP/cvat"
    echo ""
    echo "Services Status:"
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" ps
    echo ""
    echo "Next Steps:"
    echo "1. Update DNS records if using a domain"
    echo "2. Test external access from another machine"
    echo "3. Configure monitoring alerts"
    echo "4. Review security settings"
    echo "5. Test backup and restore procedures"
    echo ""
    echo "Configuration files:"
    echo "- Environment: $PROJECT_ROOT/$ENV_FILE"
    echo "- Docker Compose: $PROJECT_ROOT/$COMPOSE_FILE"
    echo "- Nginx Config: $PROJECT_ROOT/scripts/nginx/"
    echo "- SSL Certificates: /etc/nginx/ssl/"
    echo ""
    echo "Logs:"
    echo "- Deployment: $LOG_FILE"
    echo "- Application: $PROJECT_ROOT/logs/"
    echo "- System: /var/log/"
    echo ""
    echo "Backup:"
    echo "- Location: /var/backups/ai-validation/"
    echo "- Schedule: Daily at 2:00 AM UTC"
    echo "=================================="
}

# Main deployment function
main() {
    log "Starting Vultr production deployment..."
    
    check_root
    check_requirements
    install_dependencies
    setup_firewall
    prepare_environment
    setup_ssl
    build_images
    deploy_services
    setup_monitoring
    setup_backup
    run_health_checks
    display_summary
    
    log "Vultr deployment completed successfully!"
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi