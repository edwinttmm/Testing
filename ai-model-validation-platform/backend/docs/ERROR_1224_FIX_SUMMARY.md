# ERROR 1224 FIX - Quick Reference

## The Problem (In 30 Seconds)

```
✅ LabJack connects at 09:58:03
🔧 Health monitoring starts (30-second interval)
❓ Something closes the handle between 09:58:03 and 09:58:33
⏰ Health check runs at 09:58:33 (30 seconds later)
❌ ERROR 1224: Device handle already closed
```

**Root Cause**: Race condition - health monitoring thread reads from closed handle

---

## The Fix

### File: `services/labjack_hardware_service.py`

### Change 1: Add Handle Validation (Line 756)

**BEFORE**:
```python
def _health_monitoring_loop(self):
    consecutive_failures = 0
    max_consecutive_failures = 10

    while self.health_check_active:
        try:
            # ❌ No validation - reads even if handle closed
            test_voltage = self.read_single_voltage("AIN0")
            consecutive_failures = 0
```

**AFTER**:
```python
def _health_monitoring_loop(self):
    consecutive_failures = 0
    max_consecutive_failures = 10

    while self.health_check_active:
        # ✅ Validate handle before attempting read
        if self.handle is None or not self.is_connected():
            logger.debug("Health monitor exiting - device not connected")
            break

        try:
            test_voltage = self.read_single_voltage("AIN0")
            consecutive_failures = 0
```

---

## Why This Works

1. **Before Read**: Check if handle is still valid
2. **Early Exit**: Stop health monitoring if device disconnected
3. **No More Error 1224**: Won't attempt read with closed handle

---

## How to Apply

```bash
# Navigate to backend directory
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Edit the file
nano services/labjack_hardware_service.py

# Add the validation at line 756 (start of while loop in _health_monitoring_loop)
# Add these 4 lines right after "while self.health_check_active:"

        # Validate handle before attempting read
        if self.handle is None or not self.is_connected():
            logger.debug("Health monitor exiting - device not connected")
            break

# Save and restart application
```

---

## Test the Fix

```bash
# Start application
python main.py

# Watch logs - should NOT see error 1224 after 30 seconds
tail -f backend.log | grep -E "1224|Health|connected"
```

**Expected behavior**:
- ✅ Device connects
- ✅ Health monitoring starts
- ✅ If handle closes, health monitoring exits gracefully
- ❌ NO error 1224

---

## Long-Term Fix

**TODO**: Investigate multiple service instance creation

```
09:58:01.327 - labjack_hardware_service initialized
09:58:03.199 - Connected to T7
09:58:03.825 - labjack_service created (disconnected)  ⚠️ WHY?
```

**Question**: Why are TWO different LabJack service types created?
- `LabJackHardwareService` (connects)
- `LabJackService` (disconnected)

**Action**: Review `main.py` startup sequence and consolidate to single service type.

---

## Priority

**CRITICAL**: Apply immediately before production use

**Risk**: Medium - false hardware failures, test reliability issues

**Effort**: 5 minutes to apply immediate fix

---

## See Also

- Full analysis: `docs/ERROR_1224_ROOT_CAUSE_ANALYSIS.md`
- Code location: `services/labjack_hardware_service.py` line 751-792
- Related issue: Multiple service instance creation pattern
