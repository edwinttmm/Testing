# Constant Voltage Mode for 100% Detection Rate

## Problem
With constant 4.2V signal, the system only detects 80% of frames due to 100ms debounce period.

## Solution 1: Enable Constant Voltage Mode (Recommended)
Add `constant_voltage_mode: true` to your LabJack configuration.

## Solution 2: Reduce Debounce
Set `debounce_ms: 20` (must be less than frame duration of 41.67ms)

## Solution 3: Increase Sample Rate
Current: 1000 Hz (adequate)
No change needed - sample rate is sufficient

## Quick Fix Script
Run this to test with constant voltage mode:

```python
# In your test setup, pass:
config = {
    'constant_voltage_mode': True,  # Disables debounce
    'detection_threshold': 3.0,      # Your 4.2V is well above this
    'sample_rate': 1000             # 1ms sampling (good for 24 FPS)
}
```

## Expected Result
- Before: 98/122 detections (80%)
- After: 122/122 detections (100%)

## Implementation Locations
- Backend: `services/raw_labjack_logger.py` line 274
- API: `routers/monitoring_service_endpoints.py` line 234
- Frontend: Pass in monitoring configuration

## Test Command
```bash
# Set constant_voltage_mode in your test configuration
curl -X POST http://localhost:8000/api/monitoring/sessions/YOUR_SESSION_ID/start \
  -H "Content-Type: application/json" \
  -d '{"constant_voltage_mode": true, "sample_rate": 1000}'
```
