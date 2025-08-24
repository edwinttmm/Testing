# 🔒 Security Deployment Guide for AI Model Validation Platform

## Overview

This guide provides comprehensive instructions for securely deploying the AI Model Validation Platform in production environments. It covers configuration management, security hardening, and best practices.

## 🚨 Critical Security Requirements

### 1. Environment Configuration

#### Required Environment Variables (Production)

```bash
# CRITICAL: Generate secure secrets
AIVALIDATION_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Database (PostgreSQL required for production)
AIVALIDATION_DATABASE_URL="postgresql://username:secure_password@localhost:5432/vru_validation"
DATABASE_SSLMODE=require

# Application Environment
AIVALIDATION_APP_ENVIRONMENT=production
AIVALIDATION_API_DEBUG=false
AIVALIDATION_API_RELOAD=false

# Security Headers
AIVALIDATION_SECURITY_HEADERS_ENABLED=true
AIVALIDATION_HSTS_ENABLED=true
AIVALIDATION_CSP_ENABLED=true

# SSL/TLS (Required for production)
AIVALIDATION_SSL_ENABLED=true
AIVALIDATION_SSL_CERT_FILE=/path/to/certificate.pem
AIVALIDATION_SSL_KEY_FILE=/path/to/private.key
```

#### Environment File Setup

1. **Copy the production template:**
   ```bash
   cp .env.production.template .env.production
   ```

2. **Generate secure secrets:**
   ```bash
   python -c "import secrets; print('AIVALIDATION_SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env.production
   ```

3. **Configure database credentials:**
   ```bash
   # Replace with your actual database credentials
   sed -i 's/username:password/your_user:your_secure_password/' .env.production
   ```

### 2. Database Security

#### PostgreSQL Setup (Required for Production)

```sql
-- Create database and user
CREATE DATABASE vru_validation;
CREATE USER vru_app_user WITH ENCRYPTED PASSWORD 'your_secure_password_here';
GRANT CONNECT ON DATABASE vru_validation TO vru_app_user;
GRANT USAGE ON SCHEMA public TO vru_app_user;
GRANT CREATE ON SCHEMA public TO vru_app_user;
```

#### Database Connection Security

```bash
# Always use SSL in production
DATABASE_SSLMODE=require

# Use connection pooling
AIVALIDATION_DATABASE_POOL_SIZE=20
AIVALIDATION_DATABASE_MAX_OVERFLOW=40
```

### 3. SSL/TLS Configuration

#### Obtain SSL Certificates

**Using Let's Encrypt (Recommended):**

```bash
# Install certbot
sudo apt install certbot

# Obtain certificate
sudo certbot certonly --webroot -w /var/www/html -d yourdomain.com

# Configure in environment
AIVALIDATION_SSL_CERT_FILE=/etc/letsencrypt/live/yourdomain.com/fullchain.pem
AIVALIDATION_SSL_KEY_FILE=/etc/letsencrypt/live/yourdomain.com/privkey.pem
```

**Using self-signed certificates (Development only):**

```bash
# Generate self-signed certificate (NOT for production)
openssl req -x509 -newkey rsa:4096 -keyout private.key -out certificate.pem -days 365 -nodes
```

#### SSL File Permissions

```bash
# Secure certificate permissions
sudo chown root:ssl-cert /etc/letsencrypt/live/yourdomain.com/privkey.pem
sudo chmod 640 /etc/letsencrypt/live/yourdomain.com/privkey.pem

# Allow application user to read certificates
sudo usermod -a -G ssl-cert app_user
```

### 4. Reverse Proxy Configuration

#### Nginx Configuration

Create `/etc/nginx/sites-available/ai-validation`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
    
    # Proxy to FastAPI application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Static files
    location /uploads/ {
        alias /var/uploads/ai-validation/;
        expires 1d;
        add_header Cache-Control "public, immutable";
        
        # Security for uploads
        location ~* \.(php|jsp|asp|sh|py|pl|exe)$ {
            deny all;
        }
    }
}
```

#### Enable Nginx Site

```bash
sudo ln -s /etc/nginx/sites-available/ai-validation /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Firewall Configuration

#### UFW Setup

