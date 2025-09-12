# Deployment Configuration Analysis

## Executive Summary

The AI Model Validation Platform implements a comprehensive deployment architecture with production-grade monitoring, log aggregation, container orchestration, and infrastructure management optimized for cloud deployment on Vultr with advanced security and performance features.

## Production Deployment Architecture

### Infrastructure Overview

**Deployment Target**: Vultr Cloud Infrastructure
- **Primary Server**: 155.138.239.131
- **Environment**: Production Vultr deployment
- **Architecture**: Multi-container Docker deployment
- **Orchestration**: Docker Compose with health checks
- **Monitoring**: Prometheus + Grafana + Loki stack
- **Load Balancing**: Nginx reverse proxy
- **SSL/TLS**: Full encryption with certificate management

### Service Architecture

```yaml
# Production service stack
services:
  - nginx (Load Balancer/SSL Termination)
  - frontend (React Application)
  - backend (FastAPI Server)
  - postgres (Database)
  - redis (Cache/Sessions)
  - prometheus (Metrics Collection)
  - grafana (Monitoring Dashboard)
  - loki (Log Aggregation)
  - node-exporter (System Metrics)
  - blackbox-exporter (External Monitoring)
```

## Monitoring Configuration

### Prometheus Configuration

```yaml
# /scripts/monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    environment: 'vultr-production'
    cluster: 'ai-validation'

# Storage configuration
storage:
  tsdb:
    retention.time: 15d
    retention.size: 10GB
    path: /prometheus
    wal-compression: true

# Performance tuning
query:
  max_concurrency: 20
  timeout: 2m
  max_samples: 50000000

# Web configuration
web:
  max_connections: 512
  read_timeout: 30s
  enable_lifecycle: true
  enable_admin_api: true
  page_title: "AI Validation Platform - Prometheus"
  external_url: "https://155.138.239.131/prometheus/"
```

**Monitoring Targets:**
- **Prometheus Self-Monitoring**: localhost:9090 (30s interval)
- **Node Exporter**: node-exporter:9100 (15s interval) - System metrics
- **Docker Engine**: host.docker.internal:9323 (30s interval)
- **PostgreSQL**: postgres-exporter:9187 (30s interval)
- **Redis**: redis-exporter:9121 (30s interval)
- **Backend API**: backend:8000 (15s interval)
- **Nginx**: nginx:9113 (30s interval)
- **Frontend**: frontend:3000 (60s interval)
- **CVAT**: cvat:8080 (60s interval)

**External Monitoring:**
```yaml
# Blackbox exporter for external monitoring
- job_name: 'blackbox-http'
  targets:
    - http://155.138.239.131/health
    - https://155.138.239.131/health
    - http://155.138.239.131/api/health

# SSL certificate monitoring
- job_name: 'blackbox-ssl'
  targets:
    - https://155.138.239.131:443
```

### Loki Log Aggregation

```yaml
# /scripts/monitoring/loki.yml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096
  log_level: warn

# Limits configuration
limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 4
  ingestion_burst_size_mb: 6
  max_streams_per_user: 10000
  max_line_size: 256KB
  max_entries_limit_per_query: 5000
  retention_period: 744h  # 31 days

# Storage configuration
storage_config:
  boltdb_shipper:
    active_index_directory: /loki/boltdb-shipper-active
    cache_location: /loki/boltdb-shipper-cache
    cache_ttl: 24h
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

# Compactor configuration
compactor:
  working_directory: /loki/compactor
  shared_store: filesystem
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 150
```

**Log Aggregation Features:**
- **Retention**: 31 days log retention
- **Compression**: WAL compression enabled
- **Performance**: 16 concurrent queries, 4MB/s ingestion rate
- **Storage**: Filesystem-based with automatic cleanup
- **Integration**: Prometheus metrics integration

### Grafana Dashboard Configuration

```yaml
# /scripts/monitoring/grafana/datasources/prometheus.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
    
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: true
```

**Dashboard Features:**
- **System Metrics**: CPU, Memory, Disk, Network utilization
- **Application Metrics**: Request rates, response times, error rates
- **Database Metrics**: Connection pools, query performance, deadlocks
- **Container Metrics**: Docker container resource usage
- **Log Analytics**: Error tracking, performance bottlenecks
- **Business Metrics**: Video processing rates, detection accuracy

