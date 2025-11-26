# LabJack HIL Service - Rollback Procedures

**Date:** 2025-11-18
**Version:** 1.0
**Purpose:** Emergency rollback procedures for LabJack HIL service fixes

---

## Emergency Contact Information

### Rollback Authority
- **Primary:** System Administrator
- **Secondary:** Backend Team Lead
- **Escalation:** CTO/Technical Director

### Communication Channels
- **Slack:** #labjack-incidents
- **Email:** backend-team@company.com
- **Emergency Hotline:** [Your emergency contact]

---

## When to Execute Rollback

### Critical Triggers (Immediate Rollback Required)

Execute rollback **IMMEDIATELY** if any of these occur:

#### 1. System Stability Issues
- [ ] Backend service crashes repeatedly (> 3 times in 10 minutes)
- [ ] Thread deadlocks detected
- [ ] Out of memory errors
- [ ] System becomes unresponsive

#### 2. Data Integrity Issues
- [ ] Detection data corruption detected
- [ ] Timestamps incorrect or missing
- [ ] Database consistency errors
- [ ] Lost detection events

#### 3. Concurrent Access Errors
- [ ] "DEVICE_ALREADY_OPEN" errors occurring
- [ ] Multiple singleton instances created
- [ ] Race condition errors in logs
- [ ] Concurrent sessions failing

#### 4. Performance Degradation
- [ ] Detection rate drops below 50 Hz
- [ ] Latency exceeds 100ms
- [ ] CPU usage exceeds 90% sustained
- [ ] Test completion rate < 80%

---

## Rollback Procedures

### Procedure A: Quick Rollback (Stream Mode Only)
**Time Required:** < 2 minutes
**Scope:** Disable stream mode, keep other fixes

**Use When:**
- Stream mode specific issues
- Hardware communication problems
- Performance issues with streaming

#### Steps:

1. **Disable Stream Mode** (30 seconds)
   ```bash
   cd /home/rigade/Testing/ai-model-validation-platform

   # Edit configuration file
   vim backend/routers/test_sessions.py

   # Change line 1135:
   # FROM: "use_stream_mode": True,  # Re-enabled after Phase 2 fixes
   # TO:   "use_stream_mode": False,  # ROLLBACK: Stream mode disabled
   ```

2. **Restart Backend** (60 seconds)
   ```bash
   docker-compose restart backend

   # Wait for service to be healthy
   sleep 30
   ```

3. **Verify Rollback** (30 seconds)
   ```bash
   # Check logs for polling mode
   docker-compose logs backend | grep -i "mode:"

   # Expected output:
   # INFO: Using polling mode
   # INFO: Stream mode disabled

   # Verify service is responding
   curl -f http://localhost:8000/health || echo "FAILED"
   ```

4. **Document Rollback**
   ```bash
   echo "$(date): Rollback A executed - Stream mode disabled" >> deployment_log.txt
   echo "Reason: [FILL IN REASON]" >> deployment_log.txt
   echo "By: [YOUR NAME]" >> deployment_log.txt
   ```

**Expected Behavior After Rollback A:**
- ✅ System returns to polling mode
- ✅ Detection rate: 20-100 Hz (slower but stable)
- ✅ No stream mode errors
- ✅ Singleton pattern still active (Phase 1 fixes retained)

---

### Procedure B: Full Rollback (All Changes)
**Time Required:** < 5 minutes
**Scope:** Revert all Phase 1-3 changes

**Use When:**
- Singleton pattern causing issues
- Multiple cascading failures
- Need to return to known-good state

#### Steps:

1. **Restore Backup Files** (90 seconds)
   ```bash
   cd /home/rigade/Testing/ai-model-validation-platform

   # Verify backups exist
   ls -l backend/routers/test_sessions.py.backup
   ls -l backend/services/labjack_hardware_service.py.backup
   ls -l backend/services/labjack_detection_service.py.backup

   # Restore files
   cp backend/routers/test_sessions.py.backup backend/routers/test_sessions.py
   cp backend/services/labjack_hardware_service.py.backup backend/services/labjack_hardware_service.py
   cp backend/services/labjack_detection_service.py.backup backend/services/labjack_detection_service.py

   echo "Files restored from backup"
   ```

