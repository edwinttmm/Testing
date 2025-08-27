# VRU AI Model Validation Platform - Docker Deployment Guide

## Overview

This guide covers the complete Docker deployment process for the VRU AI Model Validation Platform. All Docker configurations have been tested and validated for production use.

## Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM
- 10GB+ disk space

### Basic Deployment
```bash
# Clone and setup
git clone <repository>
cd ai-model-validation-platform

# Download ML models
./models/download_models.sh

# Start development environment
docker-compose -f docker-compose.unified.yml up
```

### Production Deployment
```bash
# Set environment variables
cp backend/.env.production.template .env.production

# Start production services
docker-compose -f config/production/docker-compose.production.yml up -d
```

## Docker Configurations

### 1. Unified Development (docker-compose.unified.yml)
**Purpose**: Complete development environment with all services
**Services**: Backend, Frontend, Redis, PostgreSQL (optional)
**Best for**: Local development, testing

```bash
# Start all services
docker-compose -f docker-compose.unified.yml up

# Start specific profile
docker-compose -f docker-compose.unified.yml --profile development up
```

### 2. Production (config/production/docker-compose.production.yml)  
**Purpose**: Production deployment with microservices architecture
**Services**: API Gateway, ML Engine, Camera Service, Validation Engine, Frontend
**Best for**: Production deployment, high availability

```bash
# Production deployment
cd config/production
docker-compose up -d

# Scale specific services
docker-compose up -d --scale ml_engine=2
```

## Service Architecture

### Backend Services

#### 1. API Gateway (Port 8000)
- **Image**: Built from `backend/Dockerfile.unified`
- **Purpose**: Main API endpoint, request routing
- **Dependencies**: PostgreSQL, Redis
- **Health Check**: `http://localhost:8000/health`

#### 2. ML Inference Engine (Port 8001)
- **Image**: Built from `backend/Dockerfile.unified`
- **Purpose**: AI/ML processing, model inference
- **Features**: GPU support, model caching
- **Health Check**: `http://localhost:8001/health`

#### 3. Camera Service (Port 8002)
- **Image**: Built from `backend/Dockerfile.unified`
- **Purpose**: Camera integration, video capture
- **Features**: V4L2 support, hardware acceleration
- **Health Check**: `http://localhost:8002/health`

#### 4. Validation Engine (Port 8003)
- **Image**: Built from `backend/Dockerfile.unified`
- **Purpose**: Validation workflows, result processing
- **Health Check**: `http://localhost:8003/health`

### Frontend Service

#### React Application (Port 3000)
- **Image**: Built from `frontend/Dockerfile.unified`
- **Features**: Production-optimized, nginx-served
- **Health Check**: `http://localhost:3000/health`

### Support Services

#### PostgreSQL Database (Port 5432)
- **Image**: `postgres:15-alpine`
- **Storage**: Persistent volumes
- **Backup**: Automated backups configured

#### Redis Cache (Port 6379)
- **Image**: `redis:7-alpine`
- **Purpose**: Session management, caching
- **Persistence**: AOF enabled

## Build Targets

### Backend Dockerfile.unified Targets

#### 1. Development Target
```bash
docker build -f backend/Dockerfile.unified --target development .
```
- **Features**: Hot reload, debug tools
- **Python packages**: pytest, black, mypy
- **Port**: 8000

#### 2. Production Target
```bash
docker build -f backend/Dockerfile.unified --target production .
```
- **Features**: Optimized, security hardened
- **Workers**: Multi-worker uvicorn
- **Health checks**: Built-in monitoring

#### 3. Testing Target
```bash
docker build -f backend/Dockerfile.unified --target testing .
```
- **Features**: Test environment, coverage tools
- **Purpose**: CI/CD testing

#### 4. Migration Target
```bash
docker build -f backend/Dockerfile.unified --target migration .
```
- **Features**: Database migration tools
- **Purpose**: Schema updates

### Frontend Dockerfile.unified Targets

#### 1. Development Target
```bash
docker build -f frontend/Dockerfile.unified --target development frontend/
```
- **Features**: Hot reload, dev server
- **Port**: 3000

#### 2. Build Target
```bash
docker build -f frontend/Dockerfile.unified --target build frontend/
```
- **Features**: Optimized build, minification
- **Purpose**: CI/CD builds

#### 3. Production Target
```bash
docker build -f frontend/Dockerfile.unified --target production frontend/
```
- **Features**: nginx-served, compressed
- **Security**: Headers, CORS configured

## Environment Configuration

### Environment Files

#### Development (.env.development)
```bash
VRU_ENVIRONMENT=development
VRU_DEBUG=true
VRU_DATABASE_TYPE=sqlite
VRU_EXTERNAL_IP=localhost
```

#### Production (.env.production)
```bash
VRU_ENVIRONMENT=production
VRU_DEBUG=false
VRU_DATABASE_TYPE=postgresql
VRU_EXTERNAL_IP=155.138.239.131
VRU_SECRET_KEY=<generate-secure-key>
```

### Required Environment Variables
- `VRU_ENVIRONMENT`: deployment environment
- `VRU_EXTERNAL_IP`: external IP address
- `VRU_DATABASE_URL`: database connection string
- `VRU_REDIS_URL`: Redis connection string
- `VRU_SECRET_KEY`: application secret key

