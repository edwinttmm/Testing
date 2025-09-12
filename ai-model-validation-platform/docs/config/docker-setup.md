# Docker Configuration Analysis

## Executive Summary

The AI Model Validation Platform implements a comprehensive Docker-based architecture with multi-service orchestration, production-ready health checks, optimized networking, and sophisticated volume management for scalable deployment.

## Docker Compose Architecture

### Service Overview

The platform consists of 5 primary services:
1. **PostgreSQL Database** (`postgres`) - Primary data storage
2. **Redis Cache** (`redis`) - Session management and caching
3. **FastAPI Backend** (`backend`) - API server and business logic
4. **React Frontend** (`frontend`) - Web interface
5. **CVAT Annotation** (`cvat` + `cvat_db`) - Optional annotation service

### Network Architecture

```yaml
networks:
  vru_validation_network:
    driver: bridge
    name: vru_validation_network
    ipam:
      driver: default
      config:
        - subnet: 172.20.0.0/16
          gateway: 172.20.0.1
```

**Network Benefits:**
- Isolated network subnet (172.20.0.0/16)
- Service-to-service communication
- External access control
- DNS resolution between containers

## Service Configurations

### PostgreSQL Database Service

```yaml
postgres:
  image: postgres:15
  container_name: ai_validation_postgres
  hostname: postgres
  environment:
    POSTGRES_DB: ${VRU_DATABASE_NAME}
    POSTGRES_USER: ${VRU_DATABASE_USER}
    POSTGRES_PASSWORD: ${VRU_DATABASE_PASSWORD}
    POSTGRES_INITDB_ARGS: "--encoding=UTF-8"
  ports:
    - "127.0.0.1:5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
  networks:
    - vru_validation_network
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${VRU_DATABASE_USER} -d ${VRU_DATABASE_NAME}"]
    interval: 10s
    timeout: 10s
    retries: 10
    start_period: 30s
  restart: unless-stopped
  command: [
    "postgres",
    "-c", "log_statement=all",
    "-c", "log_destination=stderr",
    "-c", "logging_collector=off",
    "-c", "max_connections=200"
  ]
```

**Key Features:**
- PostgreSQL 15 with UTF-8 encoding
- Database initialization script support
- Comprehensive health checks (pg_isready)
- Optimized connection limit (200 connections)
- Full SQL statement logging
- Persistent data volume
- Localhost-only port binding for security

### Redis Cache Service

```yaml
redis:
  image: redis:7-alpine
  container_name: ai_validation_redis
  hostname: redis
  ports:
    - "127.0.0.1:6379:6379"
  volumes:
    - redis_data:/data
  networks:
    - vru_validation_network
  healthcheck:
    test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 10s
  restart: unless-stopped
  command: redis-server --requirepass ${VRU_REDIS_PASSWORD} --appendonly yes
```

**Key Features:**
- Redis 7 Alpine (lightweight)
- Password authentication
- Append-only file persistence
- Health check with ping increment
- Data persistence volume
- Fast startup time (10s start period)

### Backend Service (FastAPI)

```yaml
backend:
  build: ./backend
  container_name: ai_validation_backend
  hostname: backend
  ports:
    - "0.0.0.0:8000:8000"
  environment:
    # Security Configuration
    - AIVALIDATION_SECRET_KEY=${VRU_SECRET_KEY}
    - SECRET_KEY=${VRU_SECRET_KEY}
    # Database Configuration
    - AIVALIDATION_DATABASE_URL=${VRU_DATABASE_URL}
    - DATABASE_URL=${VRU_DATABASE_URL}
    # Redis Configuration
    - AIVALIDATION_REDIS_URL=${VRU_REDIS_URL}
    - REDIS_URL=${VRU_REDIS_URL}
    # API Configuration
    - AIVALIDATION_API_PORT=${VRU_API_PORT}
    - AIVALIDATION_API_HOST=${VRU_API_HOST}
    - AIVALIDATION_APP_ENVIRONMENT=${VRU_ENVIRONMENT}
    - API_PORT=${VRU_API_PORT}
    - API_HOST=${VRU_API_HOST}
    # CORS Configuration
    - AIVALIDATION_CORS_ORIGINS=${VRU_CORS_ORIGINS}
    - ALLOWED_ORIGINS=${VRU_CORS_ORIGINS}
    # Docker Configuration
    - AIVALIDATION_DOCKER_MODE=${VRU_DOCKER_MODE}
    # Environment Variables
    - NODE_ENV=${NODE_ENV}
    - LOG_LEVEL=${LOG_LEVEL}
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  networks:
    - vru_validation_network
  volumes:
    - ./backend:/app
    - ./models:/app/models
    - uploaded_videos:/app/uploads
    - postgres_migrations:/app/migrations
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
  restart: unless-stopped
  command: ["/app/scripts/wait-for-services.sh", "sh", "-c", "python simple_startup.py && uvicorn main:socketio_app --host 0.0.0.0 --port 8000"]
```

