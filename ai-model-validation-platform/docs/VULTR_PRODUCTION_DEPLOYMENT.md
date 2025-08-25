# AI Model Validation Platform - Vultr Production Deployment Guide

## Overview
This guide provides complete instructions for deploying the AI Model Validation Platform on a Vultr server with external IP access (155.138.239.131). The deployment includes SSL/HTTPS configuration, security hardening, monitoring, and automated backup solutions.

## Server Configuration
- **Provider**: Vultr
- **External IP**: 155.138.239.131
- **Environment**: Production
- **SSL**: Let's Encrypt or Self-signed certificates
- **Reverse Proxy**: Nginx
- **Monitoring**: Prometheus + Grafana + Loki
- **Backup**: Automated daily backups

## Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04 LTS or newer
- **RAM**: Minimum 4GB (8GB recommended)
- **Storage**: Minimum 50GB (100GB recommended)
- **CPU**: 2 cores minimum (4 cores recommended)

### Required Software
- Docker (automatically installed)
- Docker Compose (automatically installed)
- Git
- Curl
- UFW (Uncomplicated Firewall)

## Quick Deployment

### 1. Clone Repository and Navigate
```bash
git clone <repository-url>
cd ai-model-validation-platform
```

### 2. Configure Environment
```bash
# Copy and edit the Vultr environment file
cp .env.vultr .env.vultr.local
nano .env.vultr.local

# CRITICAL: Update these values:
# - DOMAIN_NAME=your-domain.com (or use 155.138.239.131)
# - SSL_EMAIL=admin@your-domain.com
# - Generate secure passwords for all services
```

### 3. Run Automated Deployment
```bash
# Make sure you're on the Vultr server (IP: 155.138.239.131)
sudo ./scripts/deployment/deploy-vultr.sh
```

This script will automatically:
- Install dependencies
- Configure firewall
- Set up SSL certificates
- Deploy all services
- Configure monitoring
- Set up automated backups

## Manual Step-by-Step Deployment

### 1. Environment Configuration

#### Update Environment File
```bash
# Edit the Vultr environment file
nano .env.vultr
```

**Critical Configuration Items:**
```env
# Domain Configuration
DOMAIN_NAME=your-domain.com  # OR use IP: 155.138.239.131
SSL_EMAIL=admin@your-domain.com

# Security - GENERATE SECURE PASSWORDS
POSTGRES_PASSWORD=VultrProd2024!SecureDBPass#789$
REDIS_PASSWORD=VultrRedis2024!CacheSecure#456$
AIVALIDATION_SECRET_KEY=VultrSecretKey2024!ProductionAI...
CVAT_POSTGRES_PASSWORD=CVATVultr2024!AnnotationDB#123$
GRAFANA_PASSWORD=GrafanaVultr2024!MonitorDash#456$

# External IP Configuration
DATABASE_HOST=155.138.239.131
REDIS_HOST=155.138.239.131
BACKEND_HOST=155.138.239.131
FRONTEND_HOST=155.138.239.131

# Production Settings
APP_ENV=production
ENABLE_SSL=true
FORCE_HTTPS=true
```

### 2. Firewall Configuration

#### Install and Configure UFW
```bash
sudo apt update && sudo apt install ufw

# Reset UFW
sudo ufw --force reset

# Set default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (CRITICAL - don't lock yourself out)
sudo ufw allow ssh
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow Docker network
sudo ufw allow from 172.21.0.0/16

# Rate limiting for SSH
sudo ufw limit ssh

# Enable firewall
sudo ufw --force enable

# Check status
sudo ufw status verbose
```

### 3. SSL Certificate Setup

#### Option A: Let's Encrypt (Recommended for domains)
```bash
# Configure domain in .env.vultr first
sudo ./scripts/ssl/ssl-setup.sh
```

#### Option B: Self-signed certificates (for IP access)
```bash
# Force self-signed certificate
sudo ./scripts/ssl/ssl-setup.sh --self-signed
```

### 4. Deploy Services

