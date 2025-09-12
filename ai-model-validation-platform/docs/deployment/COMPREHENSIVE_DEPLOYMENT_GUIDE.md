# AI Model Validation Platform - Comprehensive Deployment Guide

## Table of Contents
1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Pre-deployment Checklist](#pre-deployment-checklist)
4. [Development Environment Setup](#development-environment-setup)
5. [Production Deployment](#production-deployment)
6. [Docker Deployment](#docker-deployment)
7. [Environment Configuration](#environment-configuration)
8. [Database Setup](#database-setup)
9. [Security Configuration](#security-configuration)
10. [Performance Optimization](#performance-optimization)
11. [Monitoring and Logging](#monitoring-and-logging)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The AI Model Validation Platform is a comprehensive system for validating AI models with video annotation capabilities, ground truth generation, and statistical analysis. This guide provides complete instructions for deploying the platform in both development and production environments.

### Key Features
- FastAPI-based REST API backend
- SQLite/PostgreSQL database support
- Real-time WebSocket communication
- YOLOv8 integration for AI model validation
- Video annotation and ground truth generation
- Statistical validation and performance metrics
- Docker containerization support

---

## System Requirements

### Minimum Requirements
- **OS**: Linux (Ubuntu 20.04+), macOS 10.15+, Windows 10+
- **Python**: 3.9+ (3.12+ recommended)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB free space minimum
- **Network**: Internet connection for dependencies

### Recommended Production Requirements
- **OS**: Ubuntu 22.04 LTS or CentOS 8+
- **CPU**: 4+ cores
- **RAM**: 16GB+
- **Storage**: 100GB+ SSD
- **GPU**: NVIDIA GPU with CUDA support (optional, for enhanced performance)

### Required Software
```bash
# Core requirements
python3.12
pip
git
curl
docker (optional)
docker-compose (optional)

# Database (production)
postgresql-15 (recommended for production)
redis-7 (for caching and sessions)
```

---

## Pre-deployment Checklist

### ✅ System Preparation
- [ ] Operating system updated and patched
- [ ] Python 3.12+ installed and configured
- [ ] Git installed and configured
- [ ] Docker installed (if using containerized deployment)
- [ ] Firewall configured (ports 8000, 8001, 5432, 6379)
- [ ] SSL certificates prepared (production only)

### ✅ Security Preparation
- [ ] Generated secure secret keys
- [ ] Database credentials configured
- [ ] SSL/TLS certificates ready
- [ ] Backup strategy planned
- [ ] Monitoring system prepared

### ✅ Resource Preparation
- [ ] Domain name configured (production)
- [ ] DNS records set up
- [ ] Load balancer configured (if needed)
- [ ] Storage volumes prepared
- [ ] Network security groups configured

---

## Development Environment Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd ai-model-validation-platform
```

### 2. Backend Setup
```bash
cd backend

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Required environment variables for development:**
```env
# Application
ENV=development
SECRET_KEY=your-development-secret-key-min-32-chars
DEBUG=true

# Database
DATABASE_URL=sqlite:///./dev_database.db

# API Configuration
API_HOST=localhost
API_PORT=8000
FRONTEND_URL=http://localhost:3000

# Logging
LOG_LEVEL=DEBUG
LOG_FILE=backend.log

# Security (development - use secure values in production)
CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000"]
ALLOWED_HOSTS=["localhost", "127.0.0.1"]

# AI/ML Configuration
YOLO_MODEL_PATH=yolov8n.pt
INFERENCE_DEVICE=cpu
```

### 4. Database Initialization
```bash
# Initialize database
python -c "from database import engine, Base; Base.metadata.create_all(bind=engine)"

# Or use the initialization script
python database_initialization.py
```

### 5. Start Development Server
```bash
# Start backend server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Alternative startup methods
python main.py
# or
python -m uvicorn main:app --reload
```

### 6. Verify Installation
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test API documentation
open http://localhost:8000/docs
```

---

## Production Deployment

### 1. Server Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3.12 python3.12-venv python3.12-dev
sudo apt install -y postgresql postgresql-contrib redis-server
sudo apt install -y nginx certbot python3-certbot-nginx
sudo apt install -y git curl wget htop
```

### 2. User and Directory Setup
```bash
# Create application user
sudo useradd -m -s /bin/bash aivalidation
sudo usermod -aG sudo aivalidation

# Create application directories
sudo mkdir -p /opt/ai-validation-platform
sudo chown aivalidation:aivalidation /opt/ai-validation-platform
sudo -u aivalidation mkdir -p /opt/ai-validation-platform/{logs,data,backups,uploads}
```

### 3. Application Deployment
```bash
# Switch to application user
sudo -u aivalidation -i

# Clone repository
cd /opt/ai-validation-platform
git clone <repository-url> app
cd app/backend

# Create production virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install production dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn[gevent]  # Production WSGI server
```

### 4. Production Environment Configuration
```bash
# Copy production environment template
cp .env.example .env.production

# Configure production environment
nano .env.production
```

**Production environment variables:**
```env
# Application
ENV=production
SECRET_KEY=your-super-secure-production-secret-key-64-chars-minimum
DEBUG=false

# Database (PostgreSQL recommended for production)
DATABASE_URL=postgresql://ai_validation:secure_password@localhost:5432/ai_validation_db

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# API Configuration
API_HOST=0.0.0.0
API_PORT=8001
FRONTEND_URL=https://yourdomain.com

# Security
CORS_ORIGINS=["https://yourdomain.com", "https://www.yourdomain.com"]
ALLOWED_HOSTS=["yourdomain.com", "www.yourdomain.com", "your-server-ip"]
SECURITY_HEADERS_ENABLED=true
RATE_LIMITING_ENABLED=true

# SSL/TLS
SSL_CERT_PATH=/etc/letsencrypt/live/yourdomain.com/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/yourdomain.com/privkey.pem

# Logging
LOG_LEVEL=INFO
LOG_FILE=/opt/ai-validation-platform/logs/app.log
ACCESS_LOG=/opt/ai-validation-platform/logs/access.log
ERROR_LOG=/opt/ai-validation-platform/logs/error.log

# Performance
WORKER_PROCESSES=4
MAX_CONNECTIONS=1000
KEEPALIVE_TIMEOUT=65

# AI/ML Configuration
YOLO_MODEL_PATH=/opt/ai-validation-platform/models/yolov8n.pt
INFERENCE_DEVICE=cuda  # or 'cpu' if no GPU
MODEL_CACHE_SIZE=100MB

# File Upload
MAX_FILE_SIZE=100MB
UPLOAD_PATH=/opt/ai-validation-platform/uploads
TEMP_PATH=/opt/ai-validation-platform/temp

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_SCHEDULE=0 2 * * *  # Daily at 2 AM
BACKUP_RETENTION_DAYS=30
BACKUP_PATH=/opt/ai-validation-platform/backups
```

### 5. Database Setup (PostgreSQL)
```bash
# Create database and user
sudo -u postgres createuser ai_validation
sudo -u postgres createdb ai_validation_db -O ai_validation
sudo -u postgres psql -c "ALTER USER ai_validation PASSWORD 'secure_password';"

# Initialize database schema
cd /opt/ai-validation-platform/app/backend
source .venv/bin/activate
python -c "from database import engine, Base; Base.metadata.create_all(bind=engine)"
```

### 6. Systemd Service Configuration
```bash
# Create systemd service file
sudo nano /etc/systemd/system/ai-validation-api.service
```

```ini
[Unit]
Description=AI Model Validation Platform API
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=exec
User=aivalidation
Group=aivalidation
WorkingDirectory=/opt/ai-validation-platform/app/backend
Environment=PATH=/opt/ai-validation-platform/app/backend/.venv/bin
ExecStart=/opt/ai-validation-platform/app/backend/.venv/bin/gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8001 --access-logfile /opt/ai-validation-platform/logs/access.log --error-logfile /opt/ai-validation-platform/logs/error.log --log-level info
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5
KillMode=mixed
TimeoutStopSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable ai-validation-api
sudo systemctl start ai-validation-api
sudo systemctl status ai-validation-api
```

### 7. Nginx Configuration
```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/ai-validation-platform
```

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # File Upload Size
    client_max_body_size 100M;

    # API Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health Check
    location /health {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Support
    location /socket.io/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static Files (if needed)
    location /static/ {
        alias /opt/ai-validation-platform/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Upload Directory
    location /uploads/ {
        alias /opt/ai-validation-platform/uploads/;
        expires 1d;
        add_header Cache-Control "private, no-cache";
    }

    # Logging
    access_log /var/log/nginx/ai-validation-access.log;
    error_log /var/log/nginx/ai-validation-error.log;
}
```

```bash
# Enable site and restart Nginx
sudo ln -s /etc/nginx/sites-available/ai-validation-platform /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 8. SSL Certificate Setup
```bash
# Install SSL certificate using Certbot
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Set up automatic renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### 9. Firewall Configuration
```bash
# Configure UFW firewall
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 80/tcp     # HTTP
sudo ufw allow 443/tcp    # HTTPS
sudo ufw allow 8001/tcp   # API (if needed for direct access)
sudo ufw --force enable
```

### 10. Production Verification
```bash
# Test API health
curl https://yourdomain.com/health

# Test API documentation
curl https://yourdomain.com/api/docs

# Check service status
sudo systemctl status ai-validation-api
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status redis

# Check logs
sudo journalctl -u ai-validation-api -f
tail -f /opt/ai-validation-platform/logs/app.log
```

---

## Docker Deployment

### 1. Docker Configuration Files

**Dockerfile:**
```dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /app/.venv

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN /app/.venv/bin/pip install --upgrade pip
RUN /app/.venv/bin/pip install -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data uploads temp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose port
EXPOSE 8001

# Run application
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      - ENV=production
      - DATABASE_URL=postgresql://ai_validation:secure_password@postgres:5432/ai_validation_db
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-super-secure-docker-secret-key-64-chars
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./uploads:/app/uploads
      - ./models:/app/models
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=ai_validation_db
      - POSTGRES_USER=ai_validation
      - POSTGRES_PASSWORD=secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ai_validation -d ai_validation_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:

networks:
  default:
    driver: bridge
```

### 2. Docker Deployment Commands
```bash
# Build and start services
docker-compose up --build -d

# View logs
docker-compose logs -f api

# Scale API service
docker-compose up --scale api=3 -d

# Update deployment
docker-compose pull
docker-compose up -d

# Backup database
docker-compose exec postgres pg_dump -U ai_validation ai_validation_db > backup.sql

# Restore database
docker-compose exec -T postgres psql -U ai_validation ai_validation_db < backup.sql
```

---

## Environment Configuration Reference

### Complete Environment Variables

| Variable | Development | Production | Description |
|----------|-------------|------------|-------------|
| `ENV` | `development` | `production` | Application environment |
| `SECRET_KEY` | 32+ chars | 64+ chars | JWT signing key |
| `DEBUG` | `true` | `false` | Debug mode |
| `DATABASE_URL` | SQLite path | PostgreSQL URL | Database connection |
| `REDIS_URL` | Optional | Required | Cache server |
| `API_HOST` | `localhost` | `0.0.0.0` | API bind host |
| `API_PORT` | `8000` | `8001` | API port |
| `FRONTEND_URL` | Local URL | Production URL | CORS origin |
| `LOG_LEVEL` | `DEBUG` | `INFO` | Logging level |
| `MAX_FILE_SIZE` | `10MB` | `100MB` | Upload limit |
| `WORKER_PROCESSES` | `1` | `4+` | Gunicorn workers |

### Security Configuration
```env
# Rate limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_BURST=20

# Security headers
HSTS_MAX_AGE=31536000
CSP_POLICY="default-src 'self'"
X_FRAME_OPTIONS=DENY

# Session security
SESSION_TIMEOUT=3600
CSRF_PROTECTION=true
XSS_PROTECTION=true

# File upload security
ALLOWED_EXTENSIONS=["mp4", "avi", "mov", "jpg", "png"]
SCAN_UPLOADS=true
QUARANTINE_PATH=/opt/quarantine
```

---

## Database Setup and Migration

### SQLite (Development)
```bash
# Initialize SQLite database
python -c "
from database import engine, Base
from models import *
Base.metadata.create_all(bind=engine)
print('✅ SQLite database initialized')
"
```

### PostgreSQL (Production)
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres createuser ai_validation
sudo -u postgres createdb ai_validation_db -O ai_validation
sudo -u postgres psql -c "ALTER USER ai_validation PASSWORD 'secure_password';"

# Initialize schema
python -c "
from database import engine, Base
from models import *
Base.metadata.create_all(bind=engine)
print('✅ PostgreSQL database initialized')
"
```

### Database Migration Script
```python
#!/usr/bin/env python3
"""
Database migration and initialization script
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent))

from database import engine, Base, SessionLocal
from models import *
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Initialize or migrate database"""
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
        
        # Verify connection
        with SessionLocal() as session:
            session.execute("SELECT 1")
            logger.info("✅ Database connection verified")
            
        return True
    except Exception as e:
        logger.error(f"❌ Database migration failed: {e}")
        return False

if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)
```

---

## Performance Optimization

### Application Optimization
```python
# config/performance.py
PERFORMANCE_CONFIG = {
    # Database connection pooling
    'DATABASE_POOL_SIZE': 10,
    'DATABASE_MAX_OVERFLOW': 20,
    'DATABASE_POOL_TIMEOUT': 30,
    
    # Redis caching
    'CACHE_TTL': 3600,
    'CACHE_MAX_SIZE': '100MB',
    
    # File handling
    'UPLOAD_CHUNK_SIZE': 8192,
    'TEMP_FILE_CLEANUP': True,
    
    # API optimization
    'API_RESPONSE_COMPRESSION': True,
    'API_REQUEST_TIMEOUT': 30,
    
    # AI/ML optimization
    'MODEL_BATCH_SIZE': 32,
    'MODEL_CACHE_ENABLED': True,
    'INFERENCE_TIMEOUT': 60,
}
```

### Gunicorn Production Configuration
```python
# gunicorn.conf.py
import multiprocessing

# Server socket
bind = "127.0.0.1:8001"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# Timeouts
timeout = 30
keepalive = 5
graceful_timeout = 30

# Logging
accesslog = "/opt/ai-validation-platform/logs/access.log"
errorlog = "/opt/ai-validation-platform/logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "ai-validation-api"

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
```

### Database Optimization
```sql
-- PostgreSQL optimization queries
-- Create indexes for common queries
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_videos_project_id ON videos(project_id);
CREATE INDEX idx_detection_events_video_id ON detection_events(video_id);
CREATE INDEX idx_annotations_video_id ON annotations(video_id);
CREATE INDEX idx_test_sessions_created_at ON test_sessions(created_at);

-- Analyze tables for query optimization
ANALYZE projects;
ANALYZE videos;
ANALYZE detection_events;
ANALYZE annotations;
ANALYZE test_sessions;
```

---

## Monitoring and Logging

### Logging Configuration
```python
# logging_config.py
import logging
import logging.handlers
from pathlib import Path

def setup_production_logging():
    """Configure production logging"""
    
    # Create logs directory
    log_dir = Path("/opt/ai-validation-platform/logs")
    log_dir.mkdir(exist_ok=True)
    
    # Main application logger
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    
    # Rotating file handler
    app_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    
    # Error logger
    error_logger = logging.getLogger("error")
    error_logger.setLevel(logging.ERROR)
    
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10*1024*1024,
        backupCount=10
    )
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    app_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)
    
    app_logger.addHandler(app_handler)
    error_logger.addHandler(error_handler)
    
    return app_logger, error_logger
```

### System Monitoring Scripts
```bash
#!/bin/bash
# monitor.sh - System monitoring script

LOG_DIR="/opt/ai-validation-platform/logs"
ALERT_EMAIL="admin@yourdomain.com"

# Check API health
check_api_health() {
    if ! curl -f http://localhost:8001/health >/dev/null 2>&1; then
        echo "$(date): API health check failed" >> $LOG_DIR/monitor.log
        # Send alert or restart service
        sudo systemctl restart ai-validation-api
    fi
}

# Check disk space
check_disk_space() {
    USAGE=$(df /opt/ai-validation-platform | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ $USAGE -gt 80 ]; then
        echo "$(date): Disk usage high: ${USAGE}%" >> $LOG_DIR/monitor.log
    fi
}

# Check service status
check_services() {
    services=("ai-validation-api" "postgresql" "redis" "nginx")
    for service in "${services[@]}"; do
        if ! systemctl is-active --quiet $service; then
            echo "$(date): Service $service is not running" >> $LOG_DIR/monitor.log
            sudo systemctl restart $service
        fi
    done
}

# Run checks
check_api_health
check_disk_space
check_services
```

### Performance Monitoring
```python
# monitoring/metrics.py
import time
import psutil
from typing import Dict, Any

class SystemMetrics:
    """System performance metrics collector"""
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Collect system performance metrics"""
        return {
            'timestamp': time.time(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'load_average': psutil.getloadavg(),
            'network_io': psutil.net_io_counters()._asdict(),
            'disk_io': psutil.disk_io_counters()._asdict(),
        }
    
    @staticmethod
    def get_application_metrics() -> Dict[str, Any]:
        """Collect application-specific metrics"""
        # Implement application-specific metrics
        return {
            'active_connections': 0,  # From your connection pool
            'requests_per_minute': 0,  # From your request counter
            'cache_hit_rate': 0,      # From Redis metrics
            'average_response_time': 0, # From request timing
        }
```

---

## Backup and Recovery

### Automated Backup Script
```bash
#!/bin/bash
# backup.sh - Automated backup script

BACKUP_DIR="/opt/ai-validation-platform/backups"
APP_DIR="/opt/ai-validation-platform/app"
DB_NAME="ai_validation_db"
DB_USER="ai_validation"
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Generate timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Database backup
echo "Creating database backup..."
pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > $BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz

# Application files backup
echo "Creating application backup..."
tar -czf $BACKUP_DIR/app_backup_$TIMESTAMP.tar.gz -C $APP_DIR .

# Uploads backup
echo "Creating uploads backup..."
tar -czf $BACKUP_DIR/uploads_backup_$TIMESTAMP.tar.gz /opt/ai-validation-platform/uploads/

# Clean old backups
echo "Cleaning old backups..."
find $BACKUP_DIR -name "*.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $TIMESTAMP"
```

### Recovery Procedures
```bash
#!/bin/bash
# restore.sh - Database and application restore

BACKUP_DIR="/opt/ai-validation-platform/backups"
DB_NAME="ai_validation_db"
DB_USER="ai_validation"

# Function to restore database
restore_database() {
    local backup_file=$1
    echo "Restoring database from $backup_file..."
    
    # Stop API service
    sudo systemctl stop ai-validation-api
    
    # Drop and recreate database
    sudo -u postgres dropdb $DB_NAME
    sudo -u postgres createdb $DB_NAME -O $DB_USER
    
    # Restore from backup
    gunzip -c $backup_file | psql -U $DB_USER -h localhost $DB_NAME
    
    # Start API service
    sudo systemctl start ai-validation-api
    
    echo "Database restore completed"
}

# Function to restore application files
restore_application() {
    local backup_file=$1
    echo "Restoring application from $backup_file..."
    
    # Stop service
    sudo systemctl stop ai-validation-api
    
    # Backup current state
    mv /opt/ai-validation-platform/app /opt/ai-validation-platform/app.old
    
    # Restore from backup
    mkdir -p /opt/ai-validation-platform/app
    tar -xzf $backup_file -C /opt/ai-validation-platform/app
    
    # Set permissions
    chown -R aivalidation:aivalidation /opt/ai-validation-platform/app
    
    # Start service
    sudo systemctl start ai-validation-api
    
    echo "Application restore completed"
}

# Usage examples:
# ./restore.sh database db_backup_20250831_120000.sql.gz
# ./restore.sh application app_backup_20250831_120000.tar.gz
```

---

## Health Checks and Validation

### Production Health Check Script
```python
#!/usr/bin/env python3
"""
Comprehensive production health check
"""
import requests
import psycopg2
import redis
import json
import sys
from datetime import datetime

def check_api_health():
    """Check API server health"""
    try:
        response = requests.get('http://localhost:8001/health', timeout=5)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, str(e)

def check_database_health():
    """Check database connectivity"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="ai_validation_db",
            user="ai_validation",
            password="secure_password"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return True, "Database connected"
    except Exception as e:
        return False, str(e)

def check_redis_health():
    """Check Redis connectivity"""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        return True, "Redis connected"
    except Exception as e:
        return False, str(e)

def run_health_check():
    """Run comprehensive health check"""
    results = {
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {}
    }
    
    # API health check
    api_healthy, api_result = check_api_health()
    results['checks']['api'] = {
        'healthy': api_healthy,
        'result': api_result
    }
    
    # Database health check
    db_healthy, db_result = check_database_health()
    results['checks']['database'] = {
        'healthy': db_healthy,
        'result': db_result
    }
    
    # Redis health check
    redis_healthy, redis_result = check_redis_health()
    results['checks']['redis'] = {
        'healthy': redis_healthy,
        'result': redis_result
    }
    
    # Overall health
    overall_healthy = all([
        api_healthy,
        db_healthy,
        redis_healthy
    ])
    
    results['overall_healthy'] = overall_healthy
    
    return results

if __name__ == "__main__":
    results = run_health_check()
    print(json.dumps(results, indent=2))
    
    # Exit with error code if unhealthy
    sys.exit(0 if results['overall_healthy'] else 1)
```

---

This comprehensive deployment guide provides everything needed to successfully deploy the AI Model Validation Platform in both development and production environments. The next sections will cover specific fixes implemented, troubleshooting guides, and architectural documentation.