# HIL Backend Deployment Scripts

## Quick Reference

### Essential Commands

```bash
# Full deployment (recommended)
./scripts/deploy.sh

# Pre-deployment validation
./scripts/pre-deploy-checks.sh

# Post-deployment validation
./scripts/post-deploy-validation.sh

# Emergency rollback
./scripts/rollback.sh
```

---

## Script Overview

### 1. deploy.sh - Main Deployment Script

**Purpose:** Production-grade deployment with automatic process management, cache clearing, and health checks.

**Features:**
- ✅ Graceful process shutdown with SIGTERM, then SIGKILL
- ✅ Automatic port 8000 release
- ✅ Complete Python bytecode cache clearing
- ✅ Database backup before deployment
- ✅ Health check validation
- ✅ Smoke tests
- ✅ Automatic rollback on failure
- ✅ Comprehensive logging

**Usage:**
```bash
./scripts/deploy.sh
```

**Exit Codes:**
- `0` - Deployment successful
- `1` - Deployment failed, rollback initiated

**Logs:** `logs/deployment_YYYYMMDD_HHMMSS.log`

---

### 2. pre-deploy-checks.sh - Pre-Deployment Validation

**Purpose:** Comprehensive validation before deployment to prevent failures.

**Checks:**
- System resources (disk, memory, CPU)
- Python version and packages
- Python syntax validation
- File structure and permissions
- Database accessibility
- Port availability
- Network connectivity
- Configuration files

**Usage:**
```bash
./scripts/pre-deploy-checks.sh
```

**Exit Codes:**
- `0` - All checks passed (or warnings only)
- `1` - Critical checks failed

---

### 3. post-deploy-validation.sh - Post-Deployment Testing

**Purpose:** Validate deployment success and system health.

**Tests:**
- Process running verification
- Port listening check
- Memory usage monitoring
- Health endpoint tests
- API smoke tests
- Timing calculator verification
- Log analysis
- Response time checks

**Usage:**
```bash
./scripts/post-deploy-validation.sh
```

**Exit Codes:**
- `0` - All tests passed (or warnings only)
- `1` - Critical tests failed

---

### 4. rollback.sh - Emergency Rollback

**Purpose:** Emergency rollback to previous version.

**Actions:**
- Stop current backend forcefully
- Restore database from backup
- Clear Python cache
- Verify previous version
- Restart with previous version
- Create incident report

**Usage:**
```bash
./scripts/rollback.sh
```

**Exit Codes:**
- `0` - Rollback successful
- `1` - Rollback failed, manual intervention required

**Incident Reports:** `logs/incident_report_YYYYMMDD_HHMMSS.txt`

---

### 5. hil-backend.service - Systemd Service File

**Purpose:** Production service management with systemd.

**Features:**
- Automatic restart on failure
- Graceful shutdown
- Resource limits
- Security hardening
- Journal logging

**Installation:**
```bash
# Copy service file
sudo cp scripts/hil-backend.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable hil-backend.service

# Start service
sudo systemctl start hil-backend.service

# Check status
sudo systemctl status hil-backend.service
```

**Management:**
```bash
# Start service
sudo systemctl start hil-backend

# Stop service
sudo systemctl stop hil-backend

# Restart service
sudo systemctl restart hil-backend

# View logs
sudo journalctl -u hil-backend -f

# Check status
sudo systemctl status hil-backend
```

---

## Deployment Workflows

### Standard Deployment (Manual Script)

```bash
# 1. Run pre-deployment checks
./scripts/pre-deploy-checks.sh

# 2. Deploy if checks pass
./scripts/deploy.sh

# 3. Run post-deployment validation
./scripts/post-deploy-validation.sh

# 4. Monitor logs
tail -f logs/backend_*.log
```

### Systemd Deployment (Production)

```bash
# 1. Run pre-deployment checks
./scripts/pre-deploy-checks.sh

# 2. Restart service
sudo systemctl restart hil-backend

# 3. Check status
sudo systemctl status hil-backend

# 4. Monitor logs
sudo journalctl -u hil-backend -f
```

### Emergency Rollback

```bash
# 1. Execute rollback
./scripts/rollback.sh

# 2. Check status
curl http://localhost:8000/health

# 3. Review incident report
cat logs/incident_report_*.txt

# 4. Investigate root cause
grep -i "error" logs/deployment_*.log
```

---

## Troubleshooting

### Issue: Port 8000 Already in Use

**Solution:**
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9

# Or let deploy script handle it
./scripts/deploy.sh
```

### Issue: Python Import Errors

**Solution:**
```bash
# Clear all cache
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} +

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Deploy
./scripts/deploy.sh
```

### Issue: Database Locked

**Solution:**
```bash
# Check locks
lsof dev_database.db

# Kill locking processes
kill -9 <PID>

# Deploy
./scripts/deploy.sh
```

### Issue: Deployment Script Fails

**Solution:**
```bash
# Check logs
cat logs/deployment_*.log

# Run pre-checks to identify issue
./scripts/pre-deploy-checks.sh

# Fix identified issues

# Retry deployment
./scripts/deploy.sh
```

### Issue: Health Check Timeout

**Solution:**
```bash
# Check if process is running
ps aux | grep python3

# Check logs for errors
tail -100 logs/backend_*.log

# Manually test health
curl -v http://localhost:8000/health

# If needed, rollback
./scripts/rollback.sh
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

### Health Checks

```bash
# Basic health
curl http://localhost:8000/health

# API health
curl http://localhost:8000/api/health

# Database health
curl http://localhost:8000/api/database/health

# All in one
./scripts/post-deploy-validation.sh
```

### Log Management

```bash
# View recent logs
tail -100 logs/backend_*.log

# Search for errors
grep -i "error\|exception" logs/backend_*.log

# View deployment history
ls -lht logs/deployment_*.log

# Clean old logs (keep last 30 days)
find logs/ -name "*.log" -mtime +30 -delete
```

### Backup Management

```bash
# List backups
ls -lht backups/

# Restore specific backup
cp backups/db_backup_YYYYMMDD_HHMMSS.db dev_database.db

# Clean old backups (keep last 10)
ls -t backups/db_backup_*.db | tail -n +11 | xargs -r rm
```

---

## Best Practices

1. **Always run pre-deployment checks first**
   ```bash
   ./scripts/pre-deploy-checks.sh && ./scripts/deploy.sh
   ```

2. **Monitor deployment in real-time**
   ```bash
   # Terminal 1: Deploy
   ./scripts/deploy.sh

   # Terminal 2: Monitor
   tail -f logs/deployment_*.log
   ```

3. **Validate after deployment**
   ```bash
   ./scripts/post-deploy-validation.sh
   ```

4. **Keep backups for 7 days minimum**
   ```bash
   # Automated in deploy.sh (keeps last 5 backups)
   ```

5. **Review logs regularly**
   ```bash
   # Daily
   grep -i "error\|exception" logs/backend_*.log | tail -50
   ```

6. **Use systemd for production**
   ```bash
   # More robust than manual scripts
   sudo systemctl restart hil-backend
   ```

---

## Files Created

- `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/deploy.sh`
- `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/pre-deploy-checks.sh`
- `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/post-deploy-validation.sh`
- `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/rollback.sh`
- `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/hil-backend.service`
- `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/deployment-runbook.md`
- `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/README.md`

---

## Support

For detailed procedures and troubleshooting, see:
- **Deployment Runbook:** `deployment-runbook.md`
- **System Logs:** `logs/`
- **Backup Directory:** `backups/`

---

**Version:** 1.0.0
**Last Updated:** 2025-01-04