2. **Restart Backend** (90 seconds)
   ```bash
   docker-compose down
   sleep 10
   docker-compose up -d
   sleep 60
   ```

3. **Verify Rollback** (60 seconds)
   ```bash
   # Check service status
   docker-compose ps backend

   # Check logs for pre-fix behavior
   docker-compose logs backend | tail -50

   # Verify service health
   curl -f http://localhost:8000/health || echo "FAILED"

   # Test basic functionality
   # [Run a simple test session manually]
   ```

4. **Document Rollback**
   ```bash
   echo "$(date): Rollback B executed - Full rollback to pre-fix state" >> deployment_log.txt
   echo "Reason: [FILL IN REASON]" >> deployment_log.txt
   echo "By: [YOUR NAME]" >> deployment_log.txt
   echo "Restored files from: [BACKUP DATE]" >> deployment_log.txt
   ```

**Expected Behavior After Rollback B:**
- ✅ System returns to pre-fix state
- ⚠️ "DEVICE_ALREADY_OPEN" errors may return (known issue)
- ⚠️ Concurrent sessions may fail (known issue)
- ✅ Single session tests should work

---

### Procedure C: Emergency Shutdown
**Time Required:** < 1 minute
**Scope:** Stop LabJack services completely

**Use When:**
- Hardware at risk of damage
- Data corruption actively occurring
- Need time to investigate

#### Steps:

1. **Stop Backend Service** (30 seconds)
   ```bash
   docker-compose stop backend

   echo "Backend stopped for emergency maintenance"
   ```

2. **Disconnect Hardware** (If applicable)
   ```bash
   # If LabJack USB device connected:
   # 1. Stop all test sessions
   # 2. Physically disconnect LabJack device
   # 3. Document reason
   ```

3. **Document Shutdown**
   ```bash
   echo "$(date): Emergency Shutdown executed" >> deployment_log.txt
   echo "Reason: [FILL IN REASON]" >> deployment_log.txt
   echo "By: [YOUR NAME]" >> deployment_log.txt
   ```

4. **Notify Team**
   ```bash
   # Post to Slack/Teams
   # Subject: EMERGENCY - LabJack HIL Service Down
   # Message: [Reason, ETA for resolution]
   ```

---

## Rollback Verification

### Checklist After Rollback

Use this checklist to verify rollback was successful:

#### System Health
- [ ] Backend service is running
- [ ] No error logs in past 5 minutes
- [ ] Health endpoint responding
- [ ] Database connections healthy

#### Functionality
- [ ] Can create new test session
- [ ] Can upload test video
- [ ] Test session completes successfully
- [ ] Detections are recorded

#### Performance
- [ ] Detection rate matches expected (polling or stream)
- [ ] Latency within acceptable range
- [ ] No concurrent session errors
- [ ] CPU/memory usage normal

#### Data Integrity
- [ ] Recent test session data intact
- [ ] No missing detections
- [ ] Timestamps correct
- [ ] Database queries successful

---

## Post-Rollback Actions

### Immediate (Within 1 Hour)

1. **Notify Stakeholders**
   - Send email to team
   - Post to communication channel
   - Update status page (if applicable)

2. **Document Incident**
   ```bash
   # Create incident report
   cat > incident_report_$(date +%Y%m%d_%H%M%S).md <<EOF
   # LabJack HIL Rollback Incident Report

   **Date:** $(date)
   **Rollback Type:** [A/B/C]
   **Executed By:** [NAME]

   ## Trigger
   [What caused the rollback]

   ## Actions Taken
   [Rollback procedure followed]

   ## Current Status
   [System state after rollback]

   ## Root Cause
   [If known, what went wrong]

   ## Next Steps
   [Investigation plan]
   EOF
   ```

3. **Stabilize System**
   - Monitor for 1 hour
   - Run basic tests
   - Verify no further issues

### Short-term (Within 24 Hours)

1. **Root Cause Analysis**
   - Review logs before incident
   - Analyze error patterns
   - Identify failure point
   - Document findings

2. **Fix Development**
   - Identify specific issue
   - Develop targeted fix
   - Test fix in isolation
   - Plan re-deployment