### Promtail Log Collection

```yaml
# /scripts/monitoring/promtail.yml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  # Docker containers
  - job_name: containers
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: container
      - source_labels: ['__meta_docker_container_log_stream']
        target_label: stream
```

## Docker Production Configuration

### Production Docker Compose

```yaml
# docker-compose.prod.yml (inferred structure)
version: '3.8'

services:
  # Load Balancer
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
    networks:
      - production_network

  # Application Services
  frontend:
    build: 
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - NODE_ENV=production
      - REACT_APP_API_URL=https://155.138.239.131/api
      - REACT_APP_WS_URL=wss://155.138.239.131/ws
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    restart: unless-stopped
    networks:
      - production_network

  backend:
    build: 
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - AIVALIDATION_APP_ENVIRONMENT=production
      - VRU_DATABASE_URL=${PRODUCTION_DATABASE_URL}
      - VRU_REDIS_URL=${PRODUCTION_REDIS_URL}
      - VRU_SECRET_KEY=${PRODUCTION_SECRET_KEY}
      - UVICORN_WORKERS=4
      - UVICORN_WORKER_TIMEOUT=120
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
    restart: unless-stopped
    networks:
      - production_network

  # Database Services
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=${PRODUCTION_DB_NAME}
      - POSTGRES_USER=${PRODUCTION_DB_USER}
      - POSTGRES_PASSWORD=${PRODUCTION_DB_PASSWORD}
    volumes:
      - postgres_prod_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
    restart: unless-stopped
    networks:
      - production_network

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${PRODUCTION_REDIS_PASSWORD}
    volumes:
      - redis_prod_data:/data
    deploy:
      resources:
        limits:
          memory: 256M
        reservations:
          memory: 128M
    restart: unless-stopped
    networks:
      - production_network

  # Monitoring Stack
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./scripts/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'
      - '--storage.tsdb.retention.size=10GB'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'
    restart: unless-stopped
    networks:
      - production_network

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_SERVER_ROOT_URL=https://155.138.239.131/grafana
    volumes:
      - grafana_data:/var/lib/grafana
      - ./scripts/monitoring/grafana:/etc/grafana/provisioning
    restart: unless-stopped
    networks:
      - production_network

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./scripts/monitoring/loki.yml:/etc/loki/local-config.yaml
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped
    networks:
      - production_network

networks:
  production_network:
    driver: bridge
    name: ai_validation_production

volumes:
  postgres_prod_data:
  redis_prod_data:
  prometheus_data:
  grafana_data:
  loki_data:
  ssl_certificates:
```

## Security Configuration

### SSL/TLS Configuration

```nginx
# /nginx/nginx.conf
server {
    listen 80;
    server_name 155.138.239.131;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name 155.138.239.131;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    
    # Frontend
    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Backend API
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        client_max_body_size 100M;
    }
    
    # WebSocket support
    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Monitoring endpoints
    location /prometheus/ {
        proxy_pass http://prometheus:9090/;
        auth_basic "Prometheus";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
    
    location /grafana/ {
        proxy_pass http://grafana:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Environment Security

```bash
# Production environment variables (secure)
export PRODUCTION_SECRET_KEY="$(openssl rand -hex 32)"
export PRODUCTION_JWT_SECRET_KEY="$(openssl rand -hex 32)"
export PRODUCTION_DATABASE_URL="postgresql://user:$(pwgen 32 1)@postgres:5432/ai_validation"
export PRODUCTION_REDIS_URL="redis://:$(pwgen 32 1)@redis:6379/0"
export GRAFANA_ADMIN_PASSWORD="$(pwgen 16 1)"

# Database credentials
export PRODUCTION_DB_NAME="ai_validation"
export PRODUCTION_DB_USER="ai_user"
export PRODUCTION_DB_PASSWORD="$(pwgen 32 1)"
export PRODUCTION_REDIS_PASSWORD="$(pwgen 32 1)"