#### Start Services
```bash
# Use the smart startup script
./scripts/startup.sh

# Or manually with Docker Compose
docker-compose -f docker-compose.vultr.yml --env-file .env.vultr up -d
```

#### Verify Deployment
```bash
# Check service status
docker-compose -f docker-compose.vultr.yml ps

# Check health endpoints
curl http://155.138.239.131/health
curl https://155.138.239.131/health

# Check logs
docker-compose -f docker-compose.vultr.yml logs -f
```

## Security Configuration

### Firewall Rules
```bash
# View current rules
sudo ufw status numbered

# Allow specific IPs (optional)
sudo ufw allow from YOUR_OFFICE_IP to any port 22

# Block specific IPs
sudo ufw deny from MALICIOUS_IP
```

### SSL/HTTPS Security Headers
The Nginx configuration includes security headers:
- `Strict-Transport-Security`
- `X-Frame-Options`
- `X-Content-Type-Options`
- `X-XSS-Protection`
- `Referrer-Policy`

### Rate Limiting
Configured in Nginx:
- API endpoints: 10 requests/second
- Login endpoints: 1 request/second
- Connection limit: 10 per IP

## Service Access

### Application URLs
- **Frontend**: https://155.138.239.131/
- **API**: https://155.138.239.131/api/
- **API Documentation**: https://155.138.239.131/api/docs
- **Health Check**: https://155.138.239.131/health

### Annotation Tools
- **CVAT**: https://155.138.239.131/cvat/

### Monitoring (Restricted Access)
- **Grafana**: https://155.138.239.131/grafana/
- **Prometheus**: https://155.138.239.131/prometheus/

## Monitoring and Alerting

### Monitoring Stack
- **Prometheus**: Metrics collection
- **Grafana**: Visualization and dashboards
- **Loki**: Log aggregation
- **Promtail**: Log shipping

### Key Metrics Monitored
- System resources (CPU, memory, disk)
- Application performance
- Database performance
- SSL certificate expiration
- Service availability

### Default Dashboards
- System Overview
- Application Performance
- Database Monitoring
- Nginx Performance
- Docker Container Metrics

## Backup and Maintenance

### Automated Backup
```bash
# Backup runs automatically daily at 2 AM UTC
# Manual backup:
sudo /usr/local/bin/backup-ai-validation.sh

# Custom backup location:
sudo BACKUP_DIR=/custom/path ./scripts/backup/backup-system.sh
```

### Backup Contents
- PostgreSQL databases (full and incremental)
- Redis data
- Docker volumes (uploaded files, etc.)
- Application configuration
- SSL certificates
- System logs
- Monitoring data

### Backup Restoration
```bash
# See restoration instructions:
sudo ./scripts/backup/backup-system.sh --restore-help

# Verify backup integrity:
sudo ./scripts/backup/backup-system.sh --verify-only
```

### Maintenance Tasks

#### Log Rotation
```bash
# Logs are automatically rotated daily
# Manual rotation:
sudo logrotate /etc/logrotate.d/ai-validation
```

#### SSL Certificate Renewal
```bash
# Auto-renewal is configured for Let's Encrypt
# Manual renewal:
sudo ./scripts/ssl/ssl-setup.sh --test-only
```

#### System Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Docker images
docker-compose -f docker-compose.vultr.yml pull
docker-compose -f docker-compose.vultr.yml up -d
```

## Troubleshooting

### Common Issues

#### 1. Services Won't Start
```bash
# Check Docker daemon
sudo systemctl status docker

# Check logs
docker-compose -f docker-compose.vultr.yml logs [service]

# Check disk space
df -h

# Check memory usage
free -h
```

#### 2. External Access Issues
```bash
# Check firewall
sudo ufw status

# Test ports
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443

# Check DNS resolution (if using domain)
nslookup your-domain.com

# Test SSL
openssl s_client -connect 155.138.239.131:443
```

#### 3. Database Connection Issues
```bash
# Check PostgreSQL status
docker exec ai_validation_postgres pg_isready -U postgres

# Check Redis status
docker exec ai_validation_redis redis-cli ping