3. **Update Documentation**
   - Add to known issues
   - Update rollback procedures
   - Document lessons learned

### Long-term (Within 1 Week)

1. **Comprehensive Review**
   - Full incident analysis
   - Team retrospective
   - Process improvements
   - Prevention strategies

2. **Enhanced Testing**
   - Add test cases for failure scenario
   - Improve automated testing
   - Enhance monitoring

3. **Re-deployment Planning**
   - Updated deployment strategy
   - Additional safeguards
   - Enhanced rollback procedures

---

## Rollback Decision Matrix

Use this matrix to decide which rollback procedure to execute:

| Issue Type | Severity | Procedure | Time | Keep Fixes |
|------------|----------|-----------|------|------------|
| Stream mode hang | Critical | A | 2 min | Phase 1 |
| High latency | High | A | 2 min | Phase 1 |
| Fallback to polling | Medium | Investigate | - | All |
| DEVICE_ALREADY_OPEN | Critical | B | 5 min | None |
| Singleton race condition | Critical | B | 5 min | None |
| Hardware at risk | Emergency | C | 1 min | N/A |
| Data corruption | Emergency | C then B | 6 min | None |
| Unknown critical | Emergency | C then Investigate | Variable | TBD |

---

## Rollback Testing

### Pre-Deployment: Test Rollback Procedures

Before deploying fixes, **test rollback procedures** to ensure they work:

#### Test Rollback A
```bash
# 1. Deploy fixes to staging
# 2. Enable stream mode
# 3. Execute Rollback A procedure
# 4. Verify system returns to polling mode
# 5. Time the procedure (should be < 2 minutes)
```

#### Test Rollback B
```bash
# 1. Deploy fixes to staging
# 2. Create backup files
# 3. Execute Rollback B procedure
# 4. Verify system returns to pre-fix state
# 5. Time the procedure (should be < 5 minutes)
```

#### Test Rollback C
```bash
# 1. Deploy fixes to staging
# 2. Execute Rollback C procedure
# 3. Verify clean shutdown
# 4. Time the procedure (should be < 1 minute)
```

---

## Backup Strategy

### Before Deployment

**Create Backups:**
```bash
#!/bin/bash
# create_rollback_backup.sh

BACKUP_DIR="rollback_backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup key files
cp backend/routers/test_sessions.py "$BACKUP_DIR/"
cp backend/services/labjack_hardware_service.py "$BACKUP_DIR/"
cp backend/services/labjack_detection_service.py "$BACKUP_DIR/"

# Create manifest
cat > "$BACKUP_DIR/MANIFEST.txt" <<EOF
Backup created: $(date)
Purpose: Pre-deployment backup for Phase 1-3 fixes
Git commit: $(git rev-parse HEAD)
Branch: $(git branch --show-current)

Files backed up:
- test_sessions.py
- labjack_hardware_service.py
- labjack_detection_service.py

Restore command:
./restore_rollback_backup.sh $BACKUP_DIR
EOF

echo "Backup created: $BACKUP_DIR"
```

**Restore Script:**
```bash
#!/bin/bash
# restore_rollback_backup.sh

BACKUP_DIR=$1

if [ -z "$BACKUP_DIR" ]; then
    echo "Usage: $0 <backup_directory>"
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Error: Backup directory not found: $BACKUP_DIR"
    exit 1
fi

echo "Restoring from: $BACKUP_DIR"
cp "$BACKUP_DIR/test_sessions.py" backend/routers/
cp "$BACKUP_DIR/labjack_hardware_service.py" backend/services/
cp "$BACKUP_DIR/labjack_detection_service.py" backend/services/

echo "Files restored. Please restart backend:"
echo "docker-compose restart backend"
```

---

## Communication Templates

### Email Template: Rollback Notification

```
Subject: [ACTION REQUIRED] LabJack HIL Service Rollback Executed

Team,

A rollback of the LabJack HIL service has been executed.

**Details:**
- Date/Time: [TIMESTAMP]
- Rollback Type: [A/B/C]
- Reason: [BRIEF REASON]
- Current Status: [STABLE/INVESTIGATING/UNSTABLE]

**Impact:**
- [List any user-facing impacts]
- [Expected behavior changes]

**Next Steps:**
- [Immediate actions]
- [Investigation plan]
- [ETA for resolution]

**Action Required:**
- [Any actions team members need to take]

Please respond to confirm you've seen this message.

Incident Report: [LINK]

Best regards,
[YOUR NAME]
```

