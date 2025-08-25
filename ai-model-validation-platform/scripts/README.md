# Container Orchestration Scripts

This directory contains comprehensive Docker container orchestration and troubleshooting scripts for the VRU Validation Platform.

## Scripts Overview

### 🚀 docker-orchestrator.sh
**Main orchestration script for container management**

```bash
# Quick start
./scripts/docker-orchestrator.sh start

# Available commands
./scripts/docker-orchestrator.sh [start|stop|restart|status|logs|build|clean|setup|help]
```

**Key Features:**
- Proper service startup ordering (PostgreSQL → Redis → Backend → Frontend)
- Health check validation at each stage
- Automatic environment setup
- Resource monitoring
- Graceful shutdown procedures

### 🔍 validate-connectivity.sh
**Comprehensive connectivity and health validation**

```bash
# Full validation
./scripts/validate-connectivity.sh

# Available commands
./scripts/validate-connectivity.sh [full|quick|database|redis|backend|frontend|network|info|help]
```

**Key Features:**
- Inter-service communication testing
- Database operation validation
- Redis connectivity verification
- API health endpoint testing
- Network configuration analysis

### 🔧 troubleshoot-containers.sh
**Advanced troubleshooting and diagnostics**

```bash
# Complete diagnosis
./scripts/troubleshoot-containers.sh

# Available commands
./scripts/troubleshoot-containers.sh [diagnose|service|logs|resources|connectivity|environment|help]
```

**Key Features:**
- Container health analysis
- Resource usage monitoring
- Error pattern detection in logs
- Service-specific troubleshooting guides
- Environment configuration validation

### ⏳ wait-for-services.sh
**Service dependency orchestration utility**

This script is integrated into containers to ensure proper startup sequences.

**Key Features:**
- Waits for PostgreSQL to be fully ready
- Validates Redis connectivity
- Configurable timeout and retry settings
- Service-specific health checks

### 🗄️ postgres-init.sh
**PostgreSQL initialization and readiness validation**

Ensures PostgreSQL is fully initialized before other services start.

**Key Features:**
- Comprehensive readiness validation
- Database connection testing
- Schema verification
- Startup logging

## Usage Examples

### Complete Setup and Startup
```bash
# Initial setup (creates .env, builds images)
./scripts/docker-orchestrator.sh setup

# Start all services with orchestration
./scripts/docker-orchestrator.sh start

# Validate everything is working
./scripts/validate-connectivity.sh
```

### Troubleshooting Workflow
```bash
# Check service status
./scripts/docker-orchestrator.sh status

# Run diagnostics if issues found
./scripts/troubleshoot-containers.sh

# Troubleshoot specific service
./scripts/troubleshoot-containers.sh service postgres

# Check logs for specific service
./scripts/troubleshoot-containers.sh logs backend
```

### Maintenance Operations
```bash
# View real-time logs
./scripts/docker-orchestrator.sh logs

# Restart specific service
./scripts/docker-orchestrator.sh restart backend

# Clean rebuild
./scripts/docker-orchestrator.sh clean
./scripts/docker-orchestrator.sh build
./scripts/docker-orchestrator.sh start
```

## Configuration

### Environment Variables
Scripts use these environment variables (set in `.env`):

```bash
# Service dependencies
WAIT_HOSTS=postgres:5432,redis:6379
WAIT_HOSTS_TIMEOUT=300
WAIT_SLEEP_INTERVAL=5

# Database configuration
POSTGRES_DB=vru_validation
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password_change_me

# Redis configuration
REDIS_PASSWORD=secure_redis_password

# Application security
AIVALIDATION_SECRET_KEY=your-secret-key-minimum-32-chars
```

### Health Check Endpoints
The scripts utilize these backend health check endpoints:

- `/health` - Basic health status
- `/health/detailed` - All dependencies status
- `/health/database` - Database-specific checks
- `/health/redis` - Redis-specific checks
- `/health/readiness` - Kubernetes-style readiness probe
- `/health/liveness` - Kubernetes-style liveness probe

## Advanced Features

### Production Deployment
```bash
# Use production configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Production-optimized settings include:
# - Resource limits and reservations
# - Performance tuning
# - Enhanced health checks
# - Optimized worker configurations
```

### CVAT Integration
```bash
# Start with CVAT services
docker-compose --profile cvat up -d

# CVAT will be available at http://localhost:8080
```

### Custom Networks
All services use the custom `vru_validation_network` with:
- Subnet: `172.20.0.0/16`
- Gateway: `172.20.0.1`
- Enhanced DNS resolution between services

## Troubleshooting Common Issues

### PostgreSQL Not Ready
```bash
# Check PostgreSQL logs
./scripts/troubleshoot-containers.sh service postgres

# Manual validation
docker-compose exec postgres pg_isready -U postgres
```

### Backend Connection Issues
```bash
# Comprehensive backend diagnosis
./scripts/troubleshoot-containers.sh service backend

# Test database connectivity from backend
docker-compose exec backend python -c "import psycopg2; print('DB OK')"
```

### Network Resolution Problems
```bash
# Test inter-service connectivity
./scripts/validate-connectivity.sh network

# Check DNS resolution
docker-compose exec backend nslookup postgres
```

### Resource Constraints
```bash
# Check resource usage
./scripts/troubleshoot-containers.sh resources

# View real-time container stats
docker stats
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
- name: Start services with orchestration
  run: |
    cp .env.example .env
    ./scripts/docker-orchestrator.sh setup
    ./scripts/docker-orchestrator.sh start

- name: Wait for services to be ready
  run: ./scripts/validate-connectivity.sh

- name: Run tests
  run: # your test commands

- name: Collect diagnostics on failure
  if: failure()
  run: ./scripts/troubleshoot-containers.sh
```

### Docker Swarm Integration
The scripts are compatible with Docker Swarm deployments with minor modifications for service naming conventions.

### Kubernetes Migration
Health check endpoints and readiness probes are designed to be compatible with Kubernetes health check patterns.

## Monitoring and Alerting

### Prometheus Integration
Health check endpoints return metrics in formats suitable for Prometheus scraping:

```bash
# Example metrics endpoint
curl http://localhost:8000/health/detailed | jq .
```

### Log Aggregation
All containers use structured logging compatible with ELK stack, Fluentd, and other log aggregation systems.

### Custom Alerting
The troubleshooting script can be integrated with alerting systems:

```bash
# Exit code based alerting
./scripts/validate-connectivity.sh quick
if [ $? -ne 0 ]; then
    # Send alert
    echo "Container health check failed" | mail -s "Alert" admin@example.com
fi
```

## Security Considerations

### Secrets Management
- Never commit `.env` files with real passwords
- Use Docker secrets in production
- Rotate passwords regularly
- Use strong, unique passwords for each service

### Network Security
- Custom network isolation
- No unnecessary port exposures
- TLS/SSL in production
- Firewall configuration for production deployments

### Container Security
- Regular image updates
- Vulnerability scanning
- Resource limits to prevent DoS
- Non-root user execution where possible

This comprehensive orchestration solution ensures reliable, predictable container startup sequences and provides extensive troubleshooting capabilities for the VRU Validation Platform.