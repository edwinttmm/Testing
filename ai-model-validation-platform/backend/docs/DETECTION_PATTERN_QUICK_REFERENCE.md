# DETECTION PATTERN QUICK REFERENCE

## Pattern Recognition Guide

### 🎯 Quick Identification

| Pattern | Frame Gap | Time Gap (24 FPS) | Coverage | Visual Pattern |
|---------|-----------|-------------------|----------|----------------|
| **Constant Voltage** | 1 frame | ~42ms | 100% | ✅✅✅✅✅✅✅✅ |
| **Debounce (3x)** | 3 frames | ~125ms | 33% | ✅❌❌✅❌❌✅❌❌ |
| **Debounce (5x)** | 5 frames | ~208ms | 20% | ✅❌❌❌❌✅❌❌❌❌ |
| **Sparse Sample** | 75+ frames | 2,500ms+ | <5% | ✅----✅----✅---- |

---

## Pattern A: Constant Voltage Mode (100% Capture)

### Characteristics
- **Frame Gap:** 1 (every frame)
- **Time Gap:** ~41.67ms (1000ms ÷ 24 FPS)
- **Coverage:** 100%
- **Use Case:** Maximum accuracy, latency measurement, critical systems

### Detection Pattern
```
Frame   99: ✅ detected
Frame  100: ✅ detected (gap: 1 frame, 41.67ms)
Frame  101: ✅ detected (gap: 1 frame, 41.67ms)
Frame  102: ✅ detected (gap: 1 frame, 41.67ms)
Frame  103: ✅ detected (gap: 1 frame, 41.67ms)
Frame  104: ✅ detected (gap: 1 frame, 41.67ms)
```

### Identification Criteria
- ✅ 80%+ of frame gaps = 1
- ✅ Average time gap: 35-50ms
- ✅ Coverage: >90%
- ✅ Configuration: `constant_voltage_mode = true`, `debounce_ms = 0`

### Expected Performance
- Detection rate: 24 detections/second (at 24 FPS)
- Latency measurement: Accurate to <1ms
- Resource usage: HIGH (CPU, memory, storage)

---

## Pattern B: Debounce Active (33% Capture)

### Characteristics
- **Frame Gap:** 3 (every 3rd frame)
- **Time Gap:** ~125ms (3 × 41.67ms)
- **Coverage:** 33.3%
- **Use Case:** Reduce duplicate detections, save resources, non-critical monitoring

### Detection Pattern
```
Frame   99: ✅ detected
Frame  100: ❌ skipped (debounce)
Frame  101: ❌ skipped (debounce)
Frame  102: ✅ detected (gap: 3 frames, 125ms)
Frame  103: ❌ skipped (debounce)
Frame  104: ❌ skipped (debounce)
Frame  105: ✅ detected (gap: 3 frames, 125ms)
```

### Identification Criteria
- ✅ 50%+ of frame gaps = 3
- ✅ Average time gap: 100-150ms
- ✅ Coverage: 25-40%
- ✅ Configuration: `constant_voltage_mode = false`, `debounce_ms = 100-150`

### Expected Performance
- Detection rate: 8 detections/second (at 24 FPS)
- Latency measurement: Accurate to ~50ms
- Resource usage: MEDIUM (33% of constant voltage)

---

## Pattern C: Custom Sparse Sampling

### Characteristics
- **Frame Gap:** Variable or large fixed gap (>5 frames)
- **Time Gap:** Variable or >200ms
- **Coverage:** <25%
- **Use Case:** Long-term monitoring, performance testing, resource-constrained systems

### Detection Pattern Example (Every 75th Frame)
```
Frame    0: ✅ detected
Frame   75: ✅ detected (gap: 75 frames, 2,500ms)
Frame  150: ✅ detected (gap: 75 frames, 2,500ms)
Frame  225: ✅ detected (gap: 75 frames, 2,500ms)
Frame  300: ✅ detected (gap: 75 frames, 2,500ms)
```

### Identification Criteria
- ✅ Frame gaps > 5
- ✅ Average time gap: >200ms
- ✅ Coverage: <25%
- ✅ Configuration: Custom sampling logic

### Expected Performance
- Detection rate: Variable (depends on gap)
- Latency measurement: Not accurate (too sparse)
- Resource usage: LOW (minimal CPU/memory/storage)

---

## Diagnostic Decision Tree

```
START
  |
  ├─ Coverage > 90%? ──YES─→ CONSTANT VOLTAGE MODE
  |                           (Pattern A)
  |
  ├─ Coverage 25-40%? ──YES─→ Check frame gaps
  |                     |
  |                     ├─ Most gaps = 3? ──YES─→ DEBOUNCE (3x)
  |                     |                          (Pattern B)
  |                     |
  |                     └─ Most gaps = 5? ──YES─→ DEBOUNCE (5x)
  |                                                (Pattern B variant)
  |
  └─ Coverage < 25%? ──YES─→ Check gap consistency
                       |
                       ├─ Consistent large gap? ──YES─→ SPARSE SAMPLING
                       |                                 (Pattern C)
                       |
                       └─ Random/variable gaps? ──YES─→ FRAME DROPS
                                                         (Performance issue)
```

---

## SQL Queries for Pattern Detection

### Check Frame Gap Distribution
```sql
WITH frame_gaps AS (
    SELECT
        frame_number - LAG(frame_number) OVER (ORDER BY frame_number) as gap
    FROM detection_events
    WHERE test_session_id = '[SESSION_ID]'
)
SELECT
    gap,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
FROM frame_gaps
WHERE gap IS NOT NULL
GROUP BY gap
ORDER BY count DESC;
```

