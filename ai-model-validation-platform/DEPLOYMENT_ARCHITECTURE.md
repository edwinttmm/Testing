# VRU AI Model Validation Platform - Production Deployment Architecture

## Executive Summary

This document describes the unified deployment architecture implemented to resolve fundamental deployment failures and establish a production-ready system for the VRU AI Model Validation Platform on server 155.138.239.131.

## Problem Statement

The original deployment system suffered from multiple architectural issues:

1. **Path Inconsistencies**: Configuration files scattered across different locations with conflicting path references
2. **Build Context Failures**: Docker services unable to locate source files due to incorrect relative paths
3. **Environment Configuration Fragmentation**: Multiple .env files with conflicting settings
4. **Missing Production Configuration**: Essential configuration files referenced but not present
5. **Deployment Script Architecture**: Script expected files in locations that didn't match actual project structure

## Solution Architecture

### 1. Unified Root-Based Architecture

**Decision**: All deployment operations work from the project root directory with consistent relative paths.

**Implementation**:
- Deployment script (`deploy-production.sh`) placed in project root
- All path references are relative to project root
- Docker build contexts use project root as base

**Benefits**:
- Eliminates path confusion
- Consistent deployment from any environment
- Simplified troubleshooting

### 2. Consolidated Configuration Structure

**Before**: Multiple scattered configuration files
```
config/production/deploy-production.sh
config/production/docker-compose.production.yml
.env.production (multiple locations)
backend/.env.production
frontend/.env.production
```

**After**: Unified configuration at project root
```
PROJECT_ROOT/
├── deploy-production.sh              # Main deployment script
├── docker-compose.production.yml     # Production services
├── .env.production                   # Unified environment config
├── models/                           # ML models directory
└── config/production/                # Generated configs (created by script)
    ├── nginx.conf
    ├── prometheus.yml
    ├── postgresql.conf
    ├── redis.conf
    ├── ml_config.yaml
    └── validation_config.yaml
```

### 3. Service-Oriented Architecture

The production deployment implements a microservices architecture:

#### Core Services
- **API Gateway**: Main entry point (port 8000)
- **ML Engine**: AI inference processing (port 8001)
- **Camera Service**: Hardware integration (port 8002)
- **Validation Engine**: Workflow orchestration (port 8003)
- **Frontend**: React application (port 3000)

#### Infrastructure Services
- **PostgreSQL**: Production database
- **Redis**: Caching and session management
- **Prometheus**: Metrics collection
- **Grafana**: Monitoring dashboards
- **Nginx**: Reverse proxy and load balancer

### 4. Environment Configuration Strategy

**Unified .env.production file** with:
- Comprehensive environment variables for all services
- External IP configuration (155.138.239.131)
- Service discovery via Docker networking
- Security configurations with generated passwords
- Legacy compatibility for existing code

### 5. Deployment Script Architecture

**Modular deployment script** with these phases:
1. **Validation**: Pre-flight checks (network, SSH, files)
2. **Remote Setup**: Server preparation and Docker installation
3. **Configuration Generation**: Dynamic config file creation
4. **Application Deployment**: File transfer and extraction
5. **Service Orchestration**: Docker Compose deployment
6. **System Integration**: Service registration and monitoring setup
7. **Verification**: Health checks and endpoint testing

## Technical Decisions

### ADR-001: Project Root as Deployment Base

**Status**: Accepted
**Context**: Previous deployment failures due to path inconsistencies
**Decision**: Use project root as single source of truth for all paths
**Consequences**: Simplified debugging, consistent deployments, easier maintenance

### ADR-002: Dynamic Configuration Generation

**Status**: Accepted
**Context**: Missing and conflicting configuration files
**Decision**: Generate all production configs dynamically during deployment
**Consequences**: Always consistent configurations, reduced manual errors, environment-specific settings

### ADR-003: Microservices with Docker Compose

**Status**: Accepted
**Context**: Complex ML pipeline with multiple components
**Decision**: Use Docker Compose for service orchestration
**Consequences**: Better scaling, service isolation, easier debugging

### ADR-004: External Volume Binding

