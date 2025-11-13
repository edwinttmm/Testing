# Deployment Verification Checklist
**Purpose**: Verify timing fixes are actually deployed and executing in production
**Date**: 2025-11-04
**Status**: Pre-Deployment Verification

---

## Critical Finding from Code Review

**The timing fixes exist in code but we cannot confirm they're executing in the live API.**

This checklist provides step-by-step verification that must be completed before production deployment.

---

## Phase 1: Environment Verification (30 minutes)

### 1.1 Backend Status ✅
```bash
# Check if backend is running
curl -s http://localhost:8000/health | jq .

# If not running, start it:
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate
uvicorn main:app --reload --port 8000 &

# Wait for startup
sleep 5
curl -s http://localhost:8000/health
```

**Expected**: `{"status": "healthy"}`
**Actual**: _________
**Pass/Fail**: ____

---

### 1.2 Database Connectivity ✅
```bash
# Install sqlite3 if missing
sudo apt-get install sqlite3 -y

# Verify database exists and is accessible
ls -lh dev_database.db

# Test query
sqlite3 dev_database.db "SELECT COUNT(*) as total_sessions FROM test_sessions;"
```

**Expected**: Database exists, query succeeds
**Actual**: _________
**Pass/Fail**: ____

---

### 1.3 Service Availability ✅
```bash
# Check key services are importable
python3 << EOF
from services.timing_synchronization_calculator import get_timing_synchronization_calculator
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
from services.labjack_detection_service import get_detection_service
print("✅ All services importable")
EOF
```

**Expected**: "✅ All services importable"
**Actual**: _________
**Pass/Fail**: ____

---

## Phase 2: Integration Path Verification (1 hour)

### 2.1 Find Timing Calculator Usage ✅
```bash
# Search for imports
echo "=== Timing Calculator Imports ==="
grep -r "timing_synchronization_calculator" \
  backend/api/*.py \
  backend/routers/*.py \
  backend/main.py

# Search for actual calls
echo "=== Timing Calculator Calls ==="
grep -r "calculate_corrected_latency" \
  backend/api/*.py \
  backend/routers/*.py

# Expected: At least 1 import and 1 call
```

**Imports Found**: _________
**Calls Found**: _________
**Pass/Fail**: ____

**Action if FAIL**: Add timing calculator to API endpoint

---

### 2.2 Verify Detection Storage Path ✅
```bash
# Find all store_in_db usage
echo "=== Detection Storage Configuration ==="
grep -r "store_in_db" backend/services/*.py | grep -v "^#" | grep -v ".pyc"

# Check dedicated_labjack_monitor
grep -A 2 "store_in_db" backend/services/dedicated_labjack_monitor.py

# Expected: store_in_db=False in dedicated monitor
```

**dedicated_labjack_monitor.py**: store_in_db = _________
**Other services**: _________
**Pass/Fail**: ____

**Action if FAIL**: Ensure only dedicated monitor stores detections

---

### 2.3 Check Pagination Limits ✅
```bash
# Search for detection event queries
echo "=== Pagination Configuration ==="
grep -r "\.limit(" backend/api/*.py backend/routers/*.py | grep -i detection

# Search for explicit pagination
grep -r "limit=2000\|limit = 2000\|.limit(2000)" backend/api/*.py backend/routers/*.py

# Expected: limit(2000) in detection event queries
```

**Pagination Found**: _________
**Limit Value**: _________
**Pass/Fail**: ____

**Action if FAIL**: Add `.limit(2000)` to detection queries

---

## Phase 3: Code Execution Verification (1 hour)

