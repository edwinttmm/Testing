#!/usr/bin/env python3
"""
Production Deployment Configuration for VRU ML Inference Engine
Ready for deployment on 155.138.239.131

SPARC Deployment Configuration:
- Specification: Production environment requirements
- Pseudocode: Docker and service configuration patterns
- Architecture: Scalable production deployment
- Refinement: Security and performance optimizations
- Completion: Ready for 155.138.239.131 deployment

Author: SPARC Deployment Team
Version: 2.0.0
Target: 155.138.239.131 Production Server
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List

# Production configuration for 155.138.239.131
PRODUCTION_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 8001,
        "workers": 4,
        "log_level": "info",
        "access_log": True,
        "ssl_enabled": False,  # Configure SSL for production
        "max_request_size": 100 * 1024 * 1024,  # 100MB for video uploads
    },
    
    "ml_engine": {
        "model_path": "/app/models/yolo11l.pt",  # Use YOLOv11 large for production
        "device": "auto",  # Will use GPU if available
        "batch_size": 8,
        "max_fps": None,  # No FPS limit for production
        "enable_tracking": True,
        "confidence_thresholds": {
            "pedestrian": 0.25,
            "cyclist": 0.30,
            "motorcyclist": 0.35,
            "vehicle": 0.40
        },
        "cache_results": True,
        "max_cache_size": 10000
    },
    
    "database": {
        "url": "postgresql://vru_user:secure_password@localhost:5432/vru_platform",
        "pool_size": 20,
        "max_overflow": 40,
        "pool_timeout": 30,
        "pool_recycle": 3600,
        "echo": False
    },
    
    "security": {
        "cors_origins": ["http://155.138.239.131", "http://localhost:3000"],
        "api_key_required": False,  # Set to True and configure API keys
        "rate_limiting": {
            "enabled": True,
            "requests_per_minute": 100,
            "burst_size": 20
        }
    },
    
    "monitoring": {
        "metrics_enabled": True,
        "health_check_interval": 30,
        "performance_logging": True,
        "log_file": "/app/logs/ml_inference.log",
        "log_rotation": "midnight",
        "log_retention_days": 30
    },
    
    "storage": {
        "video_upload_path": "/app/data/uploads",
        "model_cache_path": "/app/data/models",
        "temp_processing_path": "/app/data/temp",
        "max_video_size": 500 * 1024 * 1024,  # 500MB
        "allowed_video_formats": [".mp4", ".avi", ".mov", ".mkv"]
    }
}

def create_docker_compose():
    """Create Docker Compose configuration for production deployment"""
    docker_compose = {
        "version": "3.8",
        "services": {
            "ml-inference-api": {
                "build": {
                    "context": ".",
                    "dockerfile": "Dockerfile.ml-inference"
                },
                "ports": ["8001:8001"],
                "environment": [
                    "ENV=production",
                    "DATABASE_URL=postgresql://vru_user:secure_password@postgres:5432/vru_platform",
                    "REDIS_URL=redis://redis:6379/0",
                    "LOG_LEVEL=info"
                ],
                "volumes": [
                    "/opt/vru-platform/data:/app/data",
                    "/opt/vru-platform/logs:/app/logs",
                    "/opt/vru-platform/models:/app/models"
                ],
                "restart": "unless-stopped",
                "depends_on": ["postgres", "redis"],
                "deploy": {
                    "resources": {
                        "limits": {
                            "memory": "8G",
                            "cpus": "4.0"
                        },
                        "reservations": {
                            "memory": "4G",
                            "cpus": "2.0"
                        }
                    }
                },
                "healthcheck": {
                    "test": ["CMD", "curl", "-f", "http://localhost:8001/api/health"],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                    "start_period": "60s"
                }
            },
            
            "postgres": {
                "image": "postgres:15",
                "environment": [
                    "POSTGRES_DB=vru_platform",
                    "POSTGRES_USER=vru_user", 
                    "POSTGRES_PASSWORD=secure_password"
                ],
                "volumes": [
                    "/opt/vru-platform/postgres-data:/var/lib/postgresql/data",
                    "./sql/init.sql:/docker-entrypoint-initdb.d/init.sql"
                ],
                "ports": ["5432:5432"],
                "restart": "unless-stopped",
                "deploy": {
                    "resources": {
                        "limits": {
                            "memory": "2G",
                            "cpus": "1.0"
                        }
                    }
                }
            },
            
            "redis": {
                "image": "redis:7",
                "command": "redis-server --appendonly yes",
                "volumes": ["/opt/vru-platform/redis-data:/data"],
                "ports": ["6379:6379"],
                "restart": "unless-stopped",
                "deploy": {
                    "resources": {
                        "limits": {
                            "memory": "512M",
                            "cpus": "0.5"
                        }
                    }
                }
            },
            
            "nginx": {
                "image": "nginx:alpine",
                "ports": ["80:80", "443:443"],
                "volumes": [
                    "./nginx/nginx.conf:/etc/nginx/nginx.conf",
                    "./nginx/ssl:/etc/nginx/ssl",
                    "/opt/vru-platform/logs/nginx:/var/log/nginx"
                ],
                "depends_on": ["ml-inference-api"],
                "restart": "unless-stopped"
            }
        },
        
        "volumes": {
            "postgres_data": None,
            "redis_data": None,
            "app_data": None
        },
        
        "networks": {
            "vru_network": {
                "driver": "bridge"
            }
        }
    }
    
    return docker_compose

def create_dockerfile():
    """Create optimized Dockerfile for ML inference service"""
    dockerfile_content = '''# Multi-stage Dockerfile for VRU ML Inference Engine
FROM python:3.11-slim as base

# System dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    git \\
    libglib2.0-0 \\
    libsm6 \\
    libxext6 \\
    libxrender-dev \\
    libgomp1 \\
    libglu1-mesa \\
    libgl1-mesa-glx \\
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /app

# Python dependencies stage
FROM base as dependencies

# Copy requirements
COPY --chown=app:app requirements-ml.txt requirements.txt ./

# Install Python dependencies
RUN pip install --user --no-cache-dir -r requirements-ml.txt && \\
    pip install --user --no-cache-dir \\
        fastapi[all] \\
        uvicorn[standard] \\
        python-multipart \\
        psycopg2-binary \\
        redis

# Production stage
FROM base as production

# Copy Python packages from dependencies stage
COPY --from=dependencies /home/app/.local /home/app/.local

# Copy application code
COPY --chown=app:app src/ ./src/
COPY --chown=app:app *.py ./
COPY --chown=app:app models/ ./models/

# Create required directories
RUN mkdir -p data/uploads data/temp data/models logs

# Set environment variables
ENV PATH=/home/app/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \\
    CMD curl -f http://localhost:8001/api/health || exit 1

# Expose port
EXPOSE 8001

# Start command
CMD ["python", "-m", "uvicorn", "src.ml_api_endpoints:app", \\
     "--host", "0.0.0.0", \\
     "--port", "8001", \\
     "--workers", "4", \\
     "--access-log", \\
     "--log-level", "info"]
'''
    return dockerfile_content

def create_nginx_config():
    """Create Nginx configuration for production"""
    nginx_config = '''events {
    worker_connections 1024;
}

http {
    upstream ml_inference {
        server ml-inference-api:8001;
    }
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    # File upload limits
    client_max_body_size 500M;
    
    server {
        listen 80;
        server_name 155.138.239.131;
        
        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        
        # API proxy
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            
            proxy_pass http://ml_inference;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts for long-running inference
            proxy_connect_timeout 60s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }
        
        # Health check
        location /health {
            proxy_pass http://ml_inference/api/health;
        }
        
        # Static files (if needed)
        location /static/ {
            alias /app/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
        
        # Logs
        access_log /var/log/nginx/vru_access.log;
        error_log /var/log/nginx/vru_error.log;
    }
}
'''
    return nginx_config

def create_systemd_service():
    """Create systemd service configuration"""
    systemd_config = '''[Unit]
Description=VRU ML Inference Engine
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/vru-platform
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
ExecReload=/usr/local/bin/docker-compose restart
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
'''
    return systemd_config

def create_deployment_script():
    """Create deployment script for 155.138.239.131"""
    deployment_script = '''#!/bin/bash
# VRU ML Inference Engine Deployment Script
# Target: 155.138.239.131

set -e

echo "🚀 Starting VRU ML Inference Engine deployment..."

# Configuration
DEPLOY_DIR="/opt/vru-platform"
BACKUP_DIR="/opt/vru-platform-backup-$(date +%Y%m%d-%H%M%S)"
SERVICE_NAME="vru-ml-inference"

# Create backup if exists
if [ -d "$DEPLOY_DIR" ]; then
    echo "📦 Creating backup..."
    sudo cp -r "$DEPLOY_DIR" "$BACKUP_DIR"
fi

# Create deployment directory
echo "📁 Setting up deployment directory..."
sudo mkdir -p "$DEPLOY_DIR"
sudo mkdir -p "$DEPLOY_DIR/data/uploads"
sudo mkdir -p "$DEPLOY_DIR/data/models"
sudo mkdir -p "$DEPLOY_DIR/data/temp"
sudo mkdir -p "$DEPLOY_DIR/logs"
sudo mkdir -p "$DEPLOY_DIR/postgres-data"
sudo mkdir -p "$DEPLOY_DIR/redis-data"

# Copy application files
echo "📋 Copying application files..."
sudo cp -r src/ "$DEPLOY_DIR/"
sudo cp docker-compose.yml "$DEPLOY_DIR/"
sudo cp Dockerfile.ml-inference "$DEPLOY_DIR/"
sudo cp requirements-ml.txt "$DEPLOY_DIR/"
sudo cp -r nginx/ "$DEPLOY_DIR/" 2>/dev/null || true

# Download YOLO models
echo "🧠 Downloading YOLO models..."
cd "$DEPLOY_DIR"
if [ ! -f "data/models/yolo11l.pt" ]; then
    sudo wget -O "data/models/yolo11l.pt" "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolo11l.pt" || true
fi
if [ ! -f "data/models/yolov8n.pt" ]; then
    sudo wget -O "data/models/yolov8n.pt" "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt" || true
fi

# Set permissions
echo "🔐 Setting permissions..."
sudo chown -R 1000:1000 "$DEPLOY_DIR/data"
sudo chown -R 1000:1000 "$DEPLOY_DIR/logs"
sudo chmod -R 755 "$DEPLOY_DIR"

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "🏗️ Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Build and start services
echo "🏗️ Building and starting services..."
cd "$DEPLOY_DIR"
sudo docker-compose down || true
sudo docker-compose build --no-cache
sudo docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Health check
echo "🩺 Running health check..."
for i in {1..30}; do
    if curl -f http://localhost:8001/api/health > /dev/null 2>&1; then
        echo "✅ Service is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Health check failed after 30 attempts"
        sudo docker-compose logs ml-inference-api
        exit 1
    fi
    echo "Attempt $i/30 - waiting..."
    sleep 10
done

# Create systemd service
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/vru-ml-inference.service > /dev/null << EOF
[Unit]
Description=VRU ML Inference Engine
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$DEPLOY_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
ExecReload=/usr/local/bin/docker-compose restart
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vru-ml-inference
sudo systemctl start vru-ml-inference

# Final status check
echo "📊 Final status check..."
sudo docker-compose ps
curl -s http://localhost:8001/api/health | jq '.' || echo "Service status check completed"

echo ""
echo "🎉 Deployment completed successfully!"
echo "📍 Service URL: http://155.138.239.131:8001"
echo "📖 API Docs: http://155.138.239.131:8001/api/docs"
echo "🩺 Health Check: http://155.138.239.131:8001/api/health"
echo ""
echo "🔧 Management commands:"
echo "  Start:   sudo systemctl start vru-ml-inference"
echo "  Stop:    sudo systemctl stop vru-ml-inference"
echo "  Restart: sudo systemctl restart vru-ml-inference"
echo "  Status:  sudo systemctl status vru-ml-inference"
echo "  Logs:    sudo docker-compose -f $DEPLOY_DIR/docker-compose.yml logs -f"
echo ""
'''
    return deployment_script

def generate_production_files():
    """Generate all production deployment files"""
    print("🚀 Generating production deployment files...")
    
    # Create docker-compose.yml
    docker_compose = create_docker_compose()
    with open("docker-compose.yml", "w") as f:
        import yaml
        yaml.dump(docker_compose, f, default_flow_style=False, sort_keys=False)
    print("✅ Generated docker-compose.yml")
    
    # Create Dockerfile
    dockerfile_content = create_dockerfile()
    with open("Dockerfile.ml-inference", "w") as f:
        f.write(dockerfile_content)
    print("✅ Generated Dockerfile.ml-inference")
    
    # Create Nginx config directory and file
    os.makedirs("nginx", exist_ok=True)
    nginx_config = create_nginx_config()
    with open("nginx/nginx.conf", "w") as f:
        f.write(nginx_config)
    print("✅ Generated nginx/nginx.conf")
    
    # Create deployment script
    deployment_script = create_deployment_script()
    with open("deploy.sh", "w") as f:
        f.write(deployment_script)
    os.chmod("deploy.sh", 0o755)
    print("✅ Generated deploy.sh")
    
    # Create production config file
    with open("production_config.json", "w") as f:
        json.dump(PRODUCTION_CONFIG, f, indent=2)
    print("✅ Generated production_config.json")
    
    print("\n🎉 All production deployment files generated!")
    print(f"📍 Ready for deployment on 155.138.239.131")
    print(f"🚀 Run: chmod +x deploy.sh && ./deploy.sh")

if __name__ == "__main__":
    generate_production_files()