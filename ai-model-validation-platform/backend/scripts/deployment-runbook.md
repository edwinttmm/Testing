# HIL Backend Deployment Runbook

## Overview

This runbook provides comprehensive procedures for deploying, monitoring, and troubleshooting the HIL Backend API service.

**Version:** 1.0.0
**Last Updated:** 2025-01-04
**Target Environment:** Ubuntu Linux / WSL2

---

## Table of Contents

1. [Pre-Deployment](#pre-deployment)
2. [Deployment Procedures](#deployment-procedures)
3. [Post-Deployment Validation](#post-deployment-validation)
4. [Rollback Procedures](#rollback-procedures)
5. [Monitoring & Maintenance](#monitoring--maintenance)
6. [Troubleshooting](#troubleshooting)
7. [Emergency Procedures](#emergency-procedures)

---

## Pre-Deployment

### Prerequisites

- Python 3.8+ installed
- Required system packages (listed in requirements.txt)
- Sufficient disk space (minimum 1GB free)
- Port 8000 available
- Database accessible

### Pre-Deployment Checklist

```bash
# Run automated pre-deployment checks
cd /home/rigade/Testing/ai-model-validation-platform/backend
./scripts/pre-deploy-checks.sh
```

**Manual verification:**

- [ ] All code reviews approved
- [ ] Tests passing in staging environment
- [ ] Database migrations reviewed
- [ ] Configuration changes documented
- [ ] Backup window scheduled
- [ ] Stakeholders notified
- [ ] Rollback plan prepared

### Environment Preparation

```bash
# Ensure scripts are executable
chmod +x scripts/*.sh

# Verify Python environment
python3 --version
python3 -m pip list | grep -E "fastapi|uvicorn|sqlalchemy"

# Check disk space
df -h /home/rigade/Testing/ai-model-validation-platform/backend

# Verify database
sqlite3 dev_database.db "PRAGMA integrity_check;"
```

---

## Deployment Procedures

### Standard Deployment

**Estimated Time:** 2-3 minutes
**Downtime:** ~30 seconds

```bash
# 1. Navigate to backend directory
cd /home/rigade/Testing/ai-model-validation-platform/backend

# 2. Run deployment script
./scripts/deploy.sh
```

**What the script does:**
1. Runs pre-flight checks
2. Creates database backup
3. Stops existing backend gracefully
4. Releases port 8000
5. Clears Python bytecode cache
6. Starts new backend process
7. Performs health checks
8. Runs smoke tests

### Systemd Service Deployment (Recommended for Production)

```bash
# 1. Copy service file to systemd directory
sudo cp scripts/hil-backend.service /etc/systemd/system/

# 2. Reload systemd daemon
sudo systemctl daemon-reload

# 3. Enable service to start on boot
sudo systemctl enable hil-backend.service

# 4. Start the service
sudo systemctl start hil-backend.service

# 5. Verify service status
sudo systemctl status hil-backend.service
```

### Zero-Downtime Deployment (Advanced)

For production environments requiring zero downtime:

```bash
# 1. Start new instance on alternate port
PORT=8001 python3 main.py &

# 2. Wait for health check
sleep 10
curl http://localhost:8001/health

# 3. Update load balancer to point to new instance

# 4. Drain connections from old instance

# 5. Stop old instance
./scripts/deploy.sh
```

---

## Post-Deployment Validation

### Automated Validation

```bash
# Run post-deployment validation suite
./scripts/post-deploy-validation.sh
```

### Manual Validation

**Health Checks:**

```bash
# Basic health check
curl http://localhost:8000/health

# API health check
curl http://localhost:8000/api/health

# Database health check
curl http://localhost:8000/api/database/health
```

**Functional Tests:**

```bash
# Test projects endpoint
curl http://localhost:8000/api/projects

# Test videos endpoint
curl http://localhost:8000/api/videos

# Test test-sessions endpoint
curl http://localhost:8000/api/test-sessions
```

**Log Analysis:**

```bash
# Check recent logs
tail -f logs/backend_*.log

# Search for errors
grep -i "error\|exception" logs/backend_*.log

# Check startup success
grep "Application startup complete" logs/backend_*.log
```

---

## Rollback Procedures

### When to Rollback

Rollback if any of these conditions are met:
- Critical functionality is broken
- Health checks fail after 3 attempts
- Database corruption detected
- Security vulnerability discovered
- Performance degradation > 50%

### Automated Rollback

```bash
# Execute emergency rollback
./scripts/rollback.sh
```

**Rollback performs:**
1. Stops current backend
2. Restores database from backup
3. Clears Python cache
4. Restarts previous version
5. Creates incident report

### Manual Rollback

```bash
# 1. Stop current backend
pkill -f "python3 main.py"

# 2. Restore database backup
cp backups/db_backup_YYYYMMDD_HHMMSS.db dev_database.db

# 3. Clear cache
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} +

# 4. Revert code changes
git checkout <previous-commit-hash>

# 5. Restart backend
python3 main.py &

# 6. Verify health
curl http://localhost:8000/health
```

---

## Monitoring & Maintenance

### Real-Time Monitoring

```bash
# Monitor process
watch -n 2 'ps aux | grep python3'

# Monitor port
watch -n 2 'lsof -i :8000'

# Monitor logs
tail -f logs/backend_*.log

# Monitor resource usage
htop -p $(pgrep -f "python3 main.py")
```

### Health Check Endpoints

- **Main Health:** `GET http://localhost:8000/health`
- **API Health:** `GET http://localhost:8000/api/health`
- **Database Health:** `GET http://localhost:8000/api/database/health`

### Log Files

- **Deployment Logs:** `logs/deployment_*.log`
- **Backend Logs:** `logs/backend_*.log`
- **Rollback Logs:** `logs/rollback_*.log`
- **Incident Reports:** `logs/incident_report_*.txt`

### Periodic Maintenance

**Daily:**
```bash
# Check disk space
df -h

# Review error logs
grep -i "error" logs/backend_*.log | tail -20

# Verify backups exist
ls -lh backups/
```

**Weekly:**
```bash
# Clean old logs (keep last 30 days)
find logs/ -name "*.log" -mtime +30 -delete

# Clean old backups (keep last 10)
ls -t backups/db_backup_*.db | tail -n +11 | xargs -r rm

# Check database integrity
sqlite3 dev_database.db "PRAGMA integrity_check;"
```

**Monthly:**
```bash
# Review and rotate logs
logrotate /etc/logrotate.d/hil-backend

# Update dependencies
pip install -r requirements.txt --upgrade

# Security audit
pip-audit
```

---

## Troubleshooting

### Common Issues

#### Issue: "Address already in use" Error

**Symptom:** Backend fails to start with port binding error

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use deployment script which handles this
./scripts/deploy.sh
```

#### Issue: Import Errors / Module Not Found

**Symptom:** Backend crashes with ImportError

**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Clear Python cache
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} +

# Verify imports
python3 -c "import fastapi, uvicorn, sqlalchemy"
```

#### Issue: Database Locked

**Symptom:** "database is locked" errors

**Solution:**
```bash
# Check database locks
lsof dev_database.db

# Kill processes holding lock
kill <PID>

# If persistent, backup and recreate
cp dev_database.db dev_database.db.backup
sqlite3 dev_database.db "VACUUM;"
```

#### Issue: High Memory Usage

**Symptom:** Backend consuming > 2GB memory

**Solution:**
```bash
# Check memory usage
ps aux | grep python3

# Restart backend
./scripts/deploy.sh

# If persistent, investigate memory leaks
python3 -m memory_profiler main.py
```

#### Issue: Slow API Response Times

**Symptom:** Response times > 5 seconds

**Solution:**
```bash
# Check database size
du -h dev_database.db

# Optimize database
sqlite3 dev_database.db "VACUUM; ANALYZE;"

# Check for slow queries
grep "slow query" logs/backend_*.log

# Consider adding indexes
```

---

## Emergency Procedures

### Complete System Failure

```bash
# 1. Immediate rollback
./scripts/rollback.sh

# 2. If rollback fails, manual recovery
pkill -9 -f "python3 main.py"
cp backups/db_backup_*.db dev_database.db
python3 main.py &

# 3. Notify stakeholders
echo "System recovery initiated at $(date)" | mail -s "HIL Backend Emergency" admin@example.com

# 4. Create incident report
./scripts/create-incident-report.sh
```

### Data Corruption Recovery

```bash
# 1. Stop backend immediately
pkill -9 -f "python3 main.py"

# 2. Backup corrupted database
cp dev_database.db dev_database.db.corrupted

# 3. Restore from last known good backup
cp backups/db_backup_YYYYMMDD_HHMMSS.db dev_database.db

# 4. Verify integrity
sqlite3 dev_database.db "PRAGMA integrity_check;"

# 5. Restart backend
python3 main.py &
```

### Security Incident

```bash
# 1. Isolate system
sudo systemctl stop hil-backend

# 2. Backup evidence
tar -czf /tmp/security-incident-$(date +%Y%m%d).tar.gz logs/ dev_database.db

# 3. Review access logs
grep "suspicious\|unauthorized" logs/*.log

# 4. Reset credentials
# Update .env file with new secrets

# 5. Deploy security patches
git pull origin security-patch
./scripts/deploy.sh
```

---

## Appendix

### Script Locations

- **Deployment:** `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/deploy.sh`
- **Pre-checks:** `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/pre-deploy-checks.sh`
- **Validation:** `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/post-deploy-validation.sh`
- **Rollback:** `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/rollback.sh`

### Contact Information

- **System Administrator:** [admin@example.com]
- **Development Team:** [dev-team@example.com]
- **Emergency Hotline:** [+1-XXX-XXX-XXXX]

### Related Documentation

- [Architecture Documentation](../docs/ARCHITECTURE_REVIEW.md)
- [API Documentation](../docs/API_RESPONSE_STRUCTURE_ANALYSIS.md)
- [Database Schema](../migrations/MULTI_VIDEO_SCHEMA_ANALYSIS_REPORT.md)

---

**Document Control:**
- **Created:** 2025-01-04
- **Author:** DevOps Team
- **Review Cycle:** Quarterly
- **Next Review:** 2025-04-04