### 3.1 Trace API Request Path 🧪
```bash
# Add temporary logging to verify execution
cat > /tmp/test_timing_execution.py << 'EOF'
import requests
import json

# Create test session (mock)
print("Testing timing calculator execution path...")

# Make API request to HIL results endpoint
response = requests.get(
    "http://localhost:8000/api/enhanced-hil-results/0846e476-e0e8-4f3f-9d73-bce64da1d2d1"
)

if response.status_code == 200:
    data = response.json()

    # Check for timing-related fields
    if "detection_events" in data:
        events = data["detection_events"]
        if events and len(events) > 0:
            first_event = events[0]

            # Verify timing fields populated
            has_video_relative = "video_relative_timestamp" in first_event
            has_frame_number = "video_frame_number" in first_event
            has_latency = "latency_ms" in first_event or "actual_latency_ms" in first_event

            print(f"✅ Found {len(events)} detection events")
            print(f"   video_relative_timestamp: {has_video_relative}")
            print(f"   video_frame_number: {has_frame_number}")
            print(f"   latency field: {has_latency}")

            if has_video_relative and has_frame_number:
                print("\n✅ PASS: Timing fields populated")
            else:
                print("\n❌ FAIL: Timing fields missing")
        else:
            print("⚠️ No detection events found")
    else:
        print("❌ FAIL: No detection_events in response")
else:
    print(f"❌ FAIL: Request failed with status {response.status_code}")
EOF

python3 /tmp/test_timing_execution.py
```

**Detection Events Found**: _________
**video_relative_timestamp present**: _________
**video_frame_number present**: _________
**Pass/Fail**: ____

---

### 3.2 Verify Database Fields 🧪
```bash
# Check if detection events have timing fields populated
sqlite3 dev_database.db << 'EOF'
.headers on
.mode column

-- Check recent detections for timing fields
SELECT
    id,
    test_session_id,
    video_relative_timestamp,
    video_frame_number,
    timestamp,
    labjack_timestamp
FROM detection_events
WHERE test_session_id = '0846e476-e0e8-4f3f-9d73-bce64da1d2d1'
LIMIT 5;

-- Check for null timing fields
SELECT
    COUNT(*) as total_events,
    SUM(CASE WHEN video_relative_timestamp IS NULL THEN 1 ELSE 0 END) as null_video_time,
    SUM(CASE WHEN video_frame_number IS NULL THEN 1 ELSE 0 END) as null_frame_number
FROM detection_events
WHERE test_session_id = '0846e476-e0e8-4f3f-9d73-bce64da1d2d1';
EOF
```

**Total Events**: _________
**NULL video_relative_timestamp**: _________
**NULL video_frame_number**: _________
**Pass/Fail**: ____

**Action if FAIL**: Timing calculator not populating fields

---

### 3.3 Test Latency Calculation 🧪
```bash
# Create test script to verify timing calculation
cat > /tmp/test_latency_calc.py << 'EOF'
from services.timing_synchronization_calculator import (
    get_timing_synchronization_calculator,
    VideoTimingMetadata
)
import time

print("Testing timing synchronization calculator...")

# Get calculator instance
calc = get_timing_synchronization_calculator()

# Create test timing metadata
video_timing = VideoTimingMetadata(
    startup_delay_ms=100.0,
    fps=30.0,
    duration=10.0,
    timing_sync_status="synchronized"
)

# Test calculation
current_time = time.time()
video_start_time = current_time - 5.0  # Video started 5 seconds ago
labjack_start = video_start_time
detection_time = current_time  # Detection just happened
gt_video_time = 4.5  # GT event at 4.5s in video

try:
    result = calc.calculate_corrected_latency(
        session_id="test-session",
        detection_id="test-detection",
        detection_system_time=detection_time,
        ground_truth_frame=135,  # 4.5s * 30fps
        ground_truth_video_time=gt_video_time,
        video_timing_metadata=video_timing,
        labjack_start_time=labjack_start,
        video_start_time=video_start_time
    )

    print(f"\n✅ Calculation succeeded!")
    print(f"   video_relative_timestamp: {result.video_relative_timestamp:.3f}s")
    print(f"   video_frame_number: {result.video_frame_number}")
    print(f"   real_latency_ms: {result.real_latency_ms:.1f}ms")
    print(f"   apparent_latency_ms: {result.apparent_latency_ms:.1f}ms")

    # Verify reasonable values
    if result.video_relative_timestamp is not None and result.video_relative_timestamp > 0:
        print("\n✅ PASS: video_relative_timestamp calculated correctly")
    else:
        print(f"\n❌ FAIL: video_relative_timestamp = {result.video_relative_timestamp}")

except Exception as e:
    print(f"\n❌ FAIL: Calculation error: {e}")
    import traceback
    traceback.print_exc()
EOF

cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 /tmp/test_latency_calc.py
```