**Status**: Accepted
**Context**: Data persistence and performance requirements
**Decision**: Bind mount volumes to host directories under /opt/vru-platform
**Consequences**: Better performance, easier backup, persistent data storage

## Deployment Process

### Prerequisites
- SSH access to 155.138.239.131
- SSH keys configured for password-less authentication
- Project must be run from root directory

### Commands
```bash
# Full deployment
./deploy-production.sh deploy

# Pre-deployment validation only
./deploy-production.sh validate

# Setup remote environment only
./deploy-production.sh setup

# Verify running deployment
./deploy-production.sh verify

# View service logs
./deploy-production.sh logs

# Check service status
./deploy-production.sh status
```

### Remote Management
After deployment, remote management is available via:
```bash
# On the target server (155.138.239.131)
vru-platform status     # Check service status
vru-platform logs       # View logs
vru-platform restart    # Restart services
vru-platform backup     # Create database backup
```

## Security Considerations

### Network Security
- Firewall configured to allow only necessary ports (80, 443, 3000, 8000, SSH)
- Internal services use Docker networking
- PostgreSQL and Redis not exposed externally

### Authentication & Authorization
- Generated secure passwords for all services
- Database uses scram-sha-256 password encryption
- Redis password protection enabled

### Container Security
- Non-root users in containers
- Read-only configuration mounts
- Resource limits on all services

## Monitoring & Observability

### Health Checks
- All services have health check endpoints
- Docker health checks with proper timeouts
- Multi-level health verification during deployment

### Monitoring Stack
- **Prometheus**: Metrics collection from all services
- **Grafana**: Dashboards and visualization
- **Log Aggregation**: Centralized logging with rotation
- **System Monitoring**: Service status via systemd

### Service URLs
- Frontend: http://155.138.239.131:3000
- API Documentation: http://155.138.239.131:8000/docs
- Health Check: http://155.138.239.131:8000/health
- Monitoring: http://155.138.239.131:3001

## Data Flow Architecture

```
[Client] → [Nginx:80] → [Frontend:3000]
                    ↘ [API Gateway:8000] → [ML Engine:8001]
                                        → [Camera Service:8002]
                                        → [Validation Engine:8003]
                                        ↓
                                   [PostgreSQL:5432]
                                   [Redis:6379]
```

## Backup & Recovery

### Automated Backups
- Database backups via `vru-platform backup` command
- Log rotation every 14 days
- Volume snapshots for persistent data

### Recovery Procedures
- Service restart via systemd
- Data recovery from /opt/vru-platform/backups
- Full redeployment capability with `./deploy-production.sh update`

## Performance Optimization

### Resource Allocation
- API Gateway: 3 CPU, 3GB RAM
- ML Engine: 4 CPU, 4GB RAM  
- Database: 2 CPU, 2GB RAM
- Frontend: 1 CPU, 1GB RAM

### Scaling Strategy
- Horizontal scaling via additional worker containers
- Load balancing through Nginx
- Database connection pooling
- Redis caching layer

## Troubleshooting Guide

### Common Issues
1. **Service Won't Start**: Check Docker logs and health checks
2. **Database Connection Issues**: Verify PostgreSQL container status
3. **Frontend Not Loading**: Check API Gateway connectivity
4. **Slow Performance**: Monitor resource usage and cache hit rates

### Diagnostic Commands
```bash
# Check all services
./deploy-production.sh status

# View service logs
./deploy-production.sh logs

# Test health endpoints
curl http://155.138.239.131:8000/health

# Restart specific service
ssh root@155.138.239.131 'cd /opt/vru-platform && docker-compose -f docker-compose.production.yml restart api_gateway'
```

## Future Enhancements

### Phase 2 Improvements
- SSL/TLS certificates for HTTPS
- Multi-node deployment for high availability
- Advanced monitoring with alerting
- Automated backup to external storage
- CI/CD integration for automated deployments

### Scaling Considerations
- Kubernetes migration path for enterprise deployments
- Multi-region deployment capabilities
- Advanced load balancing strategies
- Database clustering for high availability

---

**Document Version**: 1.0  
**Last Updated**: 2025-08-27  
**Author**: VRU Platform Architecture Team  
**Review Status**: Production Ready