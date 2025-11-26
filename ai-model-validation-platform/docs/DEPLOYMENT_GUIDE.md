# Deployment Guide: Recall Display Fix & Constant Voltage Mode

## Overview
This guide covers deployment and verification of two critical fixes:
1. **Frontend**: Corrected recall percentage display (was incorrectly showing 100%)
2. **Backend**: Added `constant_voltage_mode` parameter for high-detection testing

**Estimated Deployment Time**: 10-15 minutes

---

## Pre-Deployment Checklist

- [ ] Both code changes are committed and verified
- [ ] No syntax errors in modified files
- [ ] Backup created (if needed for production)
- [ ] Dependencies are up to date
- [ ] Development/test environment ready
- [ ] Browser cache clearing instructions shared with users

---

## Part 1: Frontend Deployment (Recall Display Fix)

### What Was Fixed
**Issue**: Recall was incorrectly displayed as 100% due to improper calculation
- **Root Cause**: Used `recall` variable (already a percentage) divided by 100, then multiplied by 100
- **Fix**: Now correctly uses raw `recall` value without double conversion

### File Modified
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`

### Deployment Steps

#### 1. Navigate to Frontend Directory
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend
```

#### 2. Verify Fix is Applied
```bash
# Check that recall calculation is correct (line 92-93)
grep -A 2 "recallDecimal = recall / 100" src/pages/HILResults.tsx
```

**Expected Output**:
```typescript
const recallDecimal = recall / 100;
const f1Score =
  rawMetrics.f1_score != null || rawMetrics.f1Score != null
```

#### 3. Rebuild Frontend (if needed)
```bash
# Install dependencies if not already installed
npm install

# Build production bundle
npm run build
```

#### 4. Restart Development Server
```bash
# Stop current server (Ctrl+C if running)
# Then restart
npm run dev
```

**Expected Output**:
```
VITE ready in XXXms
Local: http://localhost:3000/
```

### Verification: Test Frontend Fix

#### Test Case 1: Check Recall Display
1. Open browser to session results:
   ```
   http://localhost:3000/results/ddd37359-5535-4b66-b0ec-55178986470a
   ```

2. Locate the "Recall" metric in the metrics section

3. **Expected Results**:
   - If shows "85 TP / 242 GT Events"
   - Calculate manually: 85 ÷ 242 = 0.351 = **35.1%**
   - Display should show: **"Recall: 35.1%"**
   - NOT: "Recall: 100.0%"

4. Verify F1-Score also updates correctly:
   - F1 = 2 × (Precision × Recall) / (Precision + Recall)
   - Should be a reasonable value, not inflated

#### Test Case 2: Browser Cache
If you still see incorrect values:
```bash
# Clear browser cache
# Chrome/Edge: Ctrl+Shift+Delete
# Or hard refresh: Ctrl+Shift+R (Windows) / Cmd+Shift+R (Mac)
```

---

## Part 2: Backend Deployment (Constant Voltage Mode)

### What Was Fixed
**Enhancement**: Added `constant_voltage_mode` parameter to `DetectionTestConfig`
- **Purpose**: Bypass debounce logic for constant voltage testing
- **Behavior**:
  - `constant_voltage_mode=True`: Detects every frame (95-100% detection rate)
  - `constant_voltage_mode=False`: Uses 100ms debounce (33% detection rate, default)

### File Modified
- `/home/rigade/Testing/ai-model-validation-platform/backend/api_enhanced_test_workflow_integrated.py`

### Deployment Steps

#### 1. Navigate to Backend Directory
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
```

#### 2. Verify Fix is Applied
```bash
# Check that constant_voltage_mode parameter exists (line 41)
grep "constant_voltage_mode" api_enhanced_test_workflow_integrated.py
```

**Expected Output**:
```python
constant_voltage_mode: bool = False  # Bypass debounce for constant voltage tests
```

#### 3. Check for Running Backend Processes
```bash
# Find running Python backend processes
ps aux | grep -E "python.*main.py|uvicorn.*main:app" | grep -v grep
```

If processes are running, note the PID(s).

#### 4. Stop Running Backend
```bash
# Kill by process name
pkill -f "python.*main.py"
# Or kill uvicorn specifically
pkill -f "uvicorn.*main:app"

# Verify stopped
ps aux | grep -E "python.*main.py|uvicorn" | grep -v grep
```

**Expected**: No output (no processes running)

#### 5. Activate Virtual Environment (if applicable)
```bash
# If using venv
source venv/bin/activate

# Verify Python environment
which python
# Should show: .../backend/venv/bin/python
```

#### 6. Restart Backend Server
```bash
# Option 1: Direct Python execution
python main.py