**Calculation Success**: _________
**video_relative_timestamp value**: _________
**Reasonable values**: _________
**Pass/Fail**: ____

---

## Phase 4: End-to-End Verification (2 hours)

### 4.1 Create New Test Session 🧪
```bash
# Use API to create a test session
curl -X POST http://localhost:8000/api/test-sessions \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-project",
    "video_id": "test-video",
    "test_type": "HIL"
  }' | jq .

# Save session ID from response
export TEST_SESSION_ID="<from_response>"
```

**Session Created**: _________
**Session ID**: _________
**Pass/Fail**: ____

---

### 4.2 Simulate Detection Events 🧪
```bash
# Add detection events via API
curl -X POST "http://localhost:8000/api/test-sessions/$TEST_SESSION_ID/detections" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": '$(($(date +%s) * 1000))',
    "voltage": 3.5,
    "channel": "AIN0"
  }'

# Check if detection was stored
sqlite3 dev_database.db \
  "SELECT COUNT(*) FROM detection_events WHERE test_session_id = '$TEST_SESSION_ID';"
```

**Detection Created**: _________
**Pass/Fail**: ____

---

### 4.3 Verify Timing Fields Populated 🧪
```bash
# Check the detection event
sqlite3 dev_database.db << EOF
.headers on
.mode column
SELECT
    video_relative_timestamp,
    video_frame_number,
    timestamp,
    labjack_timestamp
FROM detection_events
WHERE test_session_id = '$TEST_SESSION_ID'
LIMIT 1;
EOF
```

**video_relative_timestamp**: _________
**video_frame_number**: _________
**Both populated**: _________
**Pass/Fail**: ____

---

## Phase 5: Session 0846e476 Verification (30 minutes)

### 5.1 Analyze Session Data 🧪
```bash
# Get session info
sqlite3 dev_database.db << 'EOF'
.headers on
.mode column

-- Session overview
SELECT
    id,
    started_at,
    completed_at,
    video_id,
    sequence_id
FROM test_sessions
WHERE id = '0846e476-e0e8-4f3f-9d73-bce64da1d2d1';

-- Detection events for session
SELECT
    COUNT(*) as total_detections,
    MIN(video_relative_timestamp) as first_detection_time,
    MAX(video_relative_timestamp) as last_detection_time,
    AVG(video_relative_timestamp) as avg_detection_time
FROM detection_events
WHERE test_session_id = '0846e476-e0e8-4f3f-9d73-bce64da1d2d1'
AND video_relative_timestamp IS NOT NULL;
EOF
```

**Session Found**: _________
**Total Detections**: _________
**Timing Fields Populated**: _________
**Pass/Fail**: ____

---

### 5.2 Check for Year 1762 Bug 🧪
```bash
# Check for unreasonable timestamps
sqlite3 dev_database.db << 'EOF'
-- Look for video_relative_timestamp values that indicate bug
-- Normal: 0-60 seconds
-- Bug: Millions of seconds (year 1762)
SELECT
    id,
    video_relative_timestamp,
    CASE
        WHEN video_relative_timestamp > 1000 THEN '❌ BUG PRESENT'
        WHEN video_relative_timestamp IS NULL THEN '⚠️ NULL VALUE'
        ELSE '✅ REASONABLE'
    END as status
FROM detection_events
WHERE test_session_id = '0846e476-e0e8-4f3f-9d73-bce64da1d2d1'
LIMIT 10;
EOF
```

**Unreasonable timestamps found**: _________
**All values < 1000 seconds**: _________
**Pass/Fail**: ____

---

## Phase 6: Regression Testing (1 hour)

