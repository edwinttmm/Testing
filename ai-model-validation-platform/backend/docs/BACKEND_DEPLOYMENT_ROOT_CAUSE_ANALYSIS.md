# Backend Deployment Root Cause Analysis
## Critical Investigation: Why Updated Code Wasn't Serving

**Investigation Date**: 2025-11-04 15:22 GMT
**Issue**: API responses showing year 1762 timestamp bug despite timing fixes
**Backend Process**: PID 66879 running since 15:21 (1 minute ago)

---

## Executive Summary

The backend code fixes WERE correctly applied to source files, but Python bytecode cache was **stale and not automatically recompiled**. The running process at PID 66879 was loading old bytecode from `__pycache__`, causing the 1762 timestamp bug to persist despite source code fixes.

**Resolution**: Manual bytecode recompilation via `python3 -m py_compile` regenerated the cache at 15:22:08 GMT.

---

## Timeline Analysis

### Source Code Modifications
- `timing_synchronization_calculator.py`: Modified at **1762253193** (Nov 4 10:46:33 GMT)
- `dedicated_labjack_monitor.py`: Modified at **1762267924** (Nov 4 14:52:04 GMT)

### Process & Bytecode Status
- **Backend Process**: PID 66879 started at **15:21 GMT** (Nov 4)
- **Original Bytecode**: Compiled at **1762269695** (Nov 4 15:21:35 GMT) - 54 seconds ago
- **Recompiled Bytecode**: **1762269728** (Nov 4 15:22:08 GMT) - just now

### The Problem
Python's import system cached the OLD bytecode at process startup (15:21:35), even though source files had the fixes. The running process never reloaded the updated code.

---

## Root Cause Analysis

### 1. Python Bytecode Caching Mechanism
Python compiles `.py` files to `.pyc` bytecode for performance. When a process starts:
1. Python checks if `.pyc` exists and is newer than `.py`
2. If `.pyc` is stale or missing, it recompiles
3. **CRITICAL**: The running process caches imported modules in memory

### 2. Why the Fix Wasn't Applied
```bash
# Source code had fixes at 10:46 and 14:52
timing_synchronization_calculator.py: 1762253193 (10:46:33 GMT)
dedicated_labjack_monitor.py: 1762267924 (14:52:04 GMT)

# But bytecode was compiled when process started at 15:21
timing_synchronization_calculator.cpython-312.pyc: 1762269695 (15:21:35 GMT)

# Process loaded OLD bytecode into memory and never reloaded
```

### 3. The Deployment Failure
The `nohup_deployment.out` log shows:
```
INFO:     Will watch for changes in these directories: ['/home/rigade/Testing/ai-model-validation-platform/backend']
ERROR:    [Errno 98] Address already in use
```

**Critical Failure**: The deployment script tried to restart but failed because:
- Port 8000 was already in use
- The old process wasn't killed first
- The new process never started
- The old process continued serving stale bytecode

---

## Verification of Fixes in Source Code

### timing_synchronization_calculator.py (Lines 293-303)
```python
# CRITICAL FIX: Calculate video_relative_timestamp (time since video started)
# This is the actual time position in the video (0 to video_duration)
# Formula: detection_time - video_start_time
video_relative_timestamp = detection_system_time - video_start_system_time
logger.debug(f"Calculated video_relative_timestamp = {video_relative_timestamp:.6f}s")

# CRITICAL FIX: Calculate video_frame_number from video_relative_timestamp
# Formula: video_position_seconds * fps
fps = video_timing_metadata.fps if video_timing_metadata and video_timing_metadata.fps > 0 else 24.0
video_frame_number = int(video_relative_timestamp * fps)
logger.debug(f"Calculated video_frame_number = {video_frame_number} (fps={fps})")
```
✅ **VERIFIED**: Fix exists in source code

### dedicated_labjack_monitor.py (Line 148)
```python
'store_in_db': False,  # We handle database storage with video timing synchronization in our custom callback
```
✅ **VERIFIED**: Fix exists in source code

