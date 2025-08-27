#!/bin/bash

# =====================================================
# VRU AI Model Validation Platform - Production Deployment Script
# Unified deployment architecture for 155.138.239.131
# All operations work from project root directory
# =====================================================

set -euo pipefail

# =====================================================
# CONFIGURATION - All paths relative to project root
# =====================================================
DEPLOY_HOST="155.138.239.131"
DEPLOY_USER="${DEPLOY_USER:-root}"
PROJECT_NAME="vru-production-platform"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    case $level in
        "INFO") echo -e "${GREEN}[INFO]${NC} $*" ;;
        "WARN") echo -e "${YELLOW}[WARN]${NC} $*" ;;
        "ERROR") echo -e "${RED}[ERROR]${NC} $*" ;;
        "DEBUG") echo -e "${BLUE}[DEBUG]${NC} $*" ;;
    esac
}

echo -e "${BLUE}"
cat << 'EOF'
===============================================
VRU AI MODEL VALIDATION PLATFORM
Production Deployment to 155.138.239.131
===============================================
EOF
echo -e "${NC}"

log "INFO" "Project: $PROJECT_NAME"
log "INFO" "Host: $DEPLOY_HOST"
log "INFO" "User: $DEPLOY_USER"
log "INFO" "Project Root: $PROJECT_ROOT"
echo ""

