# Firewall and Security Configuration Guide
## AI Model Validation Platform - Vultr Production Environment

This document outlines comprehensive firewall and security configurations for the AI Model Validation Platform deployed on Vultr server (155.138.239.131).

## Table of Contents
- [Firewall Configuration](#firewall-configuration)
- [Security Hardening](#security-hardening)
- [Network Security](#network-security)
- [Application Security](#application-security)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Incident Response](#incident-response)

## Firewall Configuration

### UFW (Uncomplicated Firewall) Setup

#### Initial Configuration
```bash
# Install UFW if not present
sudo apt update && sudo apt install ufw

# Reset to clean state
sudo ufw --force reset

# Set default policies (CRITICAL)
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Enable logging
sudo ufw logging on
```

#### SSH Access (CRITICAL - Don't Lock Yourself Out!)
```bash
# Allow SSH before enabling firewall
sudo ufw allow ssh
sudo ufw allow 22/tcp

# Rate limiting for SSH (prevent brute force)
sudo ufw limit ssh

# Optional: Restrict SSH to specific IPs
sudo ufw allow from YOUR_OFFICE_IP to any port 22
sudo ufw allow from YOUR_HOME_IP to any port 22
```

#### Web Traffic
```bash
# Allow HTTP (will redirect to HTTPS)
sudo ufw allow 80/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Optional: Block direct access to specific countries
# sudo ufw deny from COUNTRY_IP_RANGE
```

#### Docker Network Access
```bash
# Allow Docker internal network
sudo ufw allow from 172.21.0.0/16

# Allow Docker bridge network
sudo ufw allow from 172.17.0.0/16
```

#### Database and Service Access (Localhost Only)
```bash
# PostgreSQL - localhost only (already bound to 127.0.0.1)
# sudo ufw allow from 127.0.0.1 to any port 5432

# Redis - localhost only (already bound to 127.0.0.1)
# sudo ufw allow from 127.0.0.1 to any port 6379

# Backend API - localhost only (proxied through Nginx)
# sudo ufw allow from 127.0.0.1 to any port 8000
```

#### Monitoring Services (Restricted)
```bash
# Prometheus - localhost only
sudo ufw allow from 127.0.0.1 to any port 9090

# Grafana - localhost only
sudo ufw allow from 127.0.0.1 to any port 3001

# Loki - localhost only
sudo ufw allow from 127.0.0.1 to any port 3100

# Optional: Allow monitoring from specific IPs
# sudo ufw allow from MONITORING_SERVER_IP to any port 9090
# sudo ufw allow from ADMIN_IP to any port 3001
```

#### Enable Firewall
```bash
# Enable UFW (double-check SSH access first!)
sudo ufw --force enable

# Check status
sudo ufw status verbose
sudo ufw status numbered
```

### Advanced UFW Rules

#### Rate Limiting
```bash
# SSH rate limiting (already applied above)
sudo ufw limit ssh

# HTTP rate limiting (additional protection)
sudo ufw limit 80/tcp

# HTTPS rate limiting
sudo ufw limit 443/tcp
```

#### Specific IP Management
```bash
# Allow specific trusted IPs full access
sudo ufw allow from TRUSTED_IP_1
sudo ufw allow from TRUSTED_IP_2

# Block known malicious IPs
sudo ufw deny from MALICIOUS_IP_1
sudo ufw deny from MALICIOUS_IP_2

# Allow IP ranges (e.g., office network)
sudo ufw allow from 192.168.1.0/24
```

#### Service-Specific Rules
```bash
# Allow only specific IPs to access admin interfaces
sudo ufw allow from ADMIN_IP to any port 3001  # Grafana
sudo ufw allow from ADMIN_IP to any port 9090  # Prometheus

# CVAT access (if needed externally)
sudo ufw allow from TRUSTED_NETWORK to any port 8080
```

### Fail2Ban Configuration

#### Installation
```bash
sudo apt install fail2ban

# Create local configuration
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
```

#### Configuration
```bash
sudo nano /etc/fail2ban/jail.local
```

Add/modify the following sections:

```ini
[DEFAULT]
# Ban time in seconds (1 hour)
bantime = 3600

# Time window for finding failures
findtime = 600

# Number of failures before ban
maxretry = 3

# Action to take
action = %(action_mwl)s

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
logpath = /var/log/nginx/error.log
maxretry = 3
bantime = 3600

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 3
bantime = 3600

[nginx-botsearch]
enabled = true
filter = nginx-botsearch
logpath = /var/log/nginx/access.log
maxretry = 3
bantime = 3600
```

#### Custom Filters
```bash
# Create custom filter for API abuse
sudo nano /etc/fail2ban/filter.d/nginx-api-abuse.conf
```

```ini
[Definition]
failregex = ^<HOST> - .* "(GET|POST|PUT|DELETE) /api/.*" (4[0-9]{2}|5[0-9]{2}) .*$
ignoreregex =
```

#### Start Fail2Ban
```bash
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Check status
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

## Security Hardening

### System Hardening

#### Disable Unused Services
```bash
# List running services
sudo systemctl list-unit-files --state=enabled

# Disable unnecessary services (example)
sudo systemctl disable telnet
sudo systemctl disable rsh
sudo systemctl disable finger

# Remove unnecessary packages
sudo apt purge telnetd rsh-server finger
```

#### SSH Hardening
```bash
sudo nano /etc/ssh/sshd_config
```

Add/modify these settings:
```bash
# Change default port (optional)
# Port 2222

# Disable root login
PermitRootLogin no

# Disable password authentication (use keys only)
PasswordAuthentication no
PubkeyAuthentication yes

# Limit users
AllowUsers your-username

# Disable X11 forwarding
X11Forwarding no

# Disable empty passwords
PermitEmptyPasswords no

# Set login timeout
LoginGraceTime 30

# Maximum authentication attempts
MaxAuthTries 3

# Maximum sessions
MaxSessions 2

# Protocol version
Protocol 2

# Client alive settings
ClientAliveInterval 300
ClientAliveCountMax 2
```

Restart SSH:
```bash
sudo systemctl restart ssh
```

#### File System Hardening
```bash
# Set proper file permissions
sudo chmod 644 /etc/passwd
sudo chmod 000 /etc/shadow
sudo chmod 644 /etc/group

# Secure temporary directories
sudo chmod 1777 /tmp
sudo chmod 1777 /var/tmp

# Disable core dumps
echo "* hard core 0" | sudo tee -a /etc/security/limits.conf
```

### Application Security

#### Docker Security
```bash
# Run containers as non-root user
# (Already configured in docker-compose.vultr.yml)

# Use read-only file systems where possible
# (Implemented in docker-compose.vultr.yml)

# Limit container resources
# (CPU and memory limits set in docker-compose.vultr.yml)

# Regular security scanning
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd):/app \
  aquasec/trivy:latest image ai_validation_backend
```

#### Database Security
```bash
# PostgreSQL security (configured in docker-compose.vultr.yml)
# - Strong passwords
# - Limited connections
# - Proper user permissions
# - SSL connections (internal)

# Redis security
# - Password authentication
# - Command renaming
# - Memory limits
# - Bind to specific interfaces
```

#### SSL/TLS Security
Certificate security is handled by the SSL setup script:
- Strong cipher suites
- Perfect Forward Secrecy
- HSTS headers
- Certificate pinning (optional)

### Environment Security

#### Environment Variables
```bash
# Secure environment file permissions
chmod 600 .env.vultr
chown root:root .env.vultr

# Never commit secrets to version control
echo ".env.vultr" >> .gitignore
```

#### Secrets Management
```bash
# Generate secure passwords
openssl rand -base64 32  # For secret keys
openssl rand -base64 16  # For passwords

# Store secrets securely
# Consider using Docker secrets or external secret management
```

## Network Security

### Network Segmentation
The Docker network configuration provides isolation:
- External traffic → Nginx → Application services
- Database services only accessible internally
- Monitoring services restricted to localhost

### DDoS Protection

#### Rate Limiting (Nginx)
Already configured in nginx.conf:
```nginx
# API rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=1r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit_per_ip:10m;
```

#### Connection Limits
```nginx
# Connection limiting
limit_conn conn_limit_per_ip 10;
```

### Intrusion Detection

#### Log Monitoring
```bash
# Monitor authentication logs
sudo tail -f /var/log/auth.log

# Monitor nginx access logs
sudo tail -f /var/log/nginx/access.log

# Monitor for suspicious activity
sudo grep "Failed password" /var/log/auth.log
sudo grep "Invalid user" /var/log/auth.log
```

#### Automated Alerting
Configure monitoring alerts for:
- Multiple failed login attempts
- Unusual traffic patterns
- High error rates
- Suspicious user agents

## Monitoring and Alerting

### Security Monitoring

#### Log Analysis with Loki
Promtail configuration includes security-relevant logs:
- Authentication attempts
- Nginx access/error logs
- Application security events
- System security logs

#### Prometheus Alerting Rules
Create security alert rules:

```yaml
# /scripts/monitoring/alert_rules.yml
groups:
- name: security_alerts
  rules:
  - alert: HighErrorRate
    expr: rate(nginx_http_requests_total{status=~"4.."}[5m]) > 10
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High 4xx error rate detected"
      
  - alert: SuspiciousTraffic
    expr: rate(nginx_http_requests_total[1m]) > 100
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Possible DDoS attack detected"
      
  - alert: SSLCertificateExpiry
    expr: (probe_ssl_earliest_cert_expiry - time()) / 86400 < 7
    for: 0m
    labels:
      severity: warning
    annotations:
      summary: "SSL certificate expires in less than 7 days"
```

### Health Monitoring

#### System Health
Monitor key system metrics:
- CPU usage
- Memory usage
- Disk usage
- Network traffic
- SSL certificate expiration

#### Application Health
- Service availability
- Response times
- Error rates
- Database performance

## Incident Response

### Security Incident Procedures

#### Immediate Response
1. **Identify the incident**
   - Monitor alerts
   - Check logs
   - Assess impact

2. **Contain the threat**
   ```bash
   # Block malicious IP immediately
   sudo ufw deny from MALICIOUS_IP
   
   # Stop compromised service
   docker-compose -f docker-compose.vultr.yml stop [service]
   ```

3. **Investigate**
   ```bash
   # Check logs
   sudo journalctl -u docker
   docker-compose -f docker-compose.vultr.yml logs [service]
   
   # Check fail2ban
   sudo fail2ban-client status
   
   # Check UFW logs
   sudo tail -f /var/log/ufw.log
   ```

#### Recovery Procedures
1. **Restore from backup** (if needed)
   ```bash
   sudo ./scripts/backup/backup-system.sh --restore-help
   ```

2. **Update security measures**
   - Patch vulnerabilities
   - Update firewall rules
   - Change compromised credentials

3. **Monitor for re-occurrence**
   - Enhanced logging
   - Additional monitoring
   - Regular security scans

### Emergency Contacts
- **System Administrator**: admin@your-domain.com
- **Security Team**: security@your-domain.com
- **Vultr Support**: support@vultr.com

### Backup Security Measures

#### Offline Access
Prepare for emergency access:
- Backup SSH keys
- Alternative access methods
- Emergency contact procedures

#### Disaster Recovery
- Regular backup verification
- Documented recovery procedures
- Alternative deployment locations

## Security Maintenance

### Regular Tasks

#### Daily
- Monitor security alerts
- Check fail2ban logs
- Review access logs

#### Weekly
- Update system packages
- Review firewall rules
- Check SSL certificate status

#### Monthly
- Security audit
- Password rotation (if needed)
- Backup integrity verification
- Vulnerability scanning

### Security Scanning

#### Automated Scanning
```bash
# System vulnerability scan
sudo apt install unattended-upgrades apt-listchanges

# Configure automatic security updates
sudo dpkg-reconfigure unattended-upgrades
```

#### Manual Security Audit
```bash
# Check for security updates
sudo apt list --upgradable

# Scan for malware (optional)
sudo apt install clamav
sudo freshclam
sudo clamscan -r /home

# Check for rootkits
sudo apt install chkrootkit rkhunter
sudo chkrootkit
sudo rkhunter --check
```

### Compliance and Documentation

#### Security Documentation
- Maintain security procedure documentation
- Document all security changes
- Keep incident response logs
- Regular security policy reviews

#### Compliance Requirements
- Data protection requirements
- Industry-specific standards
- Regular compliance audits
- Security training requirements

## Testing Security Configuration

### Penetration Testing
```bash
# Test firewall rules
nmap -sS -p 1-1000 155.138.239.131

# Test web application security
nikto -h https://155.138.239.131

# Test SSL configuration
sslscan 155.138.239.131:443
```

### Security Validation
```bash
# Verify UFW status
sudo ufw status verbose

# Check fail2ban
sudo fail2ban-client status

# Verify SSL certificate
openssl s_client -connect 155.138.239.131:443

# Test rate limiting
curl -I https://155.138.239.131/api/health
```

---

**Security Note**: This configuration provides defense-in-depth security for the AI Model Validation Platform. Regular updates and monitoring are essential for maintaining security posture.

**Last Updated**: 2024-08-24  
**Version**: 1.0  
**Environment**: Vultr Production (155.138.239.131)