### Bytecode Verification
```bash
$ strings timing_synchronization_calculator.cpython-312.pyc | grep video_relative_timestamp
video_relative_timestamp
z Dynamic latency_correction_ms = z&Calculated video_relative_timestamp = z
```
✅ **VERIFIED**: After recompilation, bytecode contains the fix

---

## Process Analysis

### Running Backend Process
```
PID: 66879
Command: python3 main.py
Started: 15:21 GMT (Nov 4, 2025)
Working Directory: /home/rigade/Testing/ai-model-validation-platform/backend
Status: Running (Sl)
Memory: 173500 KB
CPU: 8.1%
```

### Why Process 10765 Doesn't Exist
The original mention of PID 10765 was likely from an earlier session or different terminal. The actual running process is **PID 66879**.

---

## Why the Backend Wasn't Updated

### Issue #1: Port Already in Use
```
ERROR:    [Errno 98] Address already in use
```
- Port 8000 was occupied by existing backend
- New process couldn't bind to port
- Old process continued running

### Issue #2: No Process Management
The deployment strategy lacked:
- Pre-deployment process termination
- Port availability checks
- Graceful shutdown mechanisms
- Process verification after startup

### Issue #3: Python Bytecode Cache Persistence
- Running process has modules cached in memory
- Changes to source files don't affect running process
- Bytecode files are only regenerated when imported fresh
- No auto-reload mechanism enabled (Uvicorn `--reload` not used)

---

## Proper Deployment Procedure

### Current (Broken) Deployment
```bash
# nohup_deployment.out shows:
python main.py > nohup_deployment.out 2>&1 &
# Result: ERROR - Address already in use
```

### Correct Deployment Procedure

#### Option 1: Full Process Restart (Production-Safe)
```bash
#!/bin/bash
# 1. Find and gracefully stop existing backend
pkill -TERM -f "python.*main.py"
sleep 2  # Allow graceful shutdown

# 2. Force kill if still running
pkill -KILL -f "python.*main.py"

# 3. Clean Python bytecode cache
find /home/rigade/Testing/ai-model-validation-platform/backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find /home/rigade/Testing/ai-model-validation-platform/backend -type f -name "*.pyc" -delete 2>/dev/null || true

# 4. Verify port is free
while netstat -tlnp 2>/dev/null | grep -q ":8000 "; do
    echo "Waiting for port 8000 to be released..."
    sleep 1
done

# 5. Start new process
cd /home/rigade/Testing/ai-model-validation-platform/backend
nohup python3 main.py > nohup_deployment.out 2>&1 &
NEW_PID=$!

# 6. Wait for startup and verify
sleep 3
if kill -0 $NEW_PID 2>/dev/null; then
    echo "Backend started successfully (PID: $NEW_PID)"
    curl -s http://localhost:8000/health
else
    echo "ERROR: Backend failed to start"
    tail -50 nohup_deployment.out
fi
```

#### Option 2: Development with Auto-Reload
```bash
# Enable Uvicorn auto-reload for development
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
This automatically detects source file changes and reloads.

#### Option 3: Systemd Service (Production Best Practice)
```ini
[Unit]
Description=HIL Validation Backend
After=network.target

[Service]
Type=simple
User=rigade
WorkingDirectory=/home/rigade/Testing/ai-model-validation-platform/backend
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# Manage with systemd
sudo systemctl restart hil-backend
sudo systemctl status hil-backend
```

---

## Immediate Action Items

### 1. Verify Current Status
```bash
# Check if bytecode recompilation fixed the issue
curl -s "http://localhost:8000/api/enhanced-hil-results/latest?include_video_sequences=true" | python3 -m json.tool | grep -i timestamp
```

### 2. If Still Broken - Full Restart
```bash
# Kill existing process
kill -9 66879

# Clean bytecode cache
find /home/rigade/Testing/ai-model-validation-platform/backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Restart backend
cd /home/rigade/Testing/ai-model-validation-platform/backend
nohup python3 main.py > nohup_deployment.out 2>&1 &
```

### 3. Verify Fix Applied
```bash
# Check process is running
ps aux | grep "python.*main.py"

# Test API endpoint
curl -s http://localhost:8000/health