# Option 2: Uvicorn with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Option 3: Run in background
nohup python main.py > backend.log 2>&1 &
```

**Expected Output**:
```
INFO:     Started server process [XXXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### 7. Verify Backend is Running
```bash
# Check server health
curl http://localhost:8000/health

# Or check API docs
curl http://localhost:8000/docs
```

**Expected**: HTTP 200 OK response

### Verification: Test Constant Voltage Mode

#### Test Case 1: Standard Mode (Debounce Active)
```bash
# Start test WITHOUT constant voltage mode
curl -X POST http://localhost:8000/api/enhanced-test-workflow/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-project-id",
    "constant_voltage_mode": false,
    "voltage_threshold": 2.5,
    "detection_window_ms": 500.0
  }'
```

**Expected Response**:
```json
{
  "message": "Enhanced Test Workflow started",
  "project_id": "test-project-id",
  "config": {
    "constant_voltage_mode": false
  }
}
```

**Expected Detection Rate**: ~33% (debounce active, 100ms between detections)

#### Test Case 2: Constant Voltage Mode (Debounce Bypassed)
```bash
# Start test WITH constant voltage mode
curl -X POST http://localhost:8000/api/enhanced-test-workflow/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-project-id",
    "constant_voltage_mode": true,
    "voltage_threshold": 2.5,
    "detection_window_ms": 500.0
  }'
```

**Expected Response**:
```json
{
  "message": "Enhanced Test Workflow started",
  "project_id": "test-project-id",
  "config": {
    "constant_voltage_mode": true
  }
}
```

**Expected Detection Rate**: 95-100% (detects every frame)

#### Test Case 3: End-to-End Constant Voltage Test

**Setup**:
1. Connect LabJack device
2. Inject constant voltage (e.g., 4.2V) for 5 seconds
3. Run enhanced test with constant voltage mode enabled

**Commands**:
```bash
# 1. Check LabJack connection
curl http://localhost:8000/api/labjack/status

# 2. Start constant voltage test
curl -X POST http://localhost:8000/api/enhanced-test-workflow/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-project-id",
    "constant_voltage_mode": true,
    "voltage_threshold": 2.5
  }'

# 3. Inject voltage (use LabJack control panel or hardware)

# 4. Check results after test completes
curl http://localhost:8000/api/enhanced-test-workflow/results
```

**Expected Results**:
```json
{
  "active": false,
  "results": [...],
  "summary": {
    "total_videos": 10,
    "passed": 9-10,        // 90-100% pass rate
    "failed": 0-1,
    "avg_latency": 10-50   // Low latency (ms)
  }
}
```

**Success Criteria**:
- Detection rate: **95-100%** (vs 33% in standard mode)
- Status: **PASS** for constant voltage
- Recall metric: **95-100%** (calculated from TP / total GT events)

---

## Rollback Procedures

### If Frontend Issues Occur

#### Option 1: Git Rollback
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Rollback specific file
git checkout HEAD -- src/pages/HILResults.tsx

# Rebuild
npm run build
npm run dev
```

#### Option 2: Manual Revert
Edit `/frontend/src/pages/HILResults.tsx` line 92:
```typescript
// Change FROM:
const recallDecimal = recall / 100;

// Change TO (old incorrect version):
const recallDecimal = accuracyRecall / 100;
```

### If Backend Issues Occur

#### Option 1: Git Rollback
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Rollback specific file
git checkout HEAD -- api_enhanced_test_workflow_integrated.py

# Restart server
pkill -f "python.*main.py"
python main.py
```

#### Option 2: Remove Parameter
Edit `/backend/api_enhanced_test_workflow_integrated.py` line 41:
```python
# Remove this line:
constant_voltage_mode: bool = False  # Bypass debounce for constant voltage tests
```

And update documentation accordingly.

---

## Known Issues and Workarounds

### Issue 1: Frontend Still Shows 100% Recall
**Symptom**: After deployment, recall still displays as 100%
**Cause**: Browser cache not cleared
**Solution**:
```bash
# Hard refresh browser
Ctrl+Shift+R (Windows/Linux)
Cmd+Shift+R (Mac)

# Or clear browser cache completely
Chrome: Ctrl+Shift+Delete > Clear cached images and files
```

### Issue 2: Backend Doesn't Accept `constant_voltage_mode`
**Symptom**: API returns 422 validation error
**Cause**: Backend not restarted or old version running
**Solution**:
```bash
# Kill ALL Python processes (careful!)
pkill -9 python

# Restart backend
cd /home/rigade/Testing/ai-model-validation-platform/backend
python main.py
```

### Issue 3: Database Has Cached Old Values
**Symptom**: Old recall values persist in database
**Cause**: Pre-existing test results stored with incorrect calculations
**Solution**:
```bash
# Re-run tests to generate new results
# Or manually update database (advanced):
sqlite3 database.db "UPDATE test_results SET recall = (true_positives * 100.0 / (true_positives + false_negatives)) WHERE recall = 100.0"
```

### Issue 4: Port Already in Use
**Symptom**: Backend fails to start (port 8000 in use)
**Cause**: Previous process didn't terminate
**Solution**:
```bash
# Find process using port 8000
lsof -i :8000

# Kill by PID
kill -9 <PID>

# Or kill by port
fuser -k 8000/tcp
```

---

## Success Criteria Checklist

### Frontend (Recall Display)
- [ ] Frontend server running without errors
- [ ] Browser loads results page successfully
- [ ] Recall displays correct percentage (NOT 100%)
- [ ] Manual calculation matches displayed value
- [ ] F1-Score is reasonable (not inflated)
- [ ] No errors in browser console (F12)

### Backend (Constant Voltage Mode)
- [ ] Backend server running without errors
- [ ] API accepts `constant_voltage_mode` parameter
- [ ] Standard mode (false): ~33% detection rate
- [ ] Constant voltage mode (true): 95-100% detection rate
- [ ] Test status shows PASS for constant voltage
- [ ] Enhanced test results reflect correct recall percentage
- [ ] No errors in backend logs

### End-to-End Integration
- [ ] Frontend displays backend test results correctly
- [ ] Recall percentage is accurate across frontend and backend
- [ ] Constant voltage tests achieve expected high detection rates
- [ ] Database stores correct metrics
- [ ] No regression in existing functionality

---

## Troubleshooting Commands

### Check Frontend Status
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Check if server is running
ps aux | grep "vite\|npm" | grep -v grep

# Check build for errors
npm run build 2>&1 | grep -i error

# View browser console logs (manual step)
# Open browser > F12 > Console tab
```

### Check Backend Status
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Check if server is running
ps aux | grep "python.*main\|uvicorn" | grep -v grep

# View recent logs
tail -f backend.log

# Test API health
curl -s http://localhost:8000/health | jq

# Test enhanced workflow endpoint
curl -s http://localhost:8000/api/enhanced-test-workflow/status | jq
```

### Verify Code Changes
```bash
# Verify frontend fix (recall calculation)
cd /home/rigade/Testing/ai-model-validation-platform/frontend
grep -n "recallDecimal = recall / 100" src/pages/HILResults.tsx

# Verify backend fix (constant voltage mode)
cd /home/rigade/Testing/ai-model-validation-platform/backend
grep -n "constant_voltage_mode: bool" api_enhanced_test_workflow_integrated.py
```

### Database Inspection
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Check test results
sqlite3 database.db "SELECT id, test_session_id, recall, true_positives, false_negatives FROM test_results ORDER BY created_at DESC LIMIT 5;"

# Recalculate recall for verification
sqlite3 database.db "SELECT id, recall, (true_positives * 100.0 / (true_positives + false_negatives)) AS calculated_recall FROM test_results WHERE (true_positives + false_negatives) > 0 LIMIT 5;"
```

---

## Post-Deployment Validation

### 1. Run Automated Tests (if available)
```bash
# Frontend tests
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm test

# Backend tests
cd /home/rigade/Testing/ai-model-validation-platform/backend
pytest tests/test_enhanced_workflow.py -v
```

### 2. Manual Smoke Tests

**Frontend Smoke Test**:
1. Open http://localhost:3000
2. Navigate to any test session results
3. Verify recall percentage is displayed correctly
4. Verify F1-Score is reasonable
5. Check for any console errors (F12)

**Backend Smoke Test**:
1. Test LabJack connection: `curl http://localhost:8000/api/labjack/status`
2. Start test (standard mode): Send POST to `/api/enhanced-test-workflow/start` with `constant_voltage_mode: false`
3. Start test (constant voltage mode): Send POST with `constant_voltage_mode: true`
4. Check results: `curl http://localhost:8000/api/enhanced-test-workflow/results`
5. Verify logs for errors: `tail -f backend.log`

### 3. Performance Check
```bash
# Check response times
time curl http://localhost:8000/api/enhanced-test-workflow/status

# Check resource usage
top -p $(pgrep -f "python.*main.py")
```

---

## Deployment Completion

### Final Checklist
- [ ] Both services (frontend & backend) are running
- [ ] All verification tests passed
- [ ] No errors in logs or console
- [ ] Recall displays correctly (not 100%)
- [ ] Constant voltage mode accepts parameter
- [ ] Detection rates meet expectations
- [ ] Rollback procedure documented and tested (optional)
- [ ] Users notified to clear browser cache
- [ ] Documentation updated (this guide)

### Deployment Sign-Off
| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | ________ | ________ | ________ |
| QA Tester | ________ | ________ | ________ |
| DevOps | ________ | ________ | ________ |

---

## Support and Contact

**For Issues**:
- Check logs: `/backend/backend.log` or browser console (F12)
- Review this deployment guide
- Check GitHub issues (if applicable)
- Contact development team

**Useful Resources**:
- Frontend source: `/frontend/src/pages/HILResults.tsx`
- Backend source: `/backend/api_enhanced_test_workflow_integrated.py`
- API documentation: http://localhost:8000/docs
- Test results: http://localhost:3000/results/[session-id]

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Deployment Status**: ✅ Ready for Deployment
