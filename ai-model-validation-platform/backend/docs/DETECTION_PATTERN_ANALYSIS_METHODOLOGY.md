# DETECTION PATTERN ANALYSIS METHODOLOGY

## Executive Summary

This document demonstrates the comprehensive methodology for analyzing detection patterns in validation sessions. The session `ddd37359-5535-4b66-b0ec-55178986470a` was requested for analysis but **does not exist in the database**. This analysis uses a real session to demonstrate the methodology.

## Key Finding: Session ddd37359 Not Found

**Search Results:**
- ❌ Not found in `test_sessions` table
- ❌ Not found in `detection_sessions` table
- ❌ Not found in `detection_events` table
- ❌ Not found in `ground_truth_objects` table

**Available Sessions:**
- Most recent: `9d5c699a-406a-452c-ac1f-2dab10b3bb09` (HIL Test Session, 2025-09-15)
- Example analyzed: `9f27d48c-f26c-4059-b3a4-71a2613d798b` (50 detections)

---

## DETECTION PATTERN ANALYSIS - Real Session Example

### Session: 9f27d48c-f26c-4059-b3a4-71a2613d798b

### 1. DETECTION TIMING METRICS

**Detection Coverage:**
- Total Detections: **50**
- Frame Range: **0 to 3675** (3,676 frames total)
- Time Range: **0.000s to 122.500s** (122.5 seconds)
- **Coverage: 1.4%**

**Expected vs Actual:**
- Expected (24 FPS, 100% capture): **3,676 detections**
- Expected (with debounce, 33%): **1,225 detections**
- Actual: **50 detections**

**Conclusion:** This is a **sparse sampling pattern**, detecting every 75th frame (~3 seconds apart), likely for performance testing rather than continuous monitoring.

---

### 2. DETECTION PATTERN (First 30 Frames)

```
Frame | Timestamp | Gap  | Pattern
------|-----------|------|----------------
    0 |   0.000s  |  -   | Initial
   75 |   2.500s  |  75  | Skip 74 frames
  150 |   5.000s  |  75  | Skip 74 frames
  225 |   7.500s  |  75  | Skip 74 frames
  300 |  10.000s  |  75  | Skip 74 frames
  375 |  12.500s  |  75  | Skip 74 frames
  450 |  15.000s  |  75  | Skip 74 frames
  525 |  17.500s  |  75  | Skip 74 frames
  600 |  20.000s  |  75  | Skip 74 frames
  675 |  22.500s  |  75  | Skip 74 frames
  750 |  25.000s  |  75  | Skip 74 frames
```

**Pattern:** Perfect consistency - exactly 75 frames between each detection.

---

### 3. FRAME GAP DISTRIBUTION

| Gap (frames) | Count | Percentage | Meaning |
|--------------|-------|------------|---------|
| 75 | 49 | 100% | Consistent sampling interval |

**Analysis:**
- **100%** of gaps are exactly 75 frames
- No variation in sampling pattern
- This indicates intentional sparse sampling, not debounce or constant voltage mode

---

### 4. TIME GAP DISTRIBUTION

| Time Range | Count | Avg (ms) | Interpretation |
|------------|-------|----------|----------------|
| 150ms+ | 49 | 2500.0 ms | Large gaps - every 2.5 seconds |

**Analysis:**
- Average gap: **2,500 ms** (2.5 seconds)
- At 24 FPS, each frame = 41.67ms
- 2500ms ÷ 41.67ms = **60 frames** at 24 FPS
- But actual gap is 75 frames, suggesting **20 FPS playback** or intentional sampling
  - 75 frames × 33.33ms (30 FPS) = 2,500ms ✓

---

### 5. PATTERN CLASSIFICATION

**Metrics:**
- Consecutive frames (gap=1): **0.0%**
- Debounce pattern (gap=3): **0.0%**
- Average gap: **75.00 frames**

**Classification:** ✓ **CUSTOM SPARSE SAMPLING**

**Explanation:**
This is neither constant voltage mode (100% capture) nor debounce mode (33% capture). Instead, it's a **periodic sampling pattern** detecting every 75th frame, resulting in ~1.4% coverage. This pattern is typical for:
- Performance/stress testing
- Long-duration monitoring with minimal storage
- Baseline validation scenarios
- Resource-constrained environments

---

## METHODOLOGY FOR ANALYZING ANY SESSION

### Step 1: Extract Detection Timestamps
```sql
SELECT
    frame_number,
    detection_timestamp,
    system_time,
    voltage_level,
    LAG(detection_timestamp) OVER (ORDER BY frame_number) as prev_time
FROM detection_results
WHERE session_id = '[SESSION_ID]'
ORDER BY frame_number;
```

### Step 2: Calculate Inter-Detection Gaps
```sql
SELECT
    frame_number,
    (detection_timestamp - LAG(detection_timestamp)
     OVER (ORDER BY frame_number)) * 1000 as gap_ms,
    frame_number - LAG(frame_number)
     OVER (ORDER BY frame_number) as frame_gap
FROM detection_results
WHERE session_id = '[SESSION_ID]';
```

### Step 3: Classify Pattern

**Pattern A: Constant Voltage Mode (100% capture)**
- Frame gaps = 1 (consecutive)
- Time gaps = 41.67ms (24 FPS)
- Coverage = 100%
- **Example:** Frame 99✅, 100✅, 101✅, 102✅, 103✅