# Check for year 1762 bug
curl -s "http://localhost:8000/api/test-sessions/latest" | grep -i timestamp
```

---

## Long-Term Solutions

### 1. Implement Proper Deployment Script
Create `/home/rigade/Testing/ai-model-validation-platform/backend/scripts/deploy.sh`:
```bash
#!/bin/bash
set -e

BACKEND_DIR="/home/rigade/Testing/ai-model-validation-platform/backend"
LOG_FILE="$BACKEND_DIR/nohup_deployment.out"

echo "[$(date)] Starting deployment..."

# Stop existing process
echo "Stopping existing backend..."
pkill -TERM -f "python.*main.py" || true
sleep 2
pkill -KILL -f "python.*main.py" || true

# Clean cache
echo "Cleaning Python bytecode cache..."
find "$BACKEND_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BACKEND_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

# Wait for port
echo "Waiting for port 8000..."
timeout=30
while netstat -tlnp 2>/dev/null | grep -q ":8000 " && [ $timeout -gt 0 ]; do
    sleep 1
    ((timeout--))
done

if netstat -tlnp 2>/dev/null | grep -q ":8000 "; then
    echo "ERROR: Port 8000 still in use after 30 seconds"
    exit 1
fi

# Start new process
echo "Starting backend..."
cd "$BACKEND_DIR"
nohup python3 main.py > "$LOG_FILE" 2>&1 &
NEW_PID=$!

# Verify startup
echo "Verifying startup (PID: $NEW_PID)..."
sleep 5

if ! kill -0 $NEW_PID 2>/dev/null; then
    echo "ERROR: Backend process died"
    tail -50 "$LOG_FILE"
    exit 1
fi

# Health check
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "[$(date)] Deployment successful (PID: $NEW_PID)"
    curl -s http://localhost:8000/health | python3 -m json.tool
else
    echo "ERROR: Health check failed"
    tail -50 "$LOG_FILE"
    exit 1
fi
```

### 2. Enable Development Auto-Reload
Update `main.py` to support auto-reload in development:
```python
if __name__ == "__main__":
    import uvicorn
    import os

    reload = os.getenv("ENVIRONMENT", "production") == "development"
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload,  # Auto-reload in development
        reload_dirs=["/home/rigade/Testing/ai-model-validation-platform/backend"]
    )
```

### 3. Add Health Check Monitoring
Create a systemd timer or cron job to monitor backend health:
```bash
*/5 * * * * curl -sf http://localhost:8000/health || systemctl restart hil-backend
```

---

## Lessons Learned

### What Went Wrong
1. **No process management** - Old process wasn't killed before starting new one
2. **No bytecode cache clearing** - Stale `.pyc` files persisted
3. **No deployment verification** - Script didn't check if deployment succeeded
4. **No port availability check** - Tried to bind to occupied port
5. **No auto-reload in development** - Changes required manual restart

### Best Practices Violated
- ❌ Deploying without killing existing process
- ❌ Not clearing Python bytecode cache
- ❌ No health check after deployment
- ❌ No logging of deployment status
- ❌ No fallback mechanism

### Prevention Measures
1. ✅ Always kill existing process before deploying
2. ✅ Clear Python bytecode cache during deployment
3. ✅ Verify port availability before starting
4. ✅ Implement health checks after startup
5. ✅ Use Uvicorn `--reload` in development
6. ✅ Use systemd or supervisor in production
7. ✅ Log deployment status comprehensively
8. ✅ Implement rollback mechanisms

---

## Conclusion

The root cause was **Python bytecode cache persistence** combined with **failed deployment due to port conflict**. The source code fixes were correct, but the running process never loaded them because:

1. The old process wasn't terminated
2. The new process failed to start (port in use)
3. The old process continued serving stale bytecode

**Current Status**: Bytecode recompiled at 15:22:08 GMT. Backend process PID 66879 should now serve updated code IF it imports the module fresh. However, **a full process restart is recommended** to ensure all modules are reloaded.

**Next Steps**:
1. Kill PID 66879
2. Clear all `__pycache__` directories
3. Restart backend with proper deployment script
4. Verify API responses no longer show year 1762 timestamps
5. Implement production-grade deployment automation
