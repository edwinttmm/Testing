# Docker Container Orchestration Guide

## Overview

This guide provides comprehensive instructions for managing Docker containers in the VRU Validation Platform, addressing startup dependencies, health checks, and troubleshooting.

## Quick Start

### 1. Initial Setup
```bash
# Navigate to project root
cd /home/user/Testing/ai-model-validation-platform

# Set up environment (creates .env if it doesn't exist)
./scripts/docker-orchestrator.sh setup

# Start all services with proper orchestration
./scripts/docker-orchestrator.sh start
```

### 2. Validate Connectivity
```bash
# Run comprehensive connectivity tests
./scripts/validate-connectivity.sh

# Quick health check
./scripts/validate-connectivity.sh quick
```

## Architecture

### Service Dependencies
```
Frontend (3000) 
    ↓ depends on
Backend (8000)
    ↓ depends on
PostgreSQL (5432) + Redis (6379)
```

### Health Checks
- **PostgreSQL**: Extended readiness validation with schema checks
- **Redis**: Connection and operation testing
- **Backend**: API health endpoints with dependency verification
- **Frontend**: Static asset and connectivity validation

### Network Configuration
- Custom bridge network: `vru_validation_network`
- Subnet: `172.20.0.0/16`
- Gateway: `172.20.0.1`
- DNS resolution between containers enabled

## Scripts Reference

### docker-orchestrator.sh
Main orchestration script for container management.

```bash
# Start services in proper order
./scripts/docker-orchestrator.sh start

# Stop all services
./scripts/docker-orchestrator.sh stop

# Restart specific service
./scripts/docker-orchestrator.sh restart backend

# View service status and health
./scripts/docker-orchestrator.sh status

# View logs for all services
./scripts/docker-orchestrator.sh logs

# View logs for specific service
./scripts/docker-orchestrator.sh logs backend

# Build images without cache
./scripts/docker-orchestrator.sh build

# Clean up containers and resources
./scripts/docker-orchestrator.sh clean

# Complete setup (environment + build)
./scripts/docker-orchestrator.sh setup
```

### validate-connectivity.sh
Comprehensive connectivity and health validation.

```bash
# Full validation (default)
./scripts/validate-connectivity.sh

# Quick health check
./scripts/validate-connectivity.sh quick

# Test specific service
./scripts/validate-connectivity.sh database
./scripts/validate-connectivity.sh redis
./scripts/validate-connectivity.sh backend
./scripts/validate-connectivity.sh frontend

# Show detailed service information
./scripts/validate-connectivity.sh info
```

## Service Configuration

### PostgreSQL
- **Image**: postgres:15
- **Port**: 5432
- **Database**: vru_validation
- **Health Check**: Extended with schema validation
- **Initialization**: Custom init scripts in `/scripts/postgres-init.sh`

### Redis
- **Image**: redis:7-alpine
- **Port**: 6379
- **Password Protected**: Yes
- **Persistence**: AOF enabled
- **Health Check**: Connection and operation testing

### Backend (FastAPI)
- **Port**: 8000
- **Dependencies**: PostgreSQL (healthy) + Redis (healthy)
- **Wait Strategy**: Custom wait-for-services script
- **Health Endpoints**: 
  - `/health` - Basic health
  - `/health/detailed` - All dependencies
  - `/health/database` - Database specific
  - `/health/redis` - Redis specific
  - `/health/readiness` - Kubernetes-style readiness
  - `/health/liveness` - Kubernetes-style liveness

### Frontend (React)
- **Port**: 3000
- **Dependencies**: Backend (healthy)
- **Build**: Optimized for Docker with memory limits
- **Health Check**: Static asset availability

## Environment Configuration

### Required Environment Variables
```bash
# Security (REQUIRED)
AIVALIDATION_SECRET_KEY=your-secret-key-minimum-32-chars

# Database (REQUIRED)
POSTGRES_DB=vru_validation
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-password

# Redis (REQUIRED) 
REDIS_PASSWORD=your-redis-password
```

### Optional Configuration
```bash
# Wait timeouts
WAIT_HOSTS_TIMEOUT=300
WAIT_SLEEP_INTERVAL=5

# Performance
UVICORN_WORKERS=1
NODE_OPTIONS=--max_old_space_size=4096

# Logging
LOG_LEVEL=INFO
```

## Startup Sequence

### 1. Infrastructure Services
1. **PostgreSQL** starts first with health checks
2. **Redis** starts with connection validation
3. Both services must be healthy before proceeding

### 2. Application Services
1. **Backend** waits for PostgreSQL and Redis to be ready
2. **Frontend** waits for Backend to be healthy