```bash
# Basic firewall rules
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow from specific IPs only (if applicable)
# sudo ufw allow from 192.168.1.0/24 to any port 8000

sudo ufw --force enable
```

### 6. Application User and Permissions

#### Create Application User

```bash
# Create dedicated user for the application
sudo useradd -r -s /bin/false -d /opt/ai-validation ai-validation
sudo mkdir -p /opt/ai-validation
sudo chown ai-validation:ai-validation /opt/ai-validation

# Create upload directory
sudo mkdir -p /var/uploads/ai-validation
sudo chown ai-validation:ai-validation /var/uploads/ai-validation
sudo chmod 750 /var/uploads/ai-validation
```

#### File Permissions

```bash
# Application files
sudo chown -R ai-validation:ai-validation /opt/ai-validation
sudo chmod -R 755 /opt/ai-validation
sudo chmod 600 /opt/ai-validation/.env.production

# Log files
sudo mkdir -p /var/log/ai-validation
sudo chown ai-validation:ai-validation /var/log/ai-validation
sudo chmod 750 /var/log/ai-validation
```

### 7. Systemd Service Configuration

Create `/etc/systemd/system/ai-validation.service`:

```ini
[Unit]
Description=AI Model Validation Platform
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=exec
User=ai-validation
Group=ai-validation
WorkingDirectory=/opt/ai-validation
Environment=PATH=/opt/ai-validation/venv/bin
EnvironmentFile=/opt/ai-validation/.env.production
ExecStart=/opt/ai-validation/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StartLimitInterval=0

# Security
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/var/log/ai-validation /var/uploads/ai-validation
CapabilityBoundingSet=
SystemCallArchitectures=native
SystemCallFilter=@system-service
SystemCallFilter=~@privileged @resources @obsolete

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-validation
sudo systemctl start ai-validation
sudo systemctl status ai-validation
```

### 8. Monitoring and Logging

#### Log Rotation

Create `/etc/logrotate.d/ai-validation`:

```
/var/log/ai-validation/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 ai-validation ai-validation
    postrotate
        systemctl reload ai-validation
    endscript
}
```

#### Health Check Endpoint

The application provides a health check endpoint at `/health`:

```bash
# Check application health
curl -f https://yourdomain.com/health || echo "Application unhealthy"
```

#### Monitoring Script

Create `/usr/local/bin/ai-validation-monitor.sh`:

```bash
#!/bin/bash

# Monitor AI Validation Platform
LOG_FILE="/var/log/ai-validation/monitor.log"
HEALTH_URL="https://localhost/health"

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Check if service is running
if ! systemctl is-active --quiet ai-validation; then
    log_message "ERROR: ai-validation service is not running"
    systemctl restart ai-validation
    exit 1
fi

# Check health endpoint
if ! curl -f -s "$HEALTH_URL" > /dev/null; then
    log_message "WARNING: Health check failed"
    exit 1
fi

log_message "INFO: Health check passed"
```

#### Cron Job for Monitoring

```bash
# Add to crontab
echo "*/5 * * * * /usr/local/bin/ai-validation-monitor.sh" | sudo crontab -u root -
```

### 9. Security Validation

#### Pre-deployment Security Check

```bash
# Run security validation
cd /opt/ai-validation
python security_validator.py --strict

# Generate security report
python security_validator.py --report > security_report.json
```

#### Regular Security Audits

```bash
# Create weekly security audit script
cat > /usr/local/bin/ai-validation-security-audit.sh << 'EOF'
#!/bin/bash
cd /opt/ai-validation
python security_validator.py --report > "/var/log/ai-validation/security_audit_$(date +%Y%m%d).json"
EOF

chmod +x /usr/local/bin/ai-validation-security-audit.sh

# Add to weekly cron
echo "0 2 * * 0 /usr/local/bin/ai-validation-security-audit.sh" | sudo crontab -u root -
```

### 10. Backup and Recovery

#### Database Backup