**Key Features:**
- Custom Dockerfile build
- Unified environment variable configuration
- Service dependency health checks
- Development volume mounts
- Health endpoint monitoring
- Service wait script integration
- Socket.IO support
- Public port binding (0.0.0.0:8000)

### Frontend Service (React)

```yaml
frontend:
  build: ./frontend
  container_name: ai_validation_frontend
  hostname: frontend
  ports:
    - "0.0.0.0:3000:3000"
  environment:
    - REACT_APP_API_URL=${REACT_APP_API_URL}
    - REACT_APP_WS_URL=${REACT_APP_WS_URL}
    - REACT_APP_ML_ENGINE_URL=${REACT_APP_ML_ENGINE_URL}
    - REACT_APP_VIDEO_BASE_URL=${REACT_APP_VIDEO_BASE_URL}
    - REACT_APP_ENVIRONMENT=${REACT_APP_ENVIRONMENT}
    - REACT_APP_DEBUG=${REACT_APP_DEBUG}
    - NODE_ENV=${NODE_ENV}
    - GENERATE_SOURCEMAP=${GENERATE_SOURCEMAP}
    - CI=false
    - DOCKER=true
    - NODE_OPTIONS=--max_old_space_size=4096
  depends_on:
    backend:
      condition: service_healthy
  networks:
    - vru_validation_network
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
  restart: unless-stopped
```

**Key Features:**
- Custom React build with CRACO
- Environment-based configuration
- Backend dependency health check
- Memory optimization (4GB)
- Public port binding
- Docker-optimized environment

### CVAT Services (Optional Annotation)

#### CVAT Database
```yaml
cvat_db:
  image: postgres:15
  container_name: ai_validation_cvat_db
  hostname: cvat_db
  environment:
    POSTGRES_DB: cvat
    POSTGRES_USER: root
    POSTGRES_PASSWORD: cvat_password
  volumes:
    - cvat_db:/var/lib/postgresql/data
  networks:
    - vru_validation_network
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U root -d cvat"]
    interval: 10s
    timeout: 5s
    retries: 5
  restart: unless-stopped
```

#### CVAT Server
```yaml
cvat:
  image: openvino/cvat_server:latest
  container_name: ai_validation_cvat
  hostname: cvat
  restart: always
  depends_on:
    cvat_db:
      condition: service_healthy
    redis:
      condition: service_healthy
  environment:
    # Redis Configuration
    CVAT_REDIS_HOST: ${VRU_REDIS_HOST}
    CVAT_REDIS_PASSWORD: ${VRU_REDIS_PASSWORD}
    # PostgreSQL Configuration
    CVAT_POSTGRES_HOST: cvat_db
    CVAT_POSTGRES_PASSWORD: cvat_password
    # Django Configuration
    DJANGO_MODWSGI_EXTRA_ARGS: ""
    DJANGO_LOG_LEVEL: INFO
  ports:
    - "0.0.0.0:8080:8080"
  networks:
    - vru_validation_network
  volumes:
    - cvat_data:/home/django/data
    - cvat_keys:/home/django/keys
    - cvat_logs:/home/django/logs
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/api/server/about"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 60s
```

## Dockerfile Configurations

### Backend Dockerfile

```dockerfile
# Deployment-optimized Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install minimal dependencies
COPY requirements-min.txt .
RUN pip install --no-cache-dir -r requirements-min.txt

# Copy application files
COPY main.py .

# Create non-root user
RUN addgroup --gid 1000 appuser \
    && adduser --uid 1000 --gid 1000 --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Security Features:**
- Non-root user execution
- Minimal system dependencies
- Health check integration
- Clean package cache

### Frontend Dockerfile

```dockerfile
FROM node:20-alpine