# SSL certificate paths
export SSL_CERT_PATH="/opt/ssl/fullchain.pem"
export SSL_KEY_PATH="/opt/ssl/privkey.pem"
```

### Firewall Configuration

```bash
# UFW firewall rules
ufw default deny incoming
ufw default allow outgoing

# SSH (restricted to specific IPs)
ufw allow from 192.168.1.0/24 to any port 22

# HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Monitoring (internal only)
ufw allow from 172.20.0.0/16 to any port 9090  # Prometheus
ufw allow from 172.20.0.0/16 to any port 3001  # Grafana
ufw allow from 172.20.0.0/16 to any port 3100  # Loki

# Database (internal only)
ufw allow from 172.20.0.0/16 to any port 5432  # PostgreSQL
ufw allow from 172.20.0.0/16 to any port 6379  # Redis

ufw enable
```

## Performance Optimization

### Resource Allocation

```yaml
# Production resource limits
backend:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 2G
      reservations:
        cpus: '1.0'
        memory: 1G

frontend:
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 1G
      reservations:
        cpus: '0.5'
        memory: 512M

postgres:
  deploy:
    resources:
      limits:
        memory: 1G
      reservations:
        memory: 512M

redis:
  deploy:
    resources:
      limits:
        memory: 256M
      reservations:
        memory: 128M
```

### Database Performance Tuning

```postgresql
-- PostgreSQL production configuration
-- /var/lib/postgresql/data/postgresql.conf

# Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB

# Checkpoint settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Connection settings
max_connections = 200
shared_preload_libraries = 'pg_stat_statements'

# Logging
log_min_duration_statement = 1000
log_statement = 'none'
log_duration = on
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

### Redis Configuration

```redis
# /etc/redis/redis.conf (production)
maxmemory 128mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

## Backup Strategy

### Database Backup

```bash
#!/bin/bash
# /scripts/backup/database-backup.sh

BACKUP_DIR="/opt/backups/postgres"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup
docker exec ai_validation_postgres pg_dump -U ${PRODUCTION_DB_USER} ${PRODUCTION_DB_NAME} | gzip > "${BACKUP_DIR}/backup_${TIMESTAMP}.sql.gz"

# Cleanup old backups
find ${BACKUP_DIR} -name "backup_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

# Upload to S3 (optional)
# aws s3 cp "${BACKUP_DIR}/backup_${TIMESTAMP}.sql.gz" s3://ai-validation-backups/postgres/
```

### Application Data Backup

```bash
#!/bin/bash
# /scripts/backup/app-backup.sh

BACKUP_DIR="/opt/backups/app"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup uploaded videos
tar -czf "${BACKUP_DIR}/uploads_${TIMESTAMP}.tar.gz" -C /opt/ai-validation uploads/

# Backup configuration
tar -czf "${BACKUP_DIR}/config_${TIMESTAMP}.tar.gz" -C /opt/ai-validation \
    docker-compose.yml \
    nginx/ \
    scripts/ \
    .env.production

# Backup monitoring data
tar -czf "${BACKUP_DIR}/monitoring_${TIMESTAMP}.tar.gz" -C /var/lib/docker/volumes \
    ai_validation_prometheus_data/ \
    ai_validation_grafana_data/
```

## Deployment Automation

### Deployment Script

```bash
#!/bin/bash
# /scripts/deploy/production-deploy.sh

set -e

REPO_URL="https://github.com/your-org/ai-model-validation-platform.git"
DEPLOY_DIR="/opt/ai-validation"
BACKUP_DIR="/opt/backups/deployments"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "🚀 Starting production deployment..."

# Create deployment backup
echo "📦 Creating backup..."
mkdir -p "${BACKUP_DIR}"
tar -czf "${BACKUP_DIR}/pre-deploy_${TIMESTAMP}.tar.gz" -C "${DEPLOY_DIR}" .

# Pull latest code
echo "📥 Pulling latest code..."
cd "${DEPLOY_DIR}"
git pull origin main

# Build new images
echo "🔨 Building images..."
docker-compose -f docker-compose.prod.yml build --no-cache

# Run database migrations
echo "📊 Running migrations..."
docker-compose -f docker-compose.prod.yml exec -T backend alembic upgrade head