```bash
# Create backup script
cat > /usr/local/bin/ai-validation-backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/ai-validation"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Database backup
pg_dump vru_validation > "$BACKUP_DIR/database_$DATE.sql"

# Compress and encrypt
gpg --cipher-algo AES256 --compress-algo 1 --s2k-mode 3 \
    --s2k-digest-algo SHA512 --s2k-count 65536 --symmetric \
    --output "$BACKUP_DIR/database_$DATE.sql.gpg" \
    "$BACKUP_DIR/database_$DATE.sql"

rm "$BACKUP_DIR/database_$DATE.sql"

# Remove old backups (keep 30 days)
find "$BACKUP_DIR" -name "database_*.sql.gpg" -mtime +30 -delete
EOF

chmod +x /usr/local/bin/ai-validation-backup.sh

# Daily backup at 3 AM
echo "0 3 * * * /usr/local/bin/ai-validation-backup.sh" | sudo crontab -u root -
```

### 11. Docker Production Deployment

#### Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgresql.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    networks:
      - internal
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    networks:
      - internal
    restart: unless-stopped

  backend:
    build: 
      context: ./backend
      dockerfile: Dockerfile.prod
    environment:
      - AIVALIDATION_SECRET_KEY=${AIVALIDATION_SECRET_KEY}
      - AIVALIDATION_DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - AIVALIDATION_REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      - AIVALIDATION_APP_ENVIRONMENT=production
      - AIVALIDATION_API_DEBUG=false
      - AIVALIDATION_SECURITY_HEADERS_ENABLED=true
      - AIVALIDATION_HSTS_ENABLED=true
    depends_on:
      - postgres
      - redis
    volumes:
      - uploaded_videos:/app/uploads:rw
      - ./ssl:/app/ssl:ro
    networks:
      - internal
      - web
    restart: unless-stopped
    user: "1000:1000"  # Non-root user

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl/certs:ro
      - uploaded_videos:/var/www/uploads:ro
    depends_on:
      - backend
    networks:
      - web
    restart: unless-stopped

volumes:
  postgres_data:
  uploaded_videos:

networks:
  internal:
    driver: bridge
  web:
    driver: bridge
```

#### Production Dockerfile

Create `backend/Dockerfile.prod`:

```dockerfile
FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Security: Set ownership and permissions
RUN chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod 600 /app/.env.production

# Create directories for uploads and logs
RUN mkdir -p /app/uploads /app/logs && \
    chown appuser:appuser /app/uploads /app/logs

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 12. Security Checklist

#### Pre-deployment Checklist

- [ ] Secure secret keys generated and configured
- [ ] Database using PostgreSQL with SSL
- [ ] SSL/TLS certificates obtained and configured
- [ ] Security headers enabled
- [ ] CORS properly configured for production domains
- [ ] Debug mode disabled
- [ ] File upload restrictions in place
- [ ] Logging configured with appropriate levels
- [ ] Firewall rules configured
- [ ] Application running as non-root user
- [ ] Regular backups configured
- [ ] Monitoring and alerts configured
- [ ] Security validation passes

#### Post-deployment Checklist

- [ ] SSL certificate expiration monitoring
- [ ] Log rotation working
- [ ] Health checks responding
- [ ] Database backups running
- [ ] Security audits scheduled
- [ ] Performance monitoring active
- [ ] Error alerting configured

### 13. Troubleshooting

#### Common Issues

**SSL Certificate Issues:**
```bash
# Check certificate validity
openssl x509 -in /etc/letsencrypt/live/yourdomain.com/cert.pem -text -noout

# Test SSL configuration
openssl s_client -connect yourdomain.com:443
```

**Database Connection Issues:**
```bash
# Test database connection
psql -h localhost -U vru_app_user -d vru_validation -c "SELECT 1;"

# Check database logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

**Application Logs:**
```bash
# Check application logs
sudo tail -f /var/log/ai-validation/app.log

# Check security logs
sudo tail -f /var/log/ai-validation/app_security.log

# Check systemd logs
sudo journalctl -u ai-validation -f
```

### 14. Contact and Support

For security issues or questions about this deployment guide:

- Create an issue in the project repository
- Email: security@yourdomain.com (replace with actual contact)
- Security advisories: Follow responsible disclosure practices

---

**⚠️ Security Notice**: This guide provides general security recommendations. Always perform your own security assessment and adapt configurations to your specific environment and requirements.

**📅 Last Updated**: 2025-08-24  
**🔄 Version**: 1.0.0