### 3. Health Validation
1. Each service reports health status
2. Dependency verification between services
3. Network connectivity validation

## Troubleshooting

### Common Issues

#### PostgreSQL Not Ready
```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Manual connection test
docker-compose exec postgres pg_isready -U postgres

# Restart PostgreSQL
./scripts/docker-orchestrator.sh restart postgres
```

#### Backend Connection Failed
```bash
# Check backend logs
docker-compose logs backend

# Test database connectivity from backend
docker-compose exec backend python -c "
import psycopg2
import os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
print('Database connection successful')
"

# Restart backend
./scripts/docker-orchestrator.sh restart backend
```

#### Network Resolution Issues
```bash
# Check network configuration
docker network ls | grep vru
docker network inspect vru_validation_network

# Test DNS resolution
docker-compose exec backend nslookup postgres
docker-compose exec backend nslookup redis
```

#### Container Won't Start
```bash
# Check container status
docker-compose ps

# View detailed logs
docker-compose logs --tail=50 [service-name]

# Force recreation
docker-compose up --force-recreate [service-name]
```

### Emergency Recovery

#### Complete Reset
```bash
# Stop all services
./scripts/docker-orchestrator.sh stop

# Clean up all containers and volumes
./scripts/docker-orchestrator.sh clean
docker system prune -f
docker volume prune -f

# Rebuild and restart
./scripts/docker-orchestrator.sh setup
./scripts/docker-orchestrator.sh start
```

#### Database Recovery
```bash
# Backup database (if accessible)
docker-compose exec postgres pg_dump -U postgres vru_validation > backup.sql

# Reset database
docker-compose down
docker volume rm ai-model-validation-platform_postgres_data
docker-compose up -d postgres

# Restore database (if backup exists)
docker-compose exec -T postgres psql -U postgres vru_validation < backup.sql
```

## Monitoring and Health Checks

### Application URLs
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Detailed Health**: http://localhost:8000/health/detailed

### Health Check Endpoints

#### Basic Health
```bash
curl http://localhost:8000/health
```

#### Detailed Health (All Dependencies)
```bash
curl http://localhost:8000/health/detailed
```

#### Database Specific
```bash
curl http://localhost:8000/health/database
```

#### Redis Specific
```bash
curl http://localhost:8000/health/redis
```

### Container Resource Usage
```bash
# View real-time resource usage
docker stats

# View specific service resources
docker stats vru_postgres vru_redis vru_backend vru_frontend
```

## Production Considerations

### Security Enhancements
1. **Change Default Passwords**: Update all default passwords in production
2. **Network Isolation**: Use Docker secrets for sensitive data
3. **TLS/SSL**: Enable HTTPS for frontend and API
4. **Firewall Rules**: Restrict port access to necessary services only

### Performance Optimization
1. **Resource Limits**: Set CPU and memory limits for containers
2. **Worker Scaling**: Increase UVICORN_WORKERS for backend
3. **Database Tuning**: Configure PostgreSQL for production workloads
4. **Cache Strategy**: Implement Redis caching strategies

### Monitoring
1. **Log Aggregation**: Centralize logs with ELK stack or similar
2. **Metrics Collection**: Use Prometheus + Grafana
3. **Alert Rules**: Set up alerts for service failures
4. **Backup Strategy**: Implement automated database backups

## Advanced Features

### Optional Services

#### CVAT (Computer Vision Annotation Tool)
```bash
# Start with CVAT profile
docker-compose --profile cvat up -d

# Access CVAT at http://localhost:8080
```

### Multi-Environment Support
```bash
# Development
docker-compose -f docker-compose.yml up -d

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Custom Networks
The platform uses a custom bridge network for enhanced isolation:
- Network Name: `vru_validation_network`
- Subnet: `172.20.0.0/16`
- Gateway: `172.20.0.1`

## Support and Maintenance

### Log Files
- Container logs: `docker-compose logs [service]`
- Application logs: Check service-specific log directories
- System logs: `/var/log/docker.log` (if available)

### Backup Strategy
```bash
# Database backup
docker-compose exec postgres pg_dump -U postgres vru_validation > backup_$(date +%Y%m%d).sql

# Volume backup
docker run --rm -v ai-model-validation-platform_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data_backup.tar.gz /data
```

### Updates and Maintenance
```bash
# Update images
docker-compose pull

# Restart services with new images
./scripts/docker-orchestrator.sh restart

# Validate after updates
./scripts/validate-connectivity.sh full
```

This guide ensures bulletproof container startup sequences and provides comprehensive troubleshooting procedures for the VRU Validation Platform.