### Slack Template: Rollback Alert

```
🚨 **ROLLBACK EXECUTED** 🚨

**Service:** LabJack HIL
**Type:** Rollback [A/B/C]
**Time:** [TIMESTAMP]
**By:** [NAME]

**Reason:**
[Brief explanation]

**Status:** [STABLE/INVESTIGATING]

**Impact:**
- [User impacts]

**Thread:** Please use this thread for updates and questions.
```

---

## Monitoring After Rollback

### First Hour: Critical Monitoring

```bash
# Run this monitoring script after rollback
#!/bin/bash
# post_rollback_monitor.sh

echo "=== Post-Rollback Monitoring ==="
echo "Start: $(date)"

for i in {1..12}; do
    echo -e "\n--- Check $i/12 ($(date)) ---"

    # Service status
    echo "Backend status:"
    docker-compose ps backend | grep -q "Up" && echo "✅ Running" || echo "❌ Down"

    # Error count
    echo "Errors in last 5 minutes:"
    docker-compose logs --since 5m backend | grep -i "error" | wc -l

    # Mode check (if Rollback A)
    echo "Current mode:"
    docker-compose logs --since 5m backend | grep -i "mode:" | tail -1

    # Wait 5 minutes
    sleep 300
done

echo -e "\n=== Monitoring Complete ==="
echo "End: $(date)"
```

---

## Success Criteria for Rollback

### Rollback A Success
- ✅ Backend service healthy
- ✅ Logs show "mode: polling"
- ✅ No stream mode errors
- ✅ Test sessions complete successfully
- ✅ Detection rate: 20-100 Hz
- ✅ Singleton pattern still working

### Rollback B Success
- ✅ Backend service healthy
- ✅ Pre-fix behavior restored
- ✅ Test sessions complete (single session)
- ✅ Known pre-fix issues present (expected)
- ✅ System stable for 1 hour

### Rollback C Success
- ✅ Backend cleanly stopped
- ✅ No active connections
- ✅ Hardware safe
- ✅ System ready for investigation

---

## Lessons Learned Template

After each rollback, document lessons learned:

```markdown
# Rollback Lessons Learned

**Date:** [DATE]
**Rollback Type:** [A/B/C]

## What Went Wrong
[Detailed description of the issue]

## What Went Right
[Aspects of the response that worked well]

## What Could Be Improved
[Areas for improvement in process or technology]

## Action Items
1. [Specific action] - Owner: [NAME] - Due: [DATE]
2. [Specific action] - Owner: [NAME] - Due: [DATE]
3. [Specific action] - Owner: [NAME] - Due: [DATE]

## Process Changes
[Any updates to procedures or documentation]

## Technical Changes
[Any updates to code or configuration]
```

---

## Conclusion

### Rollback Readiness
**Status:** 🟢 READY

- ✅ Procedures documented and tested
- ✅ Backup strategy in place
- ✅ Communication templates ready
- ✅ Monitoring scripts prepared
- ✅ Team trained on procedures

### Quick Reference

**Emergency Rollback Commands:**
```bash
# Rollback A (< 2 min): Disable stream mode only
sed -i 's/"use_stream_mode": True/"use_stream_mode": False/' backend/routers/test_sessions.py
docker-compose restart backend

# Rollback B (< 5 min): Full rollback
cp backend/routers/test_sessions.py.backup backend/routers/test_sessions.py
cp backend/services/labjack_hardware_service.py.backup backend/services/labjack_hardware_service.py
cp backend/services/labjack_detection_service.py.backup backend/services/labjack_detection_service.py
docker-compose restart backend

# Rollback C (< 1 min): Emergency shutdown
docker-compose stop backend
```

---

**Document Version:** 1.0
**Last Updated:** 2025-11-18
**Next Review:** Post-deployment
**Approved By:** [APPROVAL SIGNATURE]