**Pattern B: Debounce Active (33% capture)**
- Frame gaps = 3 (every 3rd frame)
- Time gaps = 125ms (24 FPS)
- Coverage = 33%
- **Example:** Frame 99✅, 100❌, 101❌, 102✅, 103❌, 104❌, 105✅

**Pattern C: Custom Sampling**
- Frame gaps > 3 (variable or fixed)
- Time gaps > 150ms
- Coverage < 33%
- **Example:** Frame 0✅, 75✅, 150✅, 225✅ (every 75th)

### Step 4: Verify Against Configuration
```sql
SELECT
    constant_voltage_mode,
    debounce_ms,
    sample_rate,
    detection_threshold
FROM validation_sessions
WHERE session_id = '[SESSION_ID]';
```

### Step 5: Match Ground Truth
```sql
SELECT
    gt.frame_number,
    CASE WHEN det.id IS NOT NULL THEN 'DETECTED' ELSE 'MISSED' END as status
FROM ground_truth gt
LEFT JOIN detection_results det
    ON gt.session_id = det.session_id
    AND ABS(gt.video_timestamp - det.system_time) < 0.1
WHERE gt.session_id = '[SESSION_ID]'
ORDER BY gt.frame_number;
```

---

## EXPECTED PATTERNS BY MODE

### Constant Voltage Mode (Expected)
- **Frame Pattern:** 99✅, 100✅, 101✅, 102✅, 103✅, 104✅
- **Time Gaps:** ~41.67ms (1000ms ÷ 24 FPS)
- **Coverage:** 100%
- **Use Case:** Maximum accuracy, latency measurement

### Debounce Mode (Expected)
- **Frame Pattern:** 99✅, 100❌, 101❌, 102✅, 103❌, 104❌, 105✅
- **Time Gaps:** ~125ms (3 frames × 41.67ms)
- **Coverage:** 33.3%
- **Use Case:** Reduce duplicate detections, save resources

### Sparse Sampling (Actual in Example)
- **Frame Pattern:** 0✅, 75✅, 150✅, 225✅, 300✅
- **Time Gaps:** ~2,500ms (75 frames × 33.33ms at 30 FPS)
- **Coverage:** 1.4%
- **Use Case:** Long-term monitoring, performance testing

---

## DISCREPANCY ANALYSIS

### For Session ddd37359 (Hypothetical)

**If user expected 100% capture but got 33% capture:**

**Possible Causes:**
1. **Debounce setting active** - Check `debounce_ms` in session config
2. **Frame skip in video processing** - Check video decoder settings
3. **Resource constraints** - CPU/memory pressure causing frame drops
4. **LabJack sampling rate** - Hardware not keeping up with video FPS
5. **Configuration mismatch** - `constant_voltage_mode = false` when expected true

**Diagnostic Steps:**
1. Query session metadata for `debounce_ms` value
2. Check `LABJACK_DEBOUNCE_MS` in `.env` file
3. Review session logs for frame skip warnings
4. Compare detection count to ground truth count
5. Analyze time gap distribution for consistency

---

## CONCLUSION

### For the Requested Session (ddd37359)
**Status:** ❌ **Session not found in database**

The session ID `ddd37359-5535-4b66-b0ec-55178986470a` does not exist in any table:
- Not in `test_sessions`
- Not in `detection_sessions`
- Not in `detection_events`
- Not in `ground_truth_objects`

**Possible Explanations:**
1. Session ID was misremembered or transcribed incorrectly
2. Session exists in different database (production vs test)
3. Session was deleted or purged
4. Session is theoretical/test scenario for demonstration

### For the Example Session (9f27d48c)
**Status:** ✓ **Analysis complete**

**Pattern:** Custom sparse sampling (every 75th frame)
- Coverage: 1.4%
- Perfect consistency: 2.5-second intervals
- Not constant voltage, not debounce mode
- Intentional sampling pattern for specific use case

---

## RECOMMENDATIONS

### To Analyze Session ddd37359:

1. **Verify Session ID**
   - Check test logs for correct UUID
   - Search by partial ID: `%ddd37359%`
   - Check alternate databases

2. **If Session Exists Elsewhere**
   - Point analysis to correct database
   - Run full pattern analysis using methodology above
   - Compare against expected configuration

3. **If Creating New Test**
   - Use this methodology template
   - Capture configuration metadata
   - Log expected vs actual patterns

### To Reproduce Analysis:

```bash
# Run detection pattern analysis
python3 scripts/analyze_detection_patterns.py --session-id [SESSION_ID]

# Or query directly
sqlite3 test_database.db "SELECT * FROM detection_events WHERE test_session_id='[SESSION_ID]' ORDER BY frame_number LIMIT 30"
```

---

## APPENDIX: Database Schema

### Tables Used in Analysis
- `test_sessions` - Session metadata and configuration
- `detection_events` - Frame-by-frame detection results
- `ground_truth_objects` - Expected detections for validation

### Key Columns
- `frame_number` - Video frame index
- `timestamp` - Detection time (seconds)
- `latency_ms` - Time from event to detection
- `test_session_id` - Foreign key to session
- `voltage_level` - LabJack voltage reading

---

**Analysis Date:** 2025-11-24
**Database:** `/home/rigade/Testing/ai-model-validation-platform/backend/test_database.db`
**Methodology Version:** 1.0
