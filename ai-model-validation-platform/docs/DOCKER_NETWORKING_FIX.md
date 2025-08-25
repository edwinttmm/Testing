# Docker Container Networking Fix

This document outlines the comprehensive fix for Docker container networking issues preventing backend-PostgreSQL communication.

## Problem Summary

The original Docker setup had several networking issues:

1. **Missing explicit Docker network configuration**
2. **Incomplete health checks** - Redis had no health check
3. **Missing wait conditions** for proper startup order
4. **PostgreSQL hostname resolution issue** - Backend couldn't resolve "postgres" service name
5. **No proper container dependency management**
6. **Missing comprehensive health monitoring**

## Solution Overview

### 1. Enhanced docker-compose.yml

**Key Improvements:**
- Added explicit network configuration with custom subnet
- Enhanced health checks for all services
- Proper container startup dependencies
- Container hostnames and names for better DNS resolution
- Extended timeouts and retry logic
- Comprehensive restart policies

### 2. Network Configuration

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
    driver_opts:
      com.docker.network.bridge.enable_icc: "true"
      com.docker.network.bridge.enable_ip_masquerade: "true"
      com.docker.network.driver.mtu: "1500"
```

### 3. Service Improvements

#### PostgreSQL Service
- Added container hostname: `postgres`
- Enhanced health checks with proper user/database validation
- Increased connection limits and optimized settings
- Better logging configuration for debugging

#### Redis Service  
- Added proper health checks
- Configured data persistence
- Memory optimization settings

#### Backend Service
- Added database connection testing in startup command
- Enhanced health check endpoint at `/health`
- Proper wait conditions for database readiness
- Docker-specific environment variables

#### Frontend Service
- Added health checks
- Proper backend dependency management

## Files Created/Modified

### 1. Updated Files
- `docker-compose.yml` - Complete networking overhaul
- `backend/main.py` - Enhanced health check endpoint

### 2. New Files
- `scripts/docker-network-troubleshoot.sh` - Comprehensive troubleshooting script
- `scripts/docker-network-fix.sh` - Automated fix script  
- `scripts/test-database-connection.py` - Database connection testing
- `backend/health_check.py` - Enhanced health check system
- `docker-compose.override.yml` - Development-specific overrides
- `docs/DOCKER_NETWORKING_FIX.md` - This documentation

## Usage Instructions

### Quick Fix (Automated)

```bash
# Navigate to project directory
cd /path/to/ai-model-validation-platform

# Run automated fix
./scripts/docker-network-fix.sh --auto
```

### Manual Steps

1. **Stop existing containers:**
   ```bash
   docker-compose down --remove-orphans --volumes
   ```

2. **Clean up network:**
   ```bash
   docker network rm vru_validation_network 2>/dev/null || true
   ```

3. **Start services in order:**
   ```bash
   # Start database first
   docker-compose up -d postgres
   
   # Wait for database to be ready
   docker-compose exec postgres pg_isready -U postgres -d vru_validation
   
   # Start Redis
   docker-compose up -d redis
   
   # Start backend
   docker-compose up -d backend
   
   # Start frontend  
   docker-compose up -d frontend
   ```

### Troubleshooting

Use the comprehensive troubleshooting script:

```bash
./scripts/docker-network-troubleshoot.sh
```

**Menu Options:**
1. Check Docker status
2. Check network configuration  
3. Check container status
4. Test connectivity between containers
5. Test database connections
6. Test DNS resolution
7. Show container logs
8. Restart containers in correct order
9. Fix network issues (comprehensive fix)
10. Run all checks

### Health Check Endpoints

- **Basic Health:** `http://localhost:8000/health/simple`
- **Comprehensive Health:** `http://localhost:8000/health`
- **Database Health:** `http://localhost:8000/health/database`

## Network Architecture

```
┌─────────────────────────────────────────┐
│            Docker Network              │
│        vru_validation_network           │
│          172.20.0.0/16                 │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────┐    ┌─────────────┐    │
│  │ PostgreSQL  │    │    Redis    │    │
│  │   :5432     │    │    :6379    │    │
│  │ (postgres)  │    │   (redis)   │    │
│  └─────────────┘    └─────────────┘    │
│           │                   │         │
│           └───────┬───────────┘         │
│                   │                     │
│           ┌─────────────┐               │
│           │   Backend   │               │
│           │    :8000    │               │
│           │  (backend)  │               │
│           └─────────────┘               │
│                   │                     │
│           ┌─────────────┐               │
│           │  Frontend   │               │
│           │    :3000    │               │
│           │ (frontend)  │               │
│           └─────────────┘               │
│                                         │
└─────────────────────────────────────────┘
```