# Check environment variables
docker-compose -f docker-compose.vultr.yml config
```

#### 4. SSL Certificate Issues
```bash
# Check certificate validity
sudo openssl x509 -in /etc/nginx/ssl/cert.pem -text -noout

# Test certificate
sudo ./scripts/ssl/ssl-setup.sh --test-only

# Regenerate self-signed
sudo ./scripts/ssl/ssl-setup.sh --self-signed
```

### Performance Optimization

#### Database Tuning
```bash
# PostgreSQL settings are optimized in docker-compose.vultr.yml
# Monitor query performance:
docker exec ai_validation_postgres psql -U postgres -d vru_validation_prod -c "
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
"
```

#### Memory Usage
```bash
# Monitor container memory usage
docker stats

# Optimize if needed by adjusting resource limits in docker-compose.vultr.yml
```

## Security Best Practices

### 1. Regular Updates
- Keep system packages updated
- Update Docker images regularly
- Monitor security advisories

### 2. Access Control
- Use strong passwords
- Implement IP whitelisting for admin access
- Regular security audits

### 3. Monitoring
- Monitor failed login attempts
- Set up alerts for unusual activity
- Regular backup verification

### 4. Network Security
- Keep firewall rules minimal
- Use VPN for administrative access
- Monitor network traffic

## Scaling and High Availability

### Horizontal Scaling
To scale for higher load:

1. **Load Balancer**: Add multiple Vultr instances behind a load balancer
2. **Database**: Use managed PostgreSQL service
3. **File Storage**: Use object storage for uploads
4. **Container Orchestration**: Consider Kubernetes for complex scenarios

### Monitoring Scaling
```bash
# Monitor resource usage
docker stats --no-stream

# Check application metrics in Grafana
# Scale services if needed:
docker-compose -f docker-compose.vultr.yml up -d --scale backend=3
```

## Support and Maintenance Contacts

### Emergency Contacts
- **System Administrator**: admin@your-domain.com
- **Security Issues**: security@your-domain.com
- **Monitoring Alerts**: monitoring@your-domain.com

### Maintenance Windows
- **Regular Maintenance**: Sundays 02:00-04:00 UTC
- **Emergency Maintenance**: As needed with notifications

### Documentation Updates
This documentation should be updated whenever:
- Configuration changes are made
- New services are added
- Security procedures change
- Performance optimizations are implemented

## Appendix

### Environment Variable Reference
See `.env.vultr` file for complete configuration options.

### Port Reference
- **80**: HTTP (redirects to HTTPS)
- **443**: HTTPS (main application)
- **5432**: PostgreSQL (localhost only)
- **6379**: Redis (localhost only)
- **8000**: Backend API (localhost only)
- **3000**: Frontend (localhost only)
- **8080**: CVAT (localhost only)
- **9090**: Prometheus (localhost only)
- **3001**: Grafana (localhost only)

### File Locations
- **Application**: `/home/user/Testing/ai-model-validation-platform/`
- **SSL Certificates**: `/etc/nginx/ssl/`
- **Logs**: `/var/log/ai-validation/` and `./logs/`
- **Backups**: `/var/backups/ai-validation/`
- **Configuration**: `./scripts/`

### Useful Commands
```bash
# Service management
./scripts/startup.sh --restart
./scripts/startup.sh --status
./scripts/startup.sh --stop

# SSL management
sudo ./scripts/ssl/ssl-setup.sh --test-only
sudo ./scripts/ssl/ssl-setup.sh -d your-domain.com -e admin@your-domain.com

# Backup management
sudo ./scripts/backup/backup-system.sh
sudo ./scripts/backup/backup-system.sh --verify-only
sudo ./scripts/backup/backup-system.sh --databases-only

# Monitoring
docker-compose -f docker-compose.vultr.yml logs -f [service]
docker-compose -f docker-compose.vultr.yml ps
docker stats
```

---

**Last Updated**: 2024-08-24
**Version**: 1.0
**Deployment**: Vultr Production (155.138.239.131)