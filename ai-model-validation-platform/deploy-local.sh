#!/bin/bash

# =====================================================
# VRU AI Model Validation Platform - Local Deployment Script
# For execution directly on target server (155.138.239.131)
# =====================================================

set -euo pipefail

# =====================================================
# CONFIGURATION
# =====================================================
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
Local Production Deployment
===============================================
EOF
echo -e "${NC}"

log "INFO" "Project: $PROJECT_NAME"
log "INFO" "Server: $(hostname -I | awk '{print $1}')"
log "INFO" "User: $(whoami)"
log "INFO" "Project Root: $PROJECT_ROOT"

# =====================================================
# VALIDATION FUNCTIONS
# =====================================================
validate_requirements() {
    log "INFO" "🔍 Validating local deployment requirements..."
    
    # Check for required files
    local required_files=(
        ".env.production"
        "docker-compose.production.yml"
        "backend/Dockerfile.unified"
        "frontend/Dockerfile.unified"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$PROJECT_ROOT/$file" ]]; then
            log "ERROR" "❌ Required file missing: $file"
            return 1
        fi
    done
    
    # Check Docker installation
    if ! command -v docker &> /dev/null; then
        log "ERROR" "❌ Docker is not installed"
        return 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log "ERROR" "❌ Docker Compose is not installed"
        return 1
    fi
    
    # Check if Docker service is running
    if ! docker info &> /dev/null; then
        log "ERROR" "❌ Docker service is not running"
        return 1
    fi
    
    log "INFO" "✅ All requirements validated"
}

# =====================================================
# ENVIRONMENT SETUP
# =====================================================
setup_environment() {
    log "INFO" "🔧 Setting up production environment..."
    
    # Create necessary directories
    mkdir -p logs backups data/{postgres,redis,uploads,models,cache}
    
    # Set proper permissions
    chown -R $(whoami):$(whoami) data logs backups || true
    chmod -R 755 data logs backups
    
    # Create models directory and download script if missing
    if [[ ! -d "models" ]]; then
        mkdir -p models
        cat > models/download_models.sh << 'MODEL_SCRIPT'
#!/bin/bash
echo "Downloading YOLO models..."
wget -q -O models/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt || echo "Model download failed - using existing"
MODEL_SCRIPT
        chmod +x models/download_models.sh
    fi
    
    log "INFO" "✅ Environment setup complete"
}

# =====================================================
# CONFIGURATION GENERATION
# =====================================================
generate_configs() {
    log "INFO" "⚙️ Generating production configurations..."
    
    # Generate Nginx configuration
    mkdir -p config/nginx
    cat > config/nginx/nginx.conf << 'NGINX_EOF'
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    upstream frontend {
        server frontend:3000;
    }
    
    upstream api {
        server api_gateway:8000;
    }
    
    server {
        listen 80;
        server_name _;
        
        # Frontend
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        # API
        location /api/ {
            proxy_pass http://api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        # Health check
        location /health {
            proxy_pass http://api/health;
        }
    }
}
NGINX_EOF
    
    log "INFO" "✅ Configuration generation complete"
}

# =====================================================
# SERVICE DEPLOYMENT
# =====================================================
deploy_services() {
    log "INFO" "🐳 Deploying services locally..."
    
    cd "$PROJECT_ROOT"
    
    # Load environment variables
    if [[ -f ".env.production" ]]; then
        set -a
        source .env.production
        set +a
        log "INFO" "✅ Environment variables loaded"
    fi
    
    # Stop existing services
    log "INFO" "Stopping existing services..."
    docker-compose -f docker-compose.production.yml down --remove-orphans || true
    
    # Clean up unused images and volumes
    docker system prune -f || true
    
    # Build and start services
    log "INFO" "Building and starting services..."
    docker-compose -f docker-compose.production.yml up --build -d
    
    log "INFO" "⏳ Waiting for services to become healthy..."
    sleep 30
    
    log "INFO" "✅ Services deployed"
}

# =====================================================
# HEALTH VERIFICATION
# =====================================================
verify_deployment() {
    log "INFO" "🔍 Verifying deployment health..."
    
    # Check container status
    log "INFO" "Container Status:"
    docker-compose -f docker-compose.production.yml ps
    
    # Test service endpoints
    local services=(
        "http://localhost/health"
        "http://localhost:3000"
        "http://localhost:8000/health"
    )
    
    for service in "${services[@]}"; do
        log "INFO" "Testing $service..."
        if curl -f -s --max-time 10 "$service" > /dev/null 2>&1; then
            log "INFO" "✅ $service - OK"
        else
            log "WARN" "⚠️ $service - Not responding"
        fi
    done
    
    log "INFO" ""
    log "INFO" "🌐 Service URLs:"
    log "INFO" "  Frontend:     http://$(hostname -I | awk '{print $1}'):3000"
    log "INFO" "  API Gateway:  http://$(hostname -I | awk '{print $1}'):8000/docs"
    log "INFO" "  Health Check: http://$(hostname -I | awk '{print $1}')/health"
    log "INFO" ""
}

# =====================================================
# LOG MONITORING
# =====================================================
show_logs() {
    log "INFO" "📊 Service logs:"
    docker-compose -f docker-compose.production.yml logs --tail=50
}

# =====================================================
# SERVICE MANAGEMENT
# =====================================================
stop_services() {
    log "INFO" "🛑 Stopping all services..."
    docker-compose -f docker-compose.production.yml down
    log "INFO" "✅ All services stopped"
}

restart_services() {
    log "INFO" "🔄 Restarting services..."
    docker-compose -f docker-compose.production.yml restart
    log "INFO" "✅ Services restarted"
}

show_status() {
    log "INFO" "📊 Service status:"
    docker-compose -f docker-compose.production.yml ps
}

# =====================================================
# MAIN EXECUTION
# =====================================================
main() {
    case "${1:-deploy}" in
        "validate")
            validate_requirements
            ;;
        "setup")
            validate_requirements
            setup_environment
            generate_configs
            ;;
        "deploy")
            validate_requirements
            setup_environment
            generate_configs
            deploy_services
            verify_deployment
            log "INFO" ""
            log "INFO" "🎉 Local deployment complete!"
            log "INFO" "VRU Platform is now running locally"
            ;;
        "verify")
            verify_deployment
            ;;
        "logs")
            show_logs
            ;;
        "status")
            show_status
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            restart_services
            ;;
        *)
            log "INFO" "Usage: $0 {validate|setup|deploy|verify|logs|status|stop|restart}"
            log "INFO" ""
            log "INFO" "Commands:"
            log "INFO" "  validate - Check deployment requirements"
            log "INFO" "  setup    - Setup environment only"
            log "INFO" "  deploy   - Full local deployment (default)"
            log "INFO" "  verify   - Verify deployment health"
            log "INFO" "  logs     - View service logs"
            log "INFO" "  status   - Show service status"
            log "INFO" "  stop     - Stop all services"
            log "INFO" "  restart  - Restart all services"
            exit 1
            ;;
    esac
}

# Execute main function
main "$@"