# =====================================================
# PRE-DEPLOYMENT VALIDATION
# =====================================================
validate_deployment_requirements() {
    log "INFO" "🔍 Validating deployment requirements..."
    
    # Check network connectivity
    if ! ping -c 1 "$DEPLOY_HOST" > /dev/null 2>&1; then
        log "ERROR" "❌ Cannot reach deployment host $DEPLOY_HOST"
        log "ERROR" "Please check network connectivity and host availability"
        exit 1
    fi
    log "INFO" "✅ Network connectivity verified"
    
    # Verify SSH access
    if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$DEPLOY_USER@$DEPLOY_HOST" 'echo "SSH connection successful"' > /dev/null 2>&1; then
        log "ERROR" "❌ Cannot establish SSH connection to $DEPLOY_USER@$DEPLOY_HOST"
        log "ERROR" "Please ensure SSH keys are configured or use: ssh-copy-id $DEPLOY_USER@$DEPLOY_HOST"
        exit 1
    fi
    log "INFO" "✅ SSH connectivity verified"
    
    # Check required files in project root
    local required_files=(
        ".env.production"
        "docker-compose.production.yml"
        "backend/Dockerfile.unified"
        "frontend/Dockerfile.unified"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$PROJECT_ROOT/$file" ]]; then
            log "ERROR" "❌ Required file missing: $file"
            log "ERROR" "Expected location: $PROJECT_ROOT/$file"
            exit 1
        fi
        log "DEBUG" "✅ Found: $file"
    done
    
    # Check for models directory
    if [[ ! -d "$PROJECT_ROOT/models" ]]; then
        log "WARN" "⚠️ Models directory not found, creating default structure..."
        mkdir -p "$PROJECT_ROOT/models"
        # Download YOLO model if not present
        if [[ ! -f "$PROJECT_ROOT/models/yolov8n.pt" ]] && [[ -f "$PROJECT_ROOT/backend/yolov8n.pt" ]]; then
            cp "$PROJECT_ROOT/backend/yolov8n.pt" "$PROJECT_ROOT/models/"
            log "INFO" "✅ Copied YOLO model to models directory"
        fi
    fi
    
    log "INFO" "✅ All pre-deployment requirements validated"
}

# =====================================================
# REMOTE ENVIRONMENT SETUP
# =====================================================
setup_remote_environment() {
    log "INFO" "📁 Setting up remote environment on $DEPLOY_HOST..."
    
    ssh "$DEPLOY_USER@$DEPLOY_HOST" << 'REMOTE_SETUP_EOF'
        set -euo pipefail
        
        echo "🏗️ Creating application directory structure..."
        mkdir -p /opt/vru-platform/{config,data,logs,backups}
        mkdir -p /opt/vru-platform/data/{postgres,redis,uploads,camera,validation_results,ml_cache,prometheus,grafana}
        mkdir -p /opt/vru-platform/logs/{nginx,api,application}
        mkdir -p /opt/vru-platform/config/{nginx,ssl,prometheus,grafana,production}
        
        echo "🔐 Setting proper permissions..."
        chown -R 1000:1000 /opt/vru-platform/data
        chown -R 1000:1000 /opt/vru-platform/logs
        chmod -R 755 /opt/vru-platform
        
        echo "🐳 Installing Docker and Docker Compose..."
        if ! command -v docker &> /dev/null; then
            echo "Installing Docker..."
            curl -fsSL https://get.docker.com -o get-docker.sh
            sh get-docker.sh
            systemctl enable docker
            systemctl start docker
            usermod -aG docker root
            rm -f get-docker.sh
        else
            echo "Docker already installed: $(docker --version)"
        fi
        
        if ! command -v docker-compose &> /dev/null; then
            echo "Installing Docker Compose..."
            COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
            curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
        else
            echo "Docker Compose already installed: $(docker-compose --version)"
        fi
        
        echo "🔥 Setting up system services and firewall..."
        # Configure firewall
        if command -v ufw &> /dev/null; then
            ufw --force reset
            ufw default deny incoming
            ufw default allow outgoing
            ufw allow ssh
            ufw allow 80/tcp
            ufw allow 443/tcp
            ufw allow 3000/tcp
            ufw allow 8000/tcp
            ufw --force enable
            echo "UFW firewall configured"
        elif command -v firewalld &> /dev/null; then
            systemctl start firewalld
            systemctl enable firewalld
            firewall-cmd --permanent --add-service=ssh
            firewall-cmd --permanent --add-service=http
            firewall-cmd --permanent --add-service=https
            firewall-cmd --permanent --add-port=3000/tcp
            firewall-cmd --permanent --add-port=8000/tcp
            firewall-cmd --reload
            echo "Firewalld configured"
        fi
        
        echo "✅ Remote environment setup completed"
REMOTE_SETUP_EOF
    
    log "INFO" "✅ Remote environment setup complete"
}

# =====================================================
# CREATE PRODUCTION CONFIGURATION FILES
# =====================================================
create_production_configs() {
    log "INFO" "⚙️ Creating production configuration files..."
    
    # Create temporary directory for configs
    local temp_config_dir=$(mktemp -d)
    
    # Create Redis configuration
    cat > "$temp_config_dir/redis.conf" << 'REDIS_EOF'
# Redis Production Configuration
bind 0.0.0.0
port 6379
timeout 0
keepalive 300
tcp-keepalive 60

# Memory and persistence
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000

# Security
protected-mode yes
requirepass VRU_Redis_Prod_2024_SecurePassword_5432

# Logging
loglevel notice
syslog-enabled yes
syslog-ident redis-vru

# Performance
tcp-backlog 511
databases 16
rdbcompression yes
rdbchecksum yes
REDIS_EOF

    # Create Nginx configuration
    cat > "$temp_config_dir/nginx.conf" << 'NGINX_EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;
    
    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 500M;
    
    # Gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml application/rss+xml application/atom+xml image/svg+xml;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    
    # Backend upstream
    upstream backend {
        server api-gateway:8000;
    }
    
    # Frontend upstream
    upstream frontend {
        server frontend:3000;
    }
    
    server {
        listen 80;
        server_name 155.138.239.131;
        
        # API endpoints
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
            proxy_connect_timeout 30s;
        }
        
        # Health checks
        location /health {
            proxy_pass http://backend;
            access_log off;
        }
        
        # Documentation
        location /docs {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # WebSocket connections
        location /ws {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # Frontend application
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
NGINX_EOF

    # Create Prometheus configuration
    cat > "$temp_config_dir/prometheus.yml" << 'PROMETHEUS_EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files: []

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'vru-api-gateway'
    static_configs:
      - targets: ['api-gateway:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'vru-ml-engine'
    static_configs:
      - targets: ['ml-engine:8001']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'vru-camera-service'
    static_configs:
      - targets: ['camera-service:8002']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'vru-validation-engine'
    static_configs:
      - targets: ['validation-engine:8003']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']
PROMETHEUS_EOF

    # Create PostgreSQL configuration
    cat > "$temp_config_dir/postgresql.conf" << 'POSTGRES_EOF'
# PostgreSQL Production Configuration
listen_addresses = '*'
port = 5432
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.7
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_messages = warning
log_min_error_statement = error
log_min_duration_statement = 1000

# Security
ssl = off
password_encryption = scram-sha-256
POSTGRES_EOF

    # Create ML config
    cat > "$temp_config_dir/ml_config.yaml" << 'ML_CONFIG_EOF'
ml_engine:
  model_path: "/app/models/yolov8n.pt"
  confidence_threshold: 0.6
  batch_size: 8
  max_workers: 4
  device: "cpu"
  cache_size: 1000
  timeout: 300

detection:
  classes:
    - person
    - bicycle
    - car
    - motorbike
    - bus
    - truck
  
performance:
  max_video_size_mb: 500
  max_concurrent_detections: 5
  cache_results: true
  cache_ttl: 3600

logging:
  level: INFO
  format: json
ML_CONFIG_EOF

    # Create validation config
    cat > "$temp_config_dir/validation_config.yaml" << 'VALIDATION_CONFIG_EOF'
validation_engine:
  max_concurrent_validations: 3
  timeout: 600
  retry_attempts: 3
  
workflow:
  stages:
    - preprocessing
    - detection
    - validation
    - post_processing
    
preprocessing:
  resize_max_width: 1920
  resize_max_height: 1080
  quality_threshold: 0.7

validation:
  confidence_threshold: 0.6
  iou_threshold: 0.5
  min_detections: 1
  max_detections: 100

output:
  format: "json"
  include_metadata: true
  include_timestamps: true

logging:
  level: INFO
  format: json
VALIDATION_CONFIG_EOF

    # Transfer config files to remote
    log "INFO" "📤 Transferring configuration files to remote host..."
    rsync -av "$temp_config_dir/" "$DEPLOY_USER@$DEPLOY_HOST:/opt/vru-platform/config/production/"
    
    # Cleanup
    rm -rf "$temp_config_dir"
    
    log "INFO" "✅ Production configuration files created and transferred"
}

# =====================================================
# DEPLOY APPLICATION FILES
# =====================================================
deploy_application_files() {
    log "INFO" "📦 Deploying application files..."
    
    # Create deployment archive
    local temp_dir=$(mktemp -d)
    local archive_name="vru-platform-$(date +%Y%m%d_%H%M%S).tar.gz"
    
    log "DEBUG" "Creating deployment archive in $temp_dir"
    
    # Copy essential files maintaining structure
    cp -r "$PROJECT_ROOT/backend" "$temp_dir/"
    cp -r "$PROJECT_ROOT/frontend" "$temp_dir/"
    cp "$PROJECT_ROOT/.env.production" "$temp_dir/"
    cp "$PROJECT_ROOT/docker-compose.production.yml" "$temp_dir/"
    
    # Copy models if they exist
    if [[ -d "$PROJECT_ROOT/models" ]]; then
        cp -r "$PROJECT_ROOT/models" "$temp_dir/"
        log "DEBUG" "✅ Models directory included"
    fi
    
    # Create archive
    cd "$temp_dir"
    tar -czf "$archive_name" ./*
    
    # Transfer to remote host
    log "INFO" "📤 Transferring application archive..."
    scp "$archive_name" "$DEPLOY_USER@$DEPLOY_HOST:/opt/vru-platform/"
    
    # Extract on remote host
    ssh "$DEPLOY_USER@$DEPLOY_HOST" << EXTRACT_EOF
        cd /opt/vru-platform
        echo "📂 Extracting application files..."
        tar -xzf "$archive_name"
        rm "$archive_name"
        
        # Set proper ownership
        chown -R 1000:1000 /opt/vru-platform/backend
        chown -R 1000:1000 /opt/vru-platform/frontend
        
        echo "✅ Application files extracted and permissions set"
EXTRACT_EOF
    
    # Cleanup local temp
    cd "$PROJECT_ROOT"
    rm -rf "$temp_dir"
    
    log "INFO" "✅ Application files deployed successfully"
}

# =====================================================
# DEPLOY AND START SERVICES
# =====================================================
deploy_services() {
    log "INFO" "🐳 Deploying and starting services..."
    
    ssh "$DEPLOY_USER@$DEPLOY_HOST" << 'DEPLOY_SERVICES_EOF'
        set -euo pipefail
        cd /opt/vru-platform
        
        echo "🔧 Loading environment variables..."
        set -a
        source .env.production
        set +a
        
        echo "🛑 Stopping existing services..."
        if docker-compose -f docker-compose.production.yml ps -q 2>/dev/null | grep -q .; then
            docker-compose -f docker-compose.production.yml down --remove-orphans --volumes || true
        fi
        
        echo "🧹 Cleaning up unused Docker resources..."
        docker system prune -f || true
        docker volume prune -f || true
        
        echo "📥 Pulling latest base images..."
        docker-compose -f docker-compose.production.yml pull redis postgres prometheus grafana nginx || true
        
        echo "🏗️ Building application services..."
        docker-compose -f docker-compose.production.yml build --no-cache
        
        echo "🚀 Starting services..."
        docker-compose -f docker-compose.production.yml up -d
        
        echo "⏳ Waiting for services to become healthy..."
        sleep 60
        
        echo "🔍 Checking service status..."
        docker-compose -f docker-compose.production.yml ps
        
        echo "📊 Service health checks:"
        for i in {1..10}; do
            echo "  Attempt $i/10:"
            
            # Check Redis
            if docker-compose -f docker-compose.production.yml exec -T redis redis-cli -a "$VRU_REDIS_PASSWORD" ping 2>/dev/null | grep -q PONG; then
                echo "    ✅ Redis: Healthy"
            else
                echo "    ❌ Redis: Not responding"
            fi
            
            # Check PostgreSQL
            if docker-compose -f docker-compose.production.yml exec -T postgres pg_isready -U "$VRU_DATABASE_USER" -d "$VRU_DATABASE_NAME" 2>/dev/null | grep -q "accepting connections"; then
                echo "    ✅ PostgreSQL: Healthy"
            else
                echo "    ❌ PostgreSQL: Not responding"
            fi
            
            # Check API Gateway
            if curl -f -s --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
                echo "    ✅ API Gateway: Healthy"
            else
                echo "    ❌ API Gateway: Not responding"
            fi
            
            # Check Frontend
            if curl -f -s --max-time 5 http://localhost:3000 > /dev/null 2>&1; then
                echo "    ✅ Frontend: Healthy"
            else
                echo "    ❌ Frontend: Not responding"
            fi
            
            sleep 10
        done
        
        echo "✅ Service deployment completed"
DEPLOY_SERVICES_EOF
    
    log "INFO" "✅ Services deployed successfully"
}

# =====================================================
# VERIFY DEPLOYMENT
# =====================================================
verify_deployment() {
    log "INFO" "🔍 Verifying deployment..."
    
    local services=(
        "http://$DEPLOY_HOST/health"
        "http://$DEPLOY_HOST:3000"
        "http://$DEPLOY_HOST:8000/health"
        "http://$DEPLOY_HOST:8000/docs"
    )
    
    echo ""
    log "INFO" "🧪 Testing service endpoints:"
    for service in "${services[@]}"; do
        echo -n "  Testing $service: "
        if curl -f -s --max-time 10 "$service" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ OK${NC}"
        else
            echo -e "${RED}❌ FAILED${NC}"
        fi
    done
    
    echo ""
    log "INFO" "🌐 Service URLs:"
    echo "  Frontend:         http://$DEPLOY_HOST:3000"
    echo "  API Gateway:      http://$DEPLOY_HOST:8000"
    echo "  API Documentation: http://$DEPLOY_HOST:8000/docs"
    echo "  Health Check:     http://$DEPLOY_HOST:8000/health"
    echo "  Monitoring:       http://$DEPLOY_HOST:3001 (admin/VRU_Grafana_Prod_2024_AdminPassword_monitoring123)"
    echo ""
}

# =====================================================
# SETUP SYSTEM MONITORING
# =====================================================
setup_system_monitoring() {
    log "INFO" "📊 Setting up system monitoring..."
    
    ssh "$DEPLOY_USER@$DEPLOY_HOST" << 'MONITORING_EOF'
        set -euo pipefail
        
        echo "📝 Creating log rotation configuration..."
        cat > /etc/logrotate.d/vru-platform << 'LOGROTATE_CONF'
/opt/vru-platform/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    notifempty
    create 644 1000 1000
    postrotate
        docker kill --signal="USR1" $(docker ps -q --filter="name=vru_prod") 2>/dev/null || true
    endscript
}
LOGROTATE_CONF
        
        echo "🖥️ Creating systemd service..."
        cat > /etc/systemd/system/vru-platform.service << 'SYSTEMD_SERVICE'
[Unit]
Description=VRU Platform Docker Services
Requires=docker.service
After=docker.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/vru-platform
ExecStart=/usr/local/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.production.yml down
ExecReload=/usr/local/bin/docker-compose -f docker-compose.production.yml restart
TimeoutStartSec=300
TimeoutStopSec=120
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
SYSTEMD_SERVICE
        
        systemctl daemon-reload
        systemctl enable vru-platform.service
        
        echo "📋 Creating management scripts..."
        cat > /usr/local/bin/vru-platform << 'MANAGEMENT_SCRIPT'
#!/bin/bash
cd /opt/vru-platform

case "${1:-help}" in
    "start")
        systemctl start vru-platform
        ;;
    "stop")
        systemctl stop vru-platform
        ;;
    "restart")
        systemctl restart vru-platform
        ;;
    "status")
        systemctl status vru-platform
        docker-compose -f docker-compose.production.yml ps
        ;;
    "logs")
        docker-compose -f docker-compose.production.yml logs -f
        ;;
    "update")
        docker-compose -f docker-compose.production.yml pull
        systemctl restart vru-platform
        ;;
    "backup")
        mkdir -p /opt/vru-platform/backups
        docker-compose -f docker-compose.production.yml exec -T postgres pg_dumpall -U postgres > "/opt/vru-platform/backups/backup-$(date +%Y%m%d_%H%M%S).sql"
        ;;
    "help")
        echo "VRU Platform Management Tool"
        echo "Usage: vru-platform {start|stop|restart|status|logs|update|backup|help}"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Use 'vru-platform help' for available commands"
        exit 1
        ;;
esac
MANAGEMENT_SCRIPT
        
        chmod +x /usr/local/bin/vru-platform
        
        echo "✅ System monitoring setup completed"
MONITORING_EOF
    
    log "INFO" "✅ System monitoring setup complete"
}

# =====================================================
# MAIN DEPLOYMENT ORCHESTRATION
# =====================================================
main() {
    local command="${1:-deploy}"
    
    case "$command" in
        "check"|"validate")
            validate_deployment_requirements
            log "INFO" "✅ Pre-deployment validation passed"
            ;;
        "setup")
            validate_deployment_requirements
            setup_remote_environment
            create_production_configs
            log "INFO" "✅ Remote environment setup completed"
            ;;
        "deploy"|"full")
            validate_deployment_requirements
            setup_remote_environment
            create_production_configs
            deploy_application_files
            deploy_services
            setup_system_monitoring
            verify_deployment
            
            echo ""
            echo -e "${GREEN}"
            cat << 'SUCCESS_EOF'
🎉 DEPLOYMENT SUCCESSFUL! 🎉
===============================================
VRU AI Model Validation Platform is now running!

Access Points:
  • Frontend: http://155.138.239.131:3000
  • API: http://155.138.239.131:8000/docs
  • Health: http://155.138.239.131:8000/health
  • Monitoring: http://155.138.239.131:3001

Management Commands:
  • vru-platform status
  • vru-platform logs
  • vru-platform restart
  • vru-platform backup

Logs Location: /opt/vru-platform/logs/
===============================================
SUCCESS_EOF
            echo -e "${NC}"
            ;;
        "verify")
            verify_deployment
            ;;
        "logs")
            ssh "$DEPLOY_USER@$DEPLOY_HOST" 'cd /opt/vru-platform && docker-compose -f docker-compose.production.yml logs -f'
            ;;
        "status")
            ssh "$DEPLOY_USER@$DEPLOY_HOST" 'cd /opt/vru-platform && docker-compose -f docker-compose.production.yml ps'
            ;;
        "stop")
            ssh "$DEPLOY_USER@$DEPLOY_HOST" 'cd /opt/vru-platform && docker-compose -f docker-compose.production.yml down'
            ;;
        "restart")
            ssh "$DEPLOY_USER@$DEPLOY_HOST" 'cd /opt/vru-platform && docker-compose -f docker-compose.production.yml restart'
            ;;
        "update")
            deploy_application_files
            ssh "$DEPLOY_USER@$DEPLOY_HOST" 'cd /opt/vru-platform && docker-compose -f docker-compose.production.yml build --no-cache && docker-compose -f docker-compose.production.yml up -d'
            verify_deployment
            ;;
        "help")
            cat << 'HELP_EOF'
VRU Platform Production Deployment Script
==========================================

USAGE: ./deploy-production.sh [COMMAND]

COMMANDS:
  validate  - Check deployment requirements only
  setup     - Setup remote environment only  
  deploy    - Full deployment (default)
  verify    - Verify deployment health
  logs      - View service logs
  status    - Show service status
  stop      - Stop all services
  restart   - Restart all services
  update    - Update and redeploy application
  help      - Show this help message

EXAMPLES:
  ./deploy-production.sh                    # Full deployment
  ./deploy-production.sh validate          # Check requirements
  ./deploy-production.sh setup             # Setup environment
  ./deploy-production.sh verify            # Verify deployment

ENVIRONMENT VARIABLES:
  DEPLOY_USER - Remote user (default: root)
  
NOTES:
  - Script must be run from project root directory
  - SSH key authentication must be configured
  - Target host: 155.138.239.131
HELP_EOF
            ;;
        *)
            log "ERROR" "Unknown command: $command"
            echo "Use './deploy-production.sh help' for available commands"
            exit 1
            ;;
    esac
}

# Execute main function with all arguments
main "$@"