# Install curl for healthcheck and bash for better script support
RUN apk add --no-cache curl bash

WORKDIR /app

# Set environment variables for faster startup and production readiness
ENV HOST=0.0.0.0
ENV PORT=3000
ENV NODE_ENV=development
ENV SKIP_PREFLIGHT_CHECK=true
ENV TSC_COMPILE_ON_ERROR=true
ENV FAST_REFRESH=true
ENV GENERATE_SOURCEMAP=false
ENV REACT_APP_API_URL=http://localhost:8000
ENV REACT_APP_WS_URL=ws://localhost:8000
ENV REACT_APP_ENVIRONMENT=development
ENV CI=false
ENV DOCKER=true

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies with better error handling
RUN npm ci --legacy-peer-deps --no-audit --no-fund --silent

# Copy source code
COPY . .

# Health check to ensure the app is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

EXPOSE 3000

# Copy and use start script
COPY start.sh ./
RUN chmod +x start.sh

# Start with custom script
CMD ["./start.sh"]
```

**Performance Features:**
- Alpine Linux base (minimal size)
- Layer caching optimization
- Silent npm install
- Custom start script
- Environment defaults

## Volume Management

### Persistent Volumes
```yaml
volumes:
  postgres_data:       # PostgreSQL database files
  postgres_migrations: # Database migration files
  redis_data:          # Redis persistence
  uploaded_videos:     # Video file storage
  cvat_db:             # CVAT database
  cvat_data:           # CVAT application data
  cvat_keys:           # CVAT authentication keys
  cvat_logs:           # CVAT log files
```

**Volume Strategy:**
- **Database persistence**: Ensures data survives container restarts
- **File storage**: Centralized video and media storage
- **Configuration persistence**: Maintains settings across deployments
- **Log retention**: Preserves application logs

### Development Volume Mounts

Backend Development Mounts:
```yaml
volumes:
  - ./backend:/app              # Live code reloading
  - ./models:/app/models        # ML model files
  - uploaded_videos:/app/uploads # Shared video storage
  - postgres_migrations:/app/migrations # Migration files
```

**Benefits:**
- Live code reloading
- Shared model storage
- Persistent uploads
- Migration management

## Health Check System

### Health Check Strategy

**Database Health Checks:**
```yaml
# PostgreSQL
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${VRU_DATABASE_USER} -d ${VRU_DATABASE_NAME}"]
  interval: 10s
  timeout: 10s
  retries: 10
  start_period: 30s

# Redis
healthcheck:
  test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 10s
```

**Application Health Checks:**
```yaml
# Backend
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s

# Frontend
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:3000"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

**Health Check Benefits:**
- Service readiness validation
- Automatic service restart on failures
- Dependency-based startup ordering
- Container orchestration support

## Service Dependencies

### Dependency Chain
```
Frontend → Backend → [PostgreSQL + Redis]
CVAT → [CVAT_DB + Redis]
```

**Dependency Configuration:**
```yaml
backend:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy

frontend:
  depends_on:
    backend:
      condition: service_healthy

cvat:
  depends_on:
    cvat_db:
      condition: service_healthy
    redis:
      condition: service_healthy
```

**Benefits:**
- Ordered service startup
- Health-based dependency resolution
- Automatic retry on failure
- Clean shutdown sequence

## Port Management

### Port Mapping Strategy

| Service    | Internal Port | External Port | Binding     |
|------------|---------------|---------------|-------------|
| PostgreSQL | 5432          | 5432          | 127.0.0.1   |
| Redis      | 6379          | 6379          | 127.0.0.1   |
| Backend    | 8000          | 8000          | 0.0.0.0     |
| Frontend   | 3000          | 3000          | 0.0.0.0     |
| CVAT       | 8080          | 8080          | 0.0.0.0     |

**Security Considerations:**
- Database services: Localhost binding only
- Application services: Public binding for external access
- Port isolation via network segmentation

## Environment Integration

### Environment Variable Flow

```
Host Environment → Docker Compose → Container Environment
```

**Variable Precedence:**
1. Host environment variables
2. .env file values
3. Docker Compose defaults
4. Container defaults

