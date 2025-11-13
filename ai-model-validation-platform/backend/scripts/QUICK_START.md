# HIL Backend Deployment - Quick Start Guide

## 🚀 5-Minute Deployment

### Prerequisites
```bash
# Verify you have Python 3.8+
python3 --version

# Navigate to backend directory
cd /home/rigade/Testing/ai-model-validation-platform/backend
```

### One-Command Deployment
```bash
./scripts/deploy.sh
```

That's it! The script handles everything automatically.

---

## 📋 What Happens During Deployment?

1. ✅ **Pre-flight checks** - Validates system resources
2. 🗄️ **Database backup** - Creates safety backup
3. 🛑 **Process shutdown** - Gracefully stops old backend
4. 🔓 **Port release** - Frees port 8000
5. 🧹 **Cache clearing** - Removes all `.pyc` and `__pycache__`
6. 🚀 **Backend start** - Launches new process
7. 🏥 **Health checks** - Validates startup
8. ✅ **Smoke tests** - Quick functional tests

**Total Time:** ~30-60 seconds

---

## 🔍 Verify Deployment Success

```bash
# Quick health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","timestamp":"2025-01-04T..."}
```

---

## 📊 Deployment Script Features

### Automatic Process Management
- Graceful SIGTERM shutdown (15s timeout)
- Forced SIGKILL if needed
- PID tracking
- Process verification

### Complete Cache Clearing
- Removes all `.pyc` files
- Removes all `__pycache__` directories
- Recursive search through all subdirectories
- Verification of cleanup

### Port Management
- Automatic detection of port usage
- Force kill blocking processes
- Wait up to 30 seconds for port release
- Verification port is free

### Health Validation
- 10 retry attempts
- 3 second intervals
- Process liveness checks
- HTTP endpoint validation

### Automatic Rollback
- Triggered on any failure
- Database restore from backup
- Cache clearing
- Previous version restart
- Incident report creation

---

## 🛡️ Safety Features

### Database Backups
```bash
# View backups
ls -lh backups/

# Backups are created automatically before each deployment
# Format: db_backup_YYYYMMDD_HHMMSS.db
# Retention: Last 5 backups kept
```

### Rollback on Failure
If deployment fails at any stage:
1. Current process stopped
2. Database restored from backup
3. Python cache cleared
4. System returns to previous state
5. Error logged with details

### Comprehensive Logging
```bash
# View deployment logs
ls -lht logs/deployment_*.log

# View latest deployment
tail -100 logs/deployment_*.log | head -1
```

---

## 🔧 Advanced Usage

### Pre-Deployment Validation
```bash
# Check system readiness before deploying
./scripts/pre-deploy-checks.sh

# Only deploy if checks pass
./scripts/pre-deploy-checks.sh && ./scripts/deploy.sh
```

### Post-Deployment Validation
```bash
# Run comprehensive validation after deployment
./scripts/post-deploy-validation.sh

# Tests include:
# - Process verification
# - Port listening
# - Memory usage
# - Health endpoints
# - API smoke tests
# - Log analysis
# - Response time checks
```

### Manual Rollback
```bash
# Emergency rollback to previous version
./scripts/rollback.sh
```

---

## 🔍 Monitoring & Troubleshooting

### Check Backend Status
```bash
# Is backend running?
ps aux | grep "python3 main.py"

# Is port 8000 listening?
lsof -i :8000

# Check recent logs
tail -50 logs/backend_*.log
```

### Common Issues & Solutions

#### Issue 1: Port Already in Use
```bash
# Kill process using port 8000
lsof -ti:8000 | xargs kill -9

# Then deploy
./scripts/deploy.sh
```

#### Issue 2: Import Errors
```bash
# Clear cache and reinstall dependencies
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} +
pip install -r requirements.txt --force-reinstall

# Deploy
./scripts/deploy.sh
```

#### Issue 3: Database Locked
```bash
# Find and kill processes locking database
lsof dev_database.db
kill -9 <PID>

# Deploy
./scripts/deploy.sh
```

---

## 📈 Systemd Service (Production)

For production environments, use systemd for automatic restarts and better process management.

### Install Service
```bash
# Copy service file
sudo cp scripts/hil-backend.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable hil-backend.service

# Start service
sudo systemctl start hil-backend.service

# Check status
sudo systemctl status hil-backend.service
```

### Manage Service
```bash
# Start
sudo systemctl start hil-backend

# Stop
sudo systemctl stop hil-backend

# Restart (applies updates)
sudo systemctl restart hil-backend

# View logs
sudo journalctl -u hil-backend -f

# Check status
sudo systemctl status hil-backend
```

---

## 📚 Additional Resources

### Scripts Available
- `deploy.sh` - Main deployment script
- `pre-deploy-checks.sh` - Pre-deployment validation
- `post-deploy-validation.sh` - Post-deployment tests
- `rollback.sh` - Emergency rollback

### Documentation
- `README.md` - Script reference
- `deployment-runbook.md` - Complete deployment procedures
- `hil-backend.service` - Systemd service configuration

### Logs & Backups
- `logs/deployment_*.log` - Deployment logs
- `logs/backend_*.log` - Backend application logs
- `logs/rollback_*.log` - Rollback logs
- `backups/db_backup_*.db` - Database backups

---

## 🎯 Deployment Checklist

### Before Deployment
- [ ] Code reviewed and tested
- [ ] Database migrations ready
- [ ] Configuration updated
- [ ] Stakeholders notified
- [ ] Run pre-deployment checks

### During Deployment
- [ ] Execute deployment script
- [ ] Monitor deployment logs
- [ ] Watch for errors

### After Deployment
- [ ] Verify health endpoint
- [ ] Run post-deployment validation
- [ ] Test critical API endpoints
- [ ] Monitor logs for errors
- [ ] Notify stakeholders of success

---

## 🆘 Emergency Contacts

- **System Administrator:** [admin@example.com]
- **Development Team:** [dev-team@example.com]
- **On-Call Engineer:** [oncall@example.com]

---

## 💡 Tips for Success

1. **Always run pre-checks first**
   ```bash
   ./scripts/pre-deploy-checks.sh
   ```

2. **Monitor logs during deployment**
   ```bash
   tail -f logs/deployment_*.log
   ```

3. **Validate after deployment**
   ```bash
   ./scripts/post-deploy-validation.sh
   ```

4. **Keep backups for at least 7 days**
   - Automated in deploy script (keeps last 5)

5. **Use systemd in production**
   - More robust than manual scripts
   - Auto-restart on failure

---

## 🎓 Learn More

For detailed procedures, troubleshooting, and advanced topics, see:
- **[Deployment Runbook](deployment-runbook.md)** - Complete deployment guide
- **[README](README.md)** - Script reference and troubleshooting
- **[Backend Docs](../docs/)** - Architecture and API documentation

---

**Version:** 1.0.0
**Last Updated:** 2025-01-04
**Maintained By:** DevOps Team
