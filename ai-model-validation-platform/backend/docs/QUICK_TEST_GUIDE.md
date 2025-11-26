# QUICK TEST GUIDE
## Verifying Both Fixes in 10 Minutes

**Last Updated**: 2025-11-24

---

## TL;DR - What Was Fixed

1. **Recall Display**: Frontend was showing 100% (per-video) instead of 36% (session-wide)
2. **Constant Voltage Mode**: System was only detecting 37.5% of frames due to debounce

---

## Quick Test #1: Verify Recall Display (3 min)

```bash
# Check API response includes metric_scope
curl -X GET "http://localhost:8000/api/sessions/fa204ef2-9d8b-4480-9692-86e338c1218a" | jq '.ground_truth_comparison'
```

**Expected Output**:
```json
{
  "recall": 36.0,  // ✅ NOT 100.0
  "true_positives": 87,
  "total_ground_truth": 242,
  "metric_scope": "session_wide"  // ✅ NEW FIELD
}
```

**Status**: ✅ Backend fixed, frontend integration pending

---

## Quick Test #2: Verify Constant Voltage Mode (5 min)

```bash
# Start session with constant voltage mode enabled
curl -X POST "http://localhost:8000/api/raw-labjack/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "quick_test",
    "channels": ["AIN0"],
    "sample_rate": 1000,
    "constant_voltage_mode": true,
    "detection_threshold": 3.0
  }'

# Check logs for bypass confirmation
tail -f backend.log | grep "⚡"
```

**Expected Log Output**:
```
⚡ [Decision] threshold_cross accepted (CONSTANT VOLTAGE MODE - debounce bypassed)
     for session=abc123 channel=AIN0 gap=41.67ms
```

**Apply constant 4.2V and verify**:
- Normal mode: ~33% detection rate
- Constant voltage mode: ~100% detection rate

**Status**: ✅ Fully implemented and tested

---

## Quick Test #3: Backward Compatibility (2 min)

```bash
# Start WITHOUT constant voltage mode
curl -X POST "http://localhost:8000/api/raw-labjack/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "normal_test",
    "channels": ["AIN0"],
    "sample_rate": 1000
  }'

# Verify debounce still works
tail -f backend.log | grep "debounce"
```

**Expected Log Output**:
```
⛔ [Decision] threshold suppressed by debounce
     for session=def456 channel=AIN0 gap=42.00ms < debounce=100ms
```

**Status**: ✅ Backward compatible

---

## Known Issues

### Issue #1: Frontend Integration Pending
- **Impact**: Frontend may still show wrong recall value
- **Workaround**: Check API response directly
- **ETA**: 1-2 days

### Issue #2: Enhanced Test Workflow Missing constant_voltage_mode
- **Impact**: Can't use constant voltage mode with enhanced workflow
- **Workaround**: Use direct API (`/api/raw-labjack/sessions`)
- **ETA**: 2-3 days

---

## Full Documentation

See: `/backend/docs/COMPREHENSIVE_REVIEW_REPORT.md`

---

## Quick Validation Commands

```bash
# 1. Check DetectionConfig has constant_voltage_mode
python3 -c "from services.labjack_detection_service import DetectionConfig; \
  c = DetectionConfig(session_id='test', channels=['AIN0'], constant_voltage_mode=True); \
  print(f'✅ constant_voltage_mode = {c.constant_voltage_mode}')"

# 2. Run recall calculation tests
pytest tests/test_multi_video_recall_calculation.py -v

# 3. Run constant voltage tests
pytest tests/test_constant_voltage_mode.py -v

# 4. Check API documentation
curl http://localhost:8000/docs | grep constant_voltage_mode
```

---

## Summary

| Fix | Backend | Frontend | Tests | Status |
|-----|---------|----------|-------|--------|
| Recall Display | ✅ Done | ⚠️ Pending | ✅ 6/6 Pass | Ready to deploy backend |
| Constant Voltage | ✅ Done | N/A | ✅ Pass | Ready for production |

**Recommendation**: Deploy backend immediately, update frontend within 1-2 days.