**Critical Environment Variables:**
```yaml
environment:
  # Unified Security
  - AIVALIDATION_SECRET_KEY=${VRU_SECRET_KEY}
  - SECRET_KEY=${VRU_SECRET_KEY}
  
  # Unified Database
  - AIVALIDATION_DATABASE_URL=${VRU_DATABASE_URL}
  - DATABASE_URL=${VRU_DATABASE_URL}
  
  # Unified Redis
  - AIVALIDATION_REDIS_URL=${VRU_REDIS_URL}
  - REDIS_URL=${VRU_REDIS_URL}
  
  # Unified CORS
  - AIVALIDATION_CORS_ORIGINS=${VRU_CORS_ORIGINS}
  - ALLOWED_ORIGINS=${VRU_CORS_ORIGINS}
```

## Production Deployment Configuration

### Production Docker Compose (docker-compose.prod.yml)

**Production Optimizations:**
- Multi-worker backend processes
- Production database settings
- SSL/TLS termination
- Resource limits
- Security hardening
- Monitoring integration

**Example Production Override:**
```yaml
version: '3.8'
services:
  backend:
    environment:
      - UVICORN_WORKERS=4
      - UVICORN_WORKER_TIMEOUT=120
      - LOG_LEVEL=WARNING
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
  
  frontend:
    environment:
      - NODE_ENV=production
      - GENERATE_SOURCEMAP=false
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## Docker Security Best Practices

### Security Implementation

**Container Security:**
- Non-root user execution
- Minimal base images
- Regular security updates
- Vulnerability scanning

**Network Security:**
- Isolated container network
- Service-specific port exposure
- Internal service communication
- Firewall integration

**Data Security:**
- Volume encryption support
- Backup integration
- Access control
- Audit logging

### Resource Management

**Resource Limits:**
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '1.0'
      memory: 1G
```

**Restart Policies:**
```yaml
restart: unless-stopped  # Restart on failure, not on manual stop
restart: always         # Always restart (CVAT)
restart: no            # Never restart (one-time tasks)
```

## Performance Optimizations

### Container Performance

**Build Optimization:**
- Multi-stage builds
- Layer caching
- Dependency caching
- Minimal image size

**Runtime Optimization:**
- Memory limits
- CPU allocation
- I/O optimization
- Network performance

### Monitoring and Logging

**Log Management:**
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

**Monitoring Integration:**
- Health check endpoints
- Metrics collection
- Performance monitoring
- Error tracking

## Troubleshooting Guide

### Common Docker Issues

1. **Service Won't Start**
   - Check health checks
   - Verify environment variables
   - Review service dependencies
   - Check port conflicts

2. **Database Connection Issues**
   - Verify PostgreSQL health check
   - Check database URL format
   - Confirm network connectivity
   - Review credentials

3. **Volume Mount Issues**
   - Check file permissions
   - Verify volume paths
   - Review mount syntax
   - Confirm data persistence

4. **Network Connectivity**
   - Verify network configuration
   - Check service hostnames
   - Review port mappings
   - Test internal communication

### Debugging Commands

**Service Status:**
```bash
docker-compose ps
docker-compose logs [service]
docker-compose exec [service] sh
```

**Health Checks:**
```bash
docker inspect [container] | grep Health
docker-compose exec postgres pg_isready
docker-compose exec redis redis-cli ping
```

**Network Debugging:**
```bash
docker network ls
docker network inspect vru_validation_network
docker-compose exec backend ping postgres
```

## Maintenance and Updates

### Update Strategy

**Service Updates:**
1. Backup data volumes
2. Pull new images
3. Update configurations
4. Rolling deployment
5. Verify health checks

**Security Updates:**
- Regular base image updates
- Dependency vulnerability scanning
- Security patch application
- Configuration review

### Backup Strategy

**Data Backup:**
```bash
# Database backup
docker-compose exec postgres pg_dump -U user dbname > backup.sql

# Volume backup
docker run --rm -v volume_name:/data -v $(pwd):/backup alpine tar czf /backup/backup.tar.gz -C /data .
```

**Configuration Backup:**
- Docker compose files
- Environment configurations
- Volume mount definitions
- Network settings

This comprehensive Docker configuration provides a robust, scalable, and maintainable deployment platform for the AI Model Validation Platform.