# Deploy with zero-downtime
echo "🔄 Deploying services..."
docker-compose -f docker-compose.prod.yml up -d --remove-orphans

# Health check
echo "🏥 Running health checks..."
sleep 30
curl -f https://155.138.239.131/health || {
    echo "❌ Health check failed, rolling back..."
    docker-compose -f docker-compose.prod.yml down
    tar -xzf "${BACKUP_DIR}/pre-deploy_${TIMESTAMP}.tar.gz" -C "${DEPLOY_DIR}"
    docker-compose -f docker-compose.prod.yml up -d
    exit 1
}

echo "✅ Deployment completed successfully!"
```

### CI/CD Integration

```yaml
# /.github/workflows/deploy.yml
name: Production Deployment

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup SSH
      uses: webfactory/ssh-agent@v0.5.4
      with:
        ssh-private-key: ${{ secrets.DEPLOY_SSH_KEY }}
    
    - name: Deploy to production
      run: |
        ssh -o StrictHostKeyChecking=no deploy@155.138.239.131 '
          cd /opt/ai-validation &&
          git pull origin main &&
          ./scripts/deploy/production-deploy.sh
        '
    
    - name: Notify deployment
      if: always()
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Monitoring and Alerting

### Alert Rules

```yaml
# /scripts/monitoring/alert_rules.yml
groups:
  - name: ai-validation-alerts
    rules:
    - alert: HighCPUUsage
      expr: cpu_usage_percent > 80
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High CPU usage detected"
        description: "CPU usage is {{ $value }}% for more than 5 minutes"
    
    - alert: HighMemoryUsage
      expr: memory_usage_percent > 90
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "High memory usage detected"
        description: "Memory usage is {{ $value }}% for more than 5 minutes"
    
    - alert: DatabaseConnectionFailure
      expr: up{job="postgres"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Database connection failure"
        description: "PostgreSQL database is not responding"
    
    - alert: HighErrorRate
      expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
      for: 2m
      labels:
        severity: warning
      annotations:
        summary: "High error rate detected"
        description: "Error rate is {{ $value }} requests/second"
```

### Health Check Monitoring

```bash
#!/bin/bash
# /scripts/monitoring/health-check.sh

ENDPOINTS=(
    "https://155.138.239.131/health"
    "https://155.138.239.131/api/health"
    "https://155.138.239.131/prometheus/-/healthy"
    "https://155.138.239.131/grafana/api/health"
)

for endpoint in "${ENDPOINTS[@]}"; do
    echo "Checking ${endpoint}..."
    if ! curl -sf "${endpoint}" > /dev/null; then
        echo "❌ ${endpoint} is not healthy"
        # Send alert notification
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚨 Health check failed for ${endpoint}\"}" \
            "${SLACK_WEBHOOK_URL}"
    else
        echo "✅ ${endpoint} is healthy"
    fi
done
```

## Disaster Recovery

### Recovery Procedures

```bash
# Complete system recovery
#!/bin/bash
# /scripts/recovery/full-recovery.sh

echo "🚨 Starting disaster recovery..."

# Stop all services
docker-compose -f docker-compose.prod.yml down

# Restore database from latest backup
LATEST_DB_BACKUP=$(ls -t /opt/backups/postgres/backup_*.sql.gz | head -1)
echo "Restoring database from ${LATEST_DB_BACKUP}..."
gunzip -c "${LATEST_DB_BACKUP}" | docker exec -i ai_validation_postgres psql -U ${PRODUCTION_DB_USER} ${PRODUCTION_DB_NAME}

# Restore application data
LATEST_APP_BACKUP=$(ls -t /opt/backups/app/uploads_*.tar.gz | head -1)
echo "Restoring uploads from ${LATEST_APP_BACKUP}..."
tar -xzf "${LATEST_APP_BACKUP}" -C /opt/ai-validation

# Restart services
docker-compose -f docker-compose.prod.yml up -d

echo "✅ Disaster recovery completed"
```

This comprehensive deployment configuration provides enterprise-grade reliability, monitoring, security, and scalability for the AI Model Validation Platform in production environments.