### 6.1 Check for Duplicate Events 🧪
```bash
# Look for duplicate detection events
sqlite3 dev_database.db << 'EOF'
-- Find duplicates (same session, timestamp, channel)
SELECT
    test_session_id,
    timestamp,
    detection_channel,
    COUNT(*) as duplicate_count
FROM detection_events
GROUP BY test_session_id, timestamp, detection_channel
HAVING COUNT(*) > 1
LIMIT 10;
EOF
```

**Duplicates Found**: _________
**Pass/Fail**: ____

**Action if FAIL**: Multiple storage paths active

---

### 6.2 Verify Pagination Working 🧪
```bash
# Create session with many events
curl http://localhost:8000/api/enhanced-hil-results/$TEST_SESSION_ID | \
  jq '.detection_events | length'

# Expected: All events returned (up to 2000)
```

**Events Returned**: _________
**All Events Included**: _________
**Pass/Fail**: ____

---

### 6.3 Performance Check 🧪
```bash
# Check query performance
time curl -s http://localhost:8000/api/enhanced-hil-results/0846e476-e0e8-4f3f-9d73-bce64da1d2d1 > /dev/null

# Expected: < 2 seconds
```

**Response Time**: _________
**Acceptable Performance**: _________
**Pass/Fail**: ____

---

## Summary Checklist

| Phase | Item | Status | Notes |
|-------|------|--------|-------|
| 1.1 | Backend Running | ☐ | |
| 1.2 | Database Accessible | ☐ | |
| 1.3 | Services Available | ☐ | |
| 2.1 | Timing Calculator Used | ☐ | |
| 2.2 | Storage Path Correct | ☐ | |
| 2.3 | Pagination Increased | ☐ | |
| 3.1 | API Execution Traced | ☐ | |
| 3.2 | Database Fields Populated | ☐ | |
| 3.3 | Latency Calculation Works | ☐ | |
| 4.1 | New Session Created | ☐ | |
| 4.2 | Detection Events Stored | ☐ | |
| 4.3 | Timing Fields Populated | ☐ | |
| 5.1 | Session 0846e476 Analyzed | ☐ | |
| 5.2 | No Year 1762 Bug | ☐ | |
| 6.1 | No Duplicates | ☐ | |
| 6.2 | Pagination Working | ☐ | |
| 6.3 | Performance Acceptable | ☐ | |

**Total Passed**: _____ / 17
**Ready for Production**: ☐ YES ☐ NO

---

## Deployment Decision

### ✅ APPROVED FOR PRODUCTION if:
- [ ] All Phase 1-3 items pass (environment & integration)
- [ ] At least 80% of Phase 4-6 items pass (e2e & regression)
- [ ] No critical issues found
- [ ] Session 0846e476 verified

### ❌ DO NOT DEPLOY if:
- [ ] Phase 2.1 fails (timing calculator not integrated)
- [ ] Phase 3.2 fails (database fields not populated)
- [ ] Phase 5.2 fails (year 1762 bug still present)
- [ ] Phase 6.1 fails (duplicate events found)

---

## Action Items Based on Results

### If Timing Calculator Not Integrated:
```python
# Add to api/enhanced_hil_results_endpoints.py
from services.timing_synchronization_calculator import get_timing_synchronization_calculator

timing_calc = get_timing_synchronization_calculator()

# Use in detection processing
for detection in detections:
    timing_result = timing_calc.calculate_corrected_latency(...)
    detection.video_relative_timestamp = timing_result.video_relative_timestamp
    detection.video_frame_number = timing_result.video_frame_number
```

### If Pagination Not Increased:
```python
# Add to detection event queries
detection_events = db.query(DetectionEvent)\
    .filter(DetectionEvent.test_session_id == session_id)\
    .limit(2000)\  # ADD THIS LINE
    .all()
```

### If Duplicates Found:
```python
# Ensure only dedicated monitor stores events
# In labjack_detection_service.py:
config = DetectionConfig(
    store_in_db=False,  # CHANGE TO False
    ...
)
```

---

**Verification Date**: ___________
**Verified By**: ___________
**Production Deployment Approved**: ☐ YES ☐ NO
**Deployment Date**: ___________