## Container Dependencies

```
PostgreSQL (healthy) ──┐
                       ├─→ Backend (healthy) ──→ Frontend
Redis (healthy) ───────┘
```

## Health Check Flow

1. **PostgreSQL Health Check:**
   - Tests `pg_isready` command
   - Validates database connection
   - Checks user/database accessibility

2. **Redis Health Check:**
   - Tests basic ping command
   - Validates authentication
   - Checks read/write operations

3. **Backend Health Check:**
   - Tests database connectivity
   - Tests Redis connectivity  
   - Validates file system access
   - Checks network connectivity to other services
   - Returns comprehensive health status

4. **Frontend Health Check:**
   - Simple HTTP availability check
   - Depends on backend being healthy

## Environment Variables

Key environment variables for networking:

```bash
# Database Configuration
AIVALIDATION_DATABASE_URL=postgresql://postgres:secure_password_change_me@postgres:5432/vru_validation
DATABASE_URL=postgresql://postgres:secure_password_change_me@postgres:5432/vru_validation

# Redis Configuration  
AIVALIDATION_REDIS_URL=redis://:secure_redis_password@redis:6379
REDIS_URL=redis://:secure_redis_password@redis:6379

# Docker Mode
AIVALIDATION_DOCKER_MODE=true
```

## Monitoring and Debugging

### Container Logs
```bash
# View all container logs
docker-compose logs

# View specific service logs
docker-compose logs postgres
docker-compose logs backend
docker-compose logs redis
```

### Network Inspection
```bash
# Inspect network configuration
docker network inspect vru_validation_network

# Check container connectivity
docker-compose exec backend ping postgres
docker-compose exec backend ping redis
```

### Database Connection Test
```bash
# Test from host
docker-compose exec backend python /app/scripts/test-database-connection.py

# Test from backend container
docker-compose exec backend python -c "
from database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('Database connection successful')
"
```

## Performance Optimizations

### PostgreSQL
- Increased `max_connections` to 200
- Optimized shared buffers and cache settings
- Enhanced connection pooling

### Redis  
- Configured memory limits and eviction policy
- Enabled data persistence with AOF
- Optimized for development workload

### Backend
- Increased database connection pool size
- Added connection health checks
- Implemented proper error handling and retries

## Security Considerations

1. **Network Isolation:** All containers run in isolated Docker network
2. **Service Authentication:** Redis requires password authentication  
3. **Database Security:** PostgreSQL with proper user/password authentication
4. **Container Security:** Non-root user execution where possible
5. **Secret Management:** Environment variable based configuration

## Maintenance

### Regular Tasks
1. Monitor container health status
2. Check logs for connection errors
3. Verify network connectivity
4. Update container images regularly
5. Monitor resource usage

### Backup Considerations
- PostgreSQL data persisted in Docker volume
- Redis data persisted with AOF
- Application uploads stored in Docker volume

## Troubleshooting Common Issues

### Issue: Backend cannot resolve "postgres"
**Solution:** Ensure containers are on same network and hostnames are set

### Issue: Database connection timeouts
**Solution:** Check health checks and increase timeout values

### Issue: Redis authentication failures  
**Solution:** Verify REDIS_PASSWORD environment variable

### Issue: Frontend cannot reach backend
**Solution:** Check backend health and network connectivity

### Issue: Containers restart continuously
**Solution:** Check health check configurations and resource limits

## Future Improvements

1. **Load Balancing:** Add nginx reverse proxy for production
2. **SSL/TLS:** Implement HTTPS for production deployment
3. **Monitoring:** Add Prometheus/Grafana monitoring stack
4. **Logging:** Centralized logging with ELK stack
5. **Backup:** Automated database backup system
6. **CI/CD:** Integration with deployment pipelines

## Support

For additional support or issues:

1. Run the troubleshooting script: `./scripts/docker-network-troubleshoot.sh`
2. Check container logs: `docker-compose logs [service_name]`
3. Test connectivity manually using the provided scripts
4. Consult this documentation for common solutions

## Changelog

### v1.0.0 (Current)
- Initial comprehensive networking fix
- Added health checks and proper dependencies
- Created troubleshooting and automation scripts
- Enhanced error handling and monitoring

---

**Last Updated:** August 24, 2025  
**Version:** 1.0.0