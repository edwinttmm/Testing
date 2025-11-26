# Quick Fix: Reduce Detection Gaps from 125ms

## Problem
- **Current**: 125ms gaps between detections
- **Expected**: Continuous detections during GT presence
- **Cause**: 100ms debounce + 25ms processing overhead

## Immediate Solution (Recommended)

### Option A: Reduce Debounce to 20ms (Quick & Effective)

**Changes Required**:

1. **Edit `/backend/config/timing_config.py` line 49**:
```python
# BEFORE:
DETECTION_DEBOUNCE_MS = 100

# AFTER:
DETECTION_DEBOUNCE_MS = 20  # Optimized for 24 FPS (41.67ms frame period)
```

2. **Edit `/backend/services/labjack_detection_service.py` line 135**:
```python
# BEFORE:
debounce_ms: int = 100

# AFTER:
debounce_ms: int = 20  # Matches frame period for continuous detection
```

3. **Edit `/backend/api_labjack_detection.py` line 46**:
```python
# BEFORE:
debounce_ms: int = Field(default=100, ge=10, le=5000, ...)

# AFTER:
debounce_ms: int = Field(default=20, ge=5, le=5000, ...)
```

**Expected Results**:
- ✅ Gaps reduced to ~40-45ms (20ms debounce + 20-25ms processing)
- ✅ 2-3x more detections per second
- ✅ Better tracking of continuous presence
- ⚠️ May increase false positives slightly

**Test Command**:
```bash
# Restart backend to pick up changes
docker-compose restart backend

# Or if running directly:
pkill -f "python.*main.py" && python backend/main.py
```

---

### Option B: Enhance Steady High Mode (Lower Risk)

**Changes Required**:

1. **Edit `/backend/services/labjack_detection_service.py` line 144**:
```python
# BEFORE:
steady_high_interval_ms: int = 5

# AFTER:
steady_high_interval_ms: int = 20  # Increased to match reduced debounce
```

**Expected Results**:
- ✅ Keeps 100ms debounce for initial detection (low FP)
- ✅ Periodic samples every 20ms during continuous high voltage
- ✅ Detection states distinguish edge vs steady (threshold_cross vs steady_high)
- ✅ Best of both worlds: precision + detection rate

**Test Command**: Same as Option A

---

## Environment Variable Override (No Code Changes)

**Alternative**: Override via environment variable

**Edit `/backend/.env`**:
```bash
# Add or update this line:
LABJACK_DEBOUNCE_MS=20
```

**Current value in .env**: `LABJACK_DEBOUNCE_MS=100`

**Note**: This only affects specific code paths that read this env var directly.

---

## Testing at Runtime (API Override)

**No restart required** - override per session:

```bash
curl -X POST http://localhost:8000/api/detection/start \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-123",
    "channels": ["AIN0", "AIN1"],
    "voltage_threshold": 2.5,
    "debounce_ms": 20,
    "sample_rate": 1000
  }'
```

**For constant voltage testing** (bypass debounce completely):
```bash
curl -X POST http://localhost:8000/api/detection/start \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-123",
    "channels": ["AIN0", "AIN1"],
    "voltage_threshold": 2.5,
    "debounce_ms": 0,
    "constant_voltage_mode": true,
    "sample_rate": 1000
  }'
```

---

## Verification

### Check Current Configuration

**View active debounce**:
```bash
# Check if service is using new value
curl http://localhost:8000/api/detection/status/your-session-id | jq '.config.debounce_ms'
```

**Check detection statistics**:
```bash
curl http://localhost:8000/api/detection/statistics
```

### Monitor Detection Gaps

**Watch real-time detections**:
```bash
# Check detection event timestamps
curl http://localhost:8000/api/detection/events/your-session-id | jq '.events[] | {timestamp, channel, voltage}'
```

**Calculate gaps**:
```python
import json
from datetime import datetime

# Get events
events = json.loads(requests.get('http://localhost:8000/api/detection/events/session-id').text)['events']

# Calculate gaps
timestamps = [datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')) for e in events]
gaps = [(timestamps[i+1] - timestamps[i]).total_seconds() * 1000 for i in range(len(timestamps)-1)]

print(f"Average gap: {sum(gaps)/len(gaps):.1f}ms")
print(f"Min gap: {min(gaps):.1f}ms")
print(f"Max gap: {max(gaps):.1f}ms")
```

---

## Rollback Plan

If false positives increase unacceptably:

1. **Revert code changes** (restore to 100ms)
2. **Or increase debounce incrementally**:
   - Try 30ms
   - Try 40ms
   - Try 50ms
   - Find optimal balance

3. **Or enable duplicate filtering**:
```python
# In detection config
enable_duplicate_filtering: bool = True  # Already enabled by default
```

---

## Summary

| Solution | Effort | Risk | Effectiveness |
|----------|--------|------|---------------|
| **Option A: Reduce to 20ms** | 3 file edits | ⚠️ Medium (FP risk) | ✅ Highly effective |
| **Option B: Enhance steady high** | 1 file edit | ✅ Low risk | ✅ Effective |
| **Env variable** | 1 line change | ⚠️ Medium (partial coverage) | ⚠️ Moderate |
| **API override** | No changes | ✅ Zero risk (per-session) | ✅ Effective for testing |

**Recommended**: Start with **Option B** (lowest risk), then move to **Option A** if needed.

---

## File Locations

```
/home/rigade/Testing/ai-model-validation-platform/backend/
├── config/
│   └── timing_config.py            # Line 49: DETECTION_DEBOUNCE_MS = 100
├── services/
│   └── labjack_detection_service.py # Line 135: debounce_ms = 100
│                                    # Line 144: steady_high_interval_ms = 5
├── api_labjack_detection.py        # Line 46: debounce_ms default
└── .env                            # LABJACK_DEBOUNCE_MS=100
```

---

*Quick reference generated: 2025-11-25*
