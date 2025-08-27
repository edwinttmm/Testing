#!/bin/bash

# VRU AI Model Validation Platform - Production Deployment Script
# Deploy complete VRU system to 155.138.239.131

set -euo pipefail

# Configuration
DEPLOY_HOST="155.138.239.131"
DEPLOY_USER="${DEPLOY_USER:-root}"
PROJECT_NAME="vru-production-platform"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 VRU Production Deployment to $DEPLOY_HOST"
echo "=============================================="
echo "Project: $PROJECT_NAME"
echo "Host: $DEPLOY_HOST"
echo "User: $DEPLOY_USER"
echo ""

# Pre-deployment checks
check_requirements() {
    echo "🔍 Checking deployment requirements..."
    
    # Check if we can reach the deployment host
    if ! ping -c 1 "$DEPLOY_HOST" > /dev/null 2>&1; then
        echo "❌ Cannot reach deployment host $DEPLOY_HOST"
        exit 1
    fi
    
    # Check for required files
    local required_files=(
        "docker-compose.production.yml"
        ".env.production"
        "nginx.conf"
        "prometheus.yml"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$SCRIPT_DIR/$file" ]]; then
            echo "❌ Required file missing: $file"
            exit 1
        fi
    done
    
    echo "✅ Pre-deployment checks passed"
}

# Create deployment directory structure on remote host
setup_remote_environment() {
    echo "📁 Setting up remote environment..."
    
    ssh "$DEPLOY_USER@$DEPLOY_HOST" << 'EOF'
        # Create application directory
        mkdir -p /opt/vru-platform/{config,data,logs,backups}
        mkdir -p /opt/vru-platform/data/{postgres,redis,uploads,models,cache}
        mkdir -p /opt/vru-platform/config/{nginx,ssl,prometheus,grafana}
        
        # Set proper permissions
        chown -R 1000:1000 /opt/vru-platform/data
        chmod -R 755 /opt/vru-platform
        
        # Install Docker and Docker Compose if not present
        if ! command -v docker &> /dev/null; then
            curl -fsSL https://get.docker.com -o get-docker.sh
            sh get-docker.sh
            systemctl enable docker
            systemctl start docker
        fi
        
        if ! command -v docker-compose &> /dev/null; then
            curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
        fi
EOF
    
    echo "✅ Remote environment setup complete"
}

# Copy application files to remote host
deploy_application_files() {
    echo "📦 Deploying application files..."
    
    # Create temporary deployment package
    local temp_dir=$(mktemp -d)
    
    # Copy configuration files
    cp -r "$SCRIPT_DIR"/* "$temp_dir/"
    
    # Copy application source code
    rsync -av --exclude='node_modules' --exclude='.git' --exclude='__pycache__' \
        "$PROJECT_ROOT/backend/" "$temp_dir/backend/"
    rsync -av --exclude='node_modules' --exclude='.git' --exclude='build' \
        "$PROJECT_ROOT/frontend/" "$temp_dir/frontend/"
    
    # Copy models if they exist
    if [[ -d "$PROJECT_ROOT/models" ]]; then
        cp -r "$PROJECT_ROOT/models" "$temp_dir/"
    fi
    
    # Transfer to remote host
    rsync -av --delete "$temp_dir/" "$DEPLOY_USER@$DEPLOY_HOST:/opt/vru-platform/"
    
    # Cleanup
    rm -rf "$temp_dir"
    
    echo "✅ Application files deployed"
}

# Deploy and start services
deploy_services() {
    echo "🐳 Deploying services..."
    
    ssh "$DEPLOY_USER@$DEPLOY_HOST" << 'EOF'
        cd /opt/vru-platform
        
        # Load environment variables
        set -a
        source config/production/.env.production
        set +a
        
        # Pull latest images
        docker-compose -f config/production/docker-compose.production.yml pull
        
        # Stop existing services
        docker-compose -f config/production/docker-compose.production.yml down --remove-orphans
        
        # Build and start services
        docker-compose -f config/production/docker-compose.production.yml up --build -d
        
        echo "⏳ Waiting for services to become healthy..."
        sleep 30
        
        # Check service health
        docker-compose -f config/production/docker-compose.production.yml ps
EOF
    
    echo "✅ Services deployed"
}

# Verify deployment
verify_deployment() {
    echo "🔍 Verifying deployment..."
    
    local services=(
        "http://$DEPLOY_HOST/health"
        "http://$DEPLOY_HOST:3000"
        "http://$DEPLOY_HOST:8001/health"
        "http://$DEPLOY_HOST:8002/health"
        "http://$DEPLOY_HOST:8003/health"
    )
    
    for service in "${services[@]}"; do
        echo -n "  Testing $service: "
        if curl -f -s --max-time 10 "$service" > /dev/null; then
            echo "✅ OK"
        else
            echo "❌ FAILED"
        fi
    done
    
    echo ""
    echo "🌐 Service URLs:"
    echo "  Frontend:        http://$DEPLOY_HOST"
    echo "  API Gateway:     http://$DEPLOY_HOST/docs"
    echo "  ML Engine:       http://$DEPLOY_HOST:8001/docs"
    echo "  Camera Service:  http://$DEPLOY_HOST:8002/docs"
    echo "  Validation:      http://$DEPLOY_HOST:8003/docs"
    echo "  Monitoring:      http://$DEPLOY_HOST:3001 (admin/admin)"
    echo ""
}

# Setup monitoring and logging
setup_monitoring() {
    echo "📊 Setting up monitoring..."
    
    ssh "$DEPLOY_USER@$DEPLOY_HOST" << 'EOF'
        cd /opt/vru-platform
        
        # Create log rotation configuration
        cat > /etc/logrotate.d/vru-platform << 'LOGROTATE_EOF'
/opt/vru-platform/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    notifempty
    create 644 root root
}
LOGROTATE_EOF
        
        # Setup system monitoring service
        cat > /etc/systemd/system/vru-platform.service << 'SERVICE_EOF'
[Unit]
Description=VRU Platform Docker Services
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/vru-platform
ExecStart=/usr/local/bin/docker-compose -f config/production/docker-compose.production.yml up -d
ExecStop=/usr/local/bin/docker-compose -f config/production/docker-compose.production.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
SERVICE_EOF
        
        systemctl daemon-reload
        systemctl enable vru-platform.service
        
        # Setup firewall rules
        if command -v ufw &> /dev/null; then
            ufw allow 80/tcp
            ufw allow 443/tcp
            ufw allow 3000/tcp
            ufw allow ssh
            ufw --force enable
        fi
EOF
    
    echo "✅ Monitoring setup complete"
}

# Main deployment flow
main() {
    case "${1:-deploy}" in
        "check")
            check_requirements
            ;;
        "setup")
            check_requirements
            setup_remote_environment
            ;;
        "deploy")
            check_requirements
            setup_remote_environment
            deploy_application_files
            deploy_services
            setup_monitoring
            verify_deployment
            echo ""
            echo "🎉 Deployment complete!"
            echo "VRU Platform is now running on $DEPLOY_HOST"
            ;;
        "verify")
            verify_deployment
            ;;
        "logs")
            ssh "$DEPLOY_USER@$DEPLOY_HOST" 'cd /opt/vru-platform && docker-compose -f config/production/docker-compose.production.yml logs -f'
            ;;
        "status")
            ssh "$DEPLOY_USER@$DEPLOY_HOST" 'cd /opt/vru-platform && docker-compose -f config/production/docker-compose.production.yml ps'
            ;;
        "stop")
            ssh "$DEPLOY_USER@$DEPLOY_HOST" 'cd /opt/vru-platform && docker-compose -f config/production/docker-compose.production.yml down'
            ;;
        "restart")
            ssh "$DEPLOY_USER@$DEPLOY_HOST" 'cd /opt/vru-platform && docker-compose -f config/production/docker-compose.production.yml restart'
            ;;
        *)
            echo "Usage: $0 {check|setup|deploy|verify|logs|status|stop|restart}"
            echo ""
            echo "Commands:"
            echo "  check   - Check deployment requirements"
            echo "  setup   - Setup remote environment only"
            echo "  deploy  - Full deployment (default)"
            echo "  verify  - Verify deployment health"
            echo "  logs    - View service logs"
            echo "  status  - Show service status"
            echo "  stop    - Stop all services"
            echo "  restart - Restart all services"
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"