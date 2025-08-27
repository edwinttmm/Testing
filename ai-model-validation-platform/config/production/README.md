# VRU Production Deployment Guide

## Overview

Complete production deployment for the VRU AI Model Validation Platform to server **155.138.239.131**.

## Architecture

The production deployment consists of the following services:

### Core Services
- **API Gateway** (Port 8000) - Main application entry point
- **ML Engine** (Port 8001) - YOLO detection and ML inference
- **Camera Service** (Port 8002) - Camera integration and real-time feeds
- **Validation Engine** (Port 8003) - Workflow validation and orchestration

### Infrastructure Services  
- **PostgreSQL** (Port 5432) - Production database
- **Redis** (Port 6379) - Caching and session management
- **Nginx** (Port 80/443) - Reverse proxy and load balancer
- **Prometheus** (Port 9090) - Metrics collection
- **Grafana** (Port 3001) - Monitoring dashboards

### Frontend
- **React App** (Port 3000) - User interface

## Quick Start

1. **Deploy to Production Server**:
   ```bash
   # Deploy to 155.138.239.131
   ./deploy-production.sh deploy
   ```

2. **Check Status**:
   ```bash
   ./deploy-production.sh status
   ```

3. **View Logs**:
   ```bash
   ./deploy-production.sh logs
   ```

## Service URLs

After deployment, services will be available at:

- **Frontend**: http://155.138.239.131
- **API Gateway**: http://155.138.239.131/docs  
- **ML Engine**: http://155.138.239.131:8001/docs
- **Camera Service**: http://155.138.239.131:8002/docs
- **Validation Engine**: http://155.138.239.131:8003/docs
- **Monitoring**: http://155.138.239.131:3001

## Configuration

### Environment Variables

Key production environment variables in `.env.production`:

```env
VRU_ENVIRONMENT=production
VRU_EXTERNAL_IP=155.138.239.131
VRU_DATABASE_PASSWORD=CHANGE_ME_SECURE_PASSWORD
VRU_REDIS_PASSWORD=CHANGE_ME_SECURE_REDIS_PASSWORD
VRU_SECRET_KEY=GENERATE_SECURE_SECRET_KEY
```

### Security

**IMPORTANT**: Before deploying to production:

1. Change all default passwords in `.env.production`
2. Generate secure secret keys
3. Configure SSL certificates (optional)
4. Set up firewall rules
5. Configure backup strategies

## Service Architecture

```
Internet
    |
[Nginx Reverse Proxy] :80, :443
    |
    ├─ Frontend :3000
    ├─ API Gateway :8000
    ├─ ML Engine :8001
    ├─ Camera Service :8002
    └─ Validation Engine :8003
         |
    ┌────┴──────┐
    │  Redis    │  PostgreSQL
    │  :6379    │    :5432
    └───────────┘
```

## Monitoring

The deployment includes comprehensive monitoring:

- **Prometheus**: Metrics collection from all services
- **Grafana**: Dashboards and visualizations  
- **Health Checks**: Automated service health monitoring
- **Log Aggregation**: Centralized logging with rotation

## Scaling

The deployment is designed for horizontal scaling:

- **API Gateway**: Can run multiple workers (configured to 4)
- **ML Engine**: Supports GPU acceleration and batch processing
- **Database**: PostgreSQL with connection pooling
- **Redis**: Optimized for caching and session management

## Deployment Commands

```bash
# Full deployment
./deploy-production.sh deploy

# Check services
./deploy-production.sh status

# View logs
./deploy-production.sh logs

# Restart services
./deploy-production.sh restart

# Stop services
./deploy-production.sh stop
```

## Troubleshooting

### Common Issues

1. **Services Not Starting**: Check logs with `./deploy-production.sh logs`
2. **Connection Issues**: Verify firewall rules and network configuration
3. **Performance Issues**: Monitor resource usage via Grafana dashboard
4. **Database Issues**: Check PostgreSQL logs and connections

### Health Checks

All services provide health check endpoints:

```bash
curl http://155.138.239.131:8000/health  # API Gateway
curl http://155.138.239.131:8001/health  # ML Engine  
curl http://155.138.239.131:8002/health  # Camera Service
curl http://155.138.239.131:8003/health  # Validation Engine
```

## Backup and Recovery

The deployment includes:

- **Database Backups**: Automated PostgreSQL backups
- **Configuration Backups**: All configuration files backed up
- **Volume Persistence**: Data volumes for persistent storage
- **Recovery Scripts**: Automated recovery procedures

## Security Considerations

- All services run with non-root users
- Network isolation via Docker networks
- Rate limiting on public endpoints
- Input validation and sanitization
- Secure password policies
- Regular security updates

## Support

For deployment issues:

1. Check the logs: `./deploy-production.sh logs`
2. Verify service health: `./deploy-production.sh status`  
3. Review configuration files
4. Check system resources (CPU, memory, disk)
5. Validate network connectivity

This deployment provides a production-ready, scalable, and monitored VRU validation platform.