## ML Model Management

### Model Directory Structure
```
models/
├── README.md
├── download_models.sh
├── yolov8n.pt          # Nano model (6MB)
├── yolov8s.pt          # Small model (22MB)
└── yolov8m.pt          # Medium model (52MB)
```

### Model Download
```bash
# Download all models
./models/download_models.sh

# Download specific models
DOWNLOAD_ALL_MODELS=true ./models/download_models.sh
```

### GPU Support
Models automatically detect and use GPU acceleration when available:
- **NVIDIA**: CUDA support
- **AMD**: ROCm support  
- **CPU**: Fallback mode

## Camera Integration

### Hardware Support
The platform supports various camera interfaces:
- **USB Cameras**: /dev/video0, /dev/video1
- **V4L2 Devices**: Video4Linux2 compatible
- **IP Cameras**: RTSP/HTTP streams

### Docker Configuration
```yaml
devices:
  - /dev/video0:/dev/video0
  - /dev/video1:/dev/video1
cap_add:
  - SYS_ADMIN
```

### Permissions
```bash
# Add user to video group
sudo usermod -a -G video $USER

# Set device permissions
sudo chmod 666 /dev/video*
```

## Security Configuration

### Network Security
- **Firewall**: Configure iptables/ufw rules
- **CORS**: Configured for specific origins
- **HTTPS**: SSL/TLS termination at nginx

### Container Security
- **Non-root user**: All containers run as non-root
- **Read-only volumes**: Static content mounted read-only
- **Health checks**: Automated health monitoring

### Secrets Management
```bash
# Generate secure secrets
openssl rand -hex 32 > .env.secret_key

# Use Docker secrets (production)
echo "secret_key_value" | docker secret create vru_secret_key -
```

## Monitoring and Logging

### Health Checks
All services include comprehensive health checks:
```bash
# Check service health
docker-compose ps
curl http://localhost:8000/health
curl http://localhost:3000/health
```

### Logging
- **Structured logging**: JSON format
- **Log aggregation**: Centralized logging
- **Log rotation**: Automatic cleanup

### Metrics
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **Custom metrics**: Application-specific metrics

## Troubleshooting

### Common Issues

#### 1. Build Failures
```bash
# Check build context
docker build --no-cache -f backend/Dockerfile.unified .

# Verify requirements files
ls -la backend/requirements*.txt
```

#### 2. Permission Issues
```bash
# Fix volume permissions
sudo chown -R $USER:$USER ./backend/uploads
sudo chown -R $USER:$USER ./models
```

#### 3. Network Connectivity
```bash
# Test service connectivity
docker-compose exec backend curl http://redis:6379
docker-compose exec frontend curl http://backend:8000/health
```

#### 4. Database Issues
```bash
# Reset database
docker-compose down -v
docker-compose up -d postgres
docker-compose exec backend python database_init.py
```

### Debug Commands
```bash
# View service logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Execute commands in containers
docker-compose exec backend python -c "import torch; print(torch.__version__)"
docker-compose exec backend ls -la models/

# Check resource usage
docker stats
```

## Performance Optimization

### Resource Allocation
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

### Caching Strategy
- **Redis**: Session and API response caching
- **nginx**: Static asset caching
- **Model caching**: ML model persistence

### Scaling
```bash
# Horizontal scaling
docker-compose up -d --scale ml_engine=3
docker-compose up -d --scale api_gateway=2

# Load balancing
# Configure nginx upstream for load balancing
```

## Backup and Recovery

### Database Backup
```bash
# PostgreSQL backup
docker-compose exec postgres pg_dump -U vru_user vru_validation > backup.sql

# SQLite backup
docker-compose exec backend cp dev_database.db backup_database.db
```

### Volume Backup
```bash
# Backup volumes
docker run --rm -v vru_uploaded_videos:/data -v $(pwd):/backup alpine tar czf /backup/videos.tar.gz -C /data .
```

### Recovery
```bash
# Restore database
docker-compose exec postgres psql -U vru_user -d vru_validation < backup.sql

# Restore volumes
docker run --rm -v vru_uploaded_videos:/data -v $(pwd):/backup alpine tar xzf /backup/videos.tar.gz -C /data
```

## Deployment Checklist

### Pre-deployment
- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] Firewall rules configured
- [ ] Models downloaded
- [ ] Database initialized

### Deployment
- [ ] Services started successfully
- [ ] Health checks passing
- [ ] External connectivity verified
- [ ] Performance monitoring active

### Post-deployment
- [ ] Backup systems configured
- [ ] Monitoring alerts setup
- [ ] Documentation updated
- [ ] Team access configured

## Support and Maintenance

### Regular Tasks
- Monitor resource usage
- Update ML models
- Review security logs
- Backup critical data
- Update dependencies

### Updates
```bash
# Update images
docker-compose pull
docker-compose up -d

# Update models
./models/download_models.sh
docker-compose restart ml_engine
```

This deployment guide ensures reliable, secure, and scalable operation of the VRU AI Model Validation Platform in Docker environments.