### Calculate Coverage
```sql
SELECT
    MIN(frame_number) as first_frame,
    MAX(frame_number) as last_frame,
    COUNT(*) as detected_frames,
    (MAX(frame_number) - MIN(frame_number) + 1) as total_frames,
    ROUND(100.0 * COUNT(*) / (MAX(frame_number) - MIN(frame_number) + 1), 2) as coverage_pct
FROM detection_events
WHERE test_session_id = '[SESSION_ID]';
```

### Check Time Gaps
```sql
WITH time_gaps AS (
    SELECT
        (timestamp - LAG(timestamp) OVER (ORDER BY frame_number)) * 1000 as gap_ms
    FROM detection_events
    WHERE test_session_id = '[SESSION_ID]'
)
SELECT
    ROUND(AVG(gap_ms), 2) as avg_gap_ms,
    ROUND(MIN(gap_ms), 2) as min_gap_ms,
    ROUND(MAX(gap_ms), 2) as max_gap_ms,
    COUNT(*) as gap_count
FROM time_gaps
WHERE gap_ms IS NOT NULL;
```

---

## Configuration Examples

### Constant Voltage Mode
```env
LABJACK_USE_STREAM_MODE=true
LABJACK_SAMPLE_RATE=200
LABJACK_DEBOUNCE_MS=0
LABJACK_VOLTAGE_THRESHOLD=3.3
```

### Debounce Mode (3x)
```env
LABJACK_USE_STREAM_MODE=true
LABJACK_SAMPLE_RATE=200
LABJACK_DEBOUNCE_MS=100
LABJACK_VOLTAGE_THRESHOLD=3.3
```

### Sparse Sampling
```env
LABJACK_USE_STREAM_MODE=false
LABJACK_SAMPLE_RATE=1  # 1 Hz (once per second)
LABJACK_DEBOUNCE_MS=0
LABJACK_VOLTAGE_THRESHOLD=3.3
```

---

## Common Issues and Diagnosis

### Issue 1: Expected 100%, Got 33%
**Symptoms:**
- Frame gaps = 3
- Coverage = 33%
- Time gaps = ~125ms

**Diagnosis:** Debounce mode is active when constant voltage was expected

**Solution:**
```env
# Change in .env:
LABJACK_DEBOUNCE_MS=0  # Was: 100

# Or in test configuration:
constant_voltage_mode = true
```

### Issue 2: Expected 33%, Got 1-5%
**Symptoms:**
- Large frame gaps (>10)
- Coverage < 5%
- Irregular timing

**Diagnosis:** Performance bottleneck or incorrect sampling configuration

**Solution:**
1. Check CPU usage during test
2. Verify video decode performance
3. Check LabJack sample rate
4. Review logs for frame drop warnings

### Issue 3: Inconsistent Gaps
**Symptoms:**
- Frame gaps vary wildly (1, 5, 20, 3, 15...)
- Coverage unpredictable
- Time gaps inconsistent

**Diagnosis:** System performance issue or resource contention

**Solution:**
1. Monitor system resources during test
2. Close other applications
3. Reduce video resolution
4. Increase hardware resources

---

## Performance Comparison

| Pattern | CPU Usage | Memory Usage | Storage/Hour | Latency Accuracy |
|---------|-----------|--------------|--------------|------------------|
| Constant Voltage | HIGH (100%) | HIGH | 10 GB | ±1ms |
| Debounce (3x) | MEDIUM (33%) | MEDIUM | 3.3 GB | ±50ms |
| Debounce (5x) | LOW (20%) | LOW | 2 GB | ±100ms |
| Sparse (75x) | MINIMAL (1.4%) | MINIMAL | 140 MB | Not accurate |

---

## Expected Results by Mode

### 24 FPS Video, 10 Second Duration

| Mode | Expected Detections | Frame Pattern | Time Between |
|------|--------------------|--------------|-|
| Constant Voltage | 240 | 0,1,2,3,4,5... | 42ms |
| Debounce (3x) | 80 | 0,3,6,9,12,15... | 125ms |
| Debounce (5x) | 48 | 0,5,10,15,20,25... | 208ms |
| Sparse (every 75) | 3 | 0,75,150,225 | 2.5s |

---

## Validation Checklist

Before analyzing a session, verify:

- [ ] Session ID exists in database
- [ ] Detection events present (COUNT > 0)
- [ ] Frame numbers populated
- [ ] Timestamps valid
- [ ] Configuration metadata available
- [ ] Ground truth data available (if needed)

---

## Quick Reference Card

**To determine pattern from 10 consecutive frames:**

```
Gap Pattern | Classification
------------|---------------
1,1,1,1,1,1,1,1,1 | Constant Voltage ✓
3,3,3,3,3,3,3,3,3 | Debounce (3x) ✓
5,5,5,5,5,5,5,5,5 | Debounce (5x) ✓
75,75,75,75,75... | Sparse Sampling ✓
1,1,3,1,5,2,1,3,1 | Frame Drops ⚠
```

**To determine pattern from coverage:**

```
Coverage | Most Likely Pattern
---------|--------------------
> 90%    | Constant Voltage
30-40%   | Debounce (3x)
15-25%   | Debounce (5x)
< 5%     | Sparse Sampling or Issue
```

---

**Document Version:** 1.0
**Last Updated:** 2025-11-24
**See Also:**
- `DETECTION_PATTERN_ANALYSIS_METHODOLOGY.md` - Full analysis methodology
- `SESSION_ddd37359_ANALYSIS_REPORT.md` - Example analysis report
