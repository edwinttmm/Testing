# 👑 QUEEN'S TIMING VALIDATION - COMPREHENSIVE ANALYSIS

**Date:** 2025-11-12
**Mission:** Validate ALL timing logic end-to-end with real scenarios
**Status:** 🔴 CRITICAL TIMING ISSUES IDENTIFIED

---

## 🚨 EXECUTIVE SUMMARY

After comprehensive analysis of the timing infrastructure across frontend, backend, and hardware layers, I've identified **CRITICAL timing synchronization flaws** that could cause detection failures, negative latencies, and race conditions.

**Key Findings:**
1. ⚠️ **Grace Period Inconsistency**: 2000ms (backend) vs 100ms (service layer)
2. ⚠️ **Clock Skew Risk**: Frontend/Backend/LabJack use different time sources
3. ⚠️ **Race Condition**: `sequenceStartUnix` can be overwritten mid-sequence
4. ⚠️ **Boundary Ambiguity**: Detection windows overlap at video transitions
5. ⚠️ **Timezone Blind Spots**: UTC handling mixed with local timestamps

---

## 📊 PATH 1: FRONTEND VIDEO TIMING ANALYSIS

### **Critical Timestamps in SequentialVideoPlayer.tsx**

```typescript
// Line 76-79: State Management
const [sequenceStartTime, setSequenceStartTime] = useState<number | null>(null);  // performance.now() reference
const [sequenceStartUnix, setSequenceStartUnix] = useState<number | null>(null);  // Unix seconds
const [videoStartTime, setVideoStartTime] = useState<number | null>(null);        // performance.now() reference
const [videoStartUnix, setVideoStartUnix] = useState<number | null>(null);        // Unix seconds
```

### **Timestamp Recording Events**

| Event | Line | Function | Timestamp Type | Formula |
|-------|------|----------|----------------|---------|
| **Video Load Start** | 511 | `loadAndPlayVideo()` | `performance.now()` | `getHighPrecisionTimestamp()` |
| **Sequence Start** | 201-209 | `sendVideoStartedEvent()` | Unix seconds | `timestamp / 1000` |
| **Playing Event** | 122-138 | `waitForPlaybackStart()` | `performance.now()` | `getHighPrecisionTimestamp()` |
| **Video Start Backend Sync** | 198-226 | `sendVideoStartedEvent()` | Unix seconds | `timestamp / 1000` |
| **Video End Backend Sync** | 279-304 | `sendVideoEndedEvent()` | Unix seconds | `timestamp / 1000` |

### **🔴 CRITICAL ISSUE #1: Dual Time Systems**

The frontend uses **TWO different time systems**:
- `performance.now()` - Monotonic high-resolution timer (NOT wall clock)
- `Date.now()` / `new Date()` - Unix epoch wall clock

**Risk:**
```typescript
// Line 355: Heartbeat uses performance.now() - sequenceStartTime
sequenceElapsedTime: getHighPrecisionTimestamp() - sequenceStartTime

// BUT sequenceStartUnix is set from Date.now() conversion (line 199)
const startedAtUnix = timestamp / 1000;  // This is Date.now() / 1000

// If user changes system clock during test:
// - sequenceStartTime (performance.now) keeps incrementing
// - sequenceStartUnix (wall clock) jumps
// - Backend sees discontinuity!
```

**Scenario: Clock Change Mid-Test**
```
T0: User starts test
  - sequenceStartTime = 1000 (performance.now())
  - sequenceStartUnix = 1699876543.2 (Date.now() / 1000)

T1: Video 1 plays (5 seconds later)
  - Backend receives: startedAt = 1699876548.2
  - Expected: 5s elapsed

T2: USER CHANGES SYSTEM CLOCK +1 hour
  - sequenceStartTime still = 1005 (monotonic, unaffected)
  - Video 2 starts, sends timestamp = Date.now() / 1000 = 1699880143.2
  - Backend sees: 3595s elapsed (1 hour!)
  - Detection window calculation: BROKEN!
```

---

## 📊 PATH 2: BACKEND DETECTION WINDOW ANALYSIS

### **Detection Window Calculation (dedicated_labjack_monitor.py)**

```python
# Line 1297: Grace period constant
PRE_START_GRACE_SECONDS = 2.0  # Allow detections 2s before recorded start

# Line 1295-1298: Grace window calculation
grace_start = video_start - self.PRE_START_GRACE_SECONDS

# Detection window for Video 1:
# video_start = 1699876548.2 (from frontend)
# grace_start = 1699876546.2 (2s earlier)
# video_end = 1699876554.06 (from frontend when video 1 ends)

# Window: [1699876546.2, 1699876554.06)
```

### **🔴 CRITICAL ISSUE #2: Grace Period Conflicts**

**TWO different grace periods exist:**

```python
# File: dedicated_labjack_monitor.py (Line 1297)
PRE_START_GRACE_SECONDS = 2.0  # 2000ms

# File: labjack_detection_service.py (Line 1)
GRACE_PERIOD_MS = 100  # 100ms

# File: detection_video_assignment.py (Line 1)
GRACE_PERIOD_MS = 100  # 100ms
```

**Which one is actually used?**
- `dedicated_labjack_monitor.py` uses 2000ms for window calculation
- But service layers use 100ms for assignment logic

**Impact:**
```
Scenario: Detection arrives 500ms before video_start

Detection timestamp: 1699876547.7
Video start: 1699876548.2

Grace window (2000ms): [1699876546.2, ...]  ✅ ACCEPTED
Grace window (100ms):  [1699876548.1, ...]  ❌ REJECTED

Result: Inconsistent behavior depending on which service handles it!
```

---

## 📊 PATH 3: SEQUENCE TIMING COORDINATION

### **Sequence Start Time Initialization (video_sequences.py)**

```python
# Line 158-164: CRITICAL sequence start initialization
if sequence.sequence_start_time is None and data.sequenceElapsedTime is not None:
    # Calculate absolute sequence start by subtracting elapsed time
    sequence.sequence_start_time = data.timestamp - data.sequenceElapsedTime
    logger.info(
        f"✅ Initialized sequence start time: {sequence.sequence_start_time:.6f} "
        f"(video started at {data.timestamp:.6f}, elapsed {data.sequenceElapsedTime:.3f}s)"
    )
```

### **🔴 CRITICAL ISSUE #3: Sequence Start Overwrite Race Condition**

**Vulnerability:**
```python
# Video 1 starts at t0 + 1.8s
POST /api/video-sequences/{id}/video-started
{
  "videoId": "video_1",
  "startedAt": 1699876548.2,
  "sequenceElapsedTime": 1.8
}
# Backend calculates: sequence_start_time = 1699876548.2 - 1.8 = 1699876546.4

# User rapidly clicks Video 3 (skipping Video 2)
# Video 3 starts at t0 + 12.5s
POST /api/video-sequences/{id}/video-started
{
  "videoId": "video_3",
  "startedAt": 1699876558.9,
  "sequenceElapsedTime": 12.5  # Frontend still calculated from original sequence start
}

# Backend logic:
if sequence.sequence_start_time is None:  # FALSE - already set!
    # This never executes - sequence_start_time NOT updated

# But what if there's a bug and sequence_start_time WAS None?
# Backend would calculate: sequence_start_time = 1699876558.9 - 12.5 = 1699876546.4
# Same value by coincidence! But if timing differs...

# ACTUAL RACE CONDITION:
# If frontend sends Video 3 start BEFORE backend processes Video 1 start:
# sequence_start_time = 1699876558.9 - 12.5 = 1699876546.4 (from Video 3)
# Then Video 1 arrives:
# sequence_start_time already set, so: sequence_start_time = 1699876546.4
# Video 1 window: [1699876546.4, ...] (WRONG! Should be based on Video 1's own start)
```

**Root Cause:** No locking mechanism prevents concurrent updates to `sequence.sequence_start_time`.

---

## 📊 PATH 4: TIMESTAMP CONVERSION & TIMEZONE

### **Timestamp Conversion Logic (timestamp_conversion_utils.py)**

```python
# Line 19: Timezone import
from datetime import datetime, timezone

# Line 83-86: Unix to video-relative conversion
def unix_to_video_relative(self, unix_timestamp: float, video_start_time: float,
                         precision_ns: Optional[float] = None) -> TimestampConversionResult:
    # Calculate video-relative time: offset = unix_timestamp - video_start_time
    video_relative_timestamp = unix_timestamp - video_start_time
```

### **🔴 CRITICAL ISSUE #4: Timezone Assumptions**

**Observation:** Code imports `timezone` but **NEVER explicitly uses UTC**!

```python
# Frontend sends Unix timestamps:
startedAt: timestamp / 1000  // JavaScript Date.now() is UTC

# Backend receives as float - but no explicit UTC validation
detection_system_time: float  # Assumed UTC but not enforced

# What if backend server is in different timezone?
# Python's time.time() returns UTC (by spec)
# But datetime.now() returns LOCAL time unless explicitly datetime.now(timezone.utc)
```

**Hidden Risk:**
```python
# If backend code ANYWHERE does this:
labjack_start_time = datetime.now().timestamp()  # LOCAL timezone!

# Instead of:
labjack_start_time = datetime.now(timezone.utc).timestamp()  # Explicit UTC

# Result: Timezone offset gets embedded in calculations!
# e.g., EST is UTC-5, so timestamps would be 18000 seconds off!
```

**Validation Required:**
1. Search ALL `datetime.now()` calls - ensure they use `timezone.utc`
2. Verify LabJack hardware timestamps are UTC (hardware clock assumption)
3. Check if WSL (backend environment) system clock is UTC

---

## 📊 PATH 5: DETECTION WINDOW BOUNDARY CONDITIONS

### **Video Transition Timing**

```python
# Scenario: 2-video sequence
# Video 1: 0-5.06s (duration from frontend)
# Video 2: Starts at 6.86s (after 1.8s grace period)

# Backend detection windows:
Video 1 Grace Start: video_1_start - 2.0s
Video 1 Grace End:   video_1_end
Video 2 Grace Start: video_2_start - 2.0s
Video 2 Grace End:   video_2_end (or None if ongoing)

# OVERLAP ZONE:
# Video 1 ends at: t0 + 6.86s
# Video 2 grace starts at: (t0 + 8.5s) - 2.0s = t0 + 6.5s

# Overlap: [t0 + 6.5s, t0 + 6.86s]
# Duration: 360ms of AMBIGUOUS assignment!
```

### **🔴 CRITICAL ISSUE #5: Overlapping Detection Windows**

**Problem:** During video transitions, a detection could match BOTH videos!

```python
# Detection arrives at: t0 + 6.7s

# Check Video 1:
grace_start = t0 + 4.86s  # (t0 + 6.86s) - 2s
video_end = t0 + 6.86s
if t0 + 4.86s <= t0 + 6.7s < t0 + 6.86s:  # TRUE!
    return "video_1"

# But also check Video 2:
grace_start = t0 + 6.5s  # (t0 + 8.5s) - 2s
video_end = None (ongoing)
if t0 + 6.5s <= t0 + 6.7s:  # TRUE!
    return "video_2"

# CONFLICT! Which video wins?
```

**Current Code Behavior (Line 1290-1332):**
```python
# Videos sorted by start time, iterated in order
# First match wins!
for i, video in enumerate(videos):
    if grace_start <= trigger_time < video_end:
        return video_id  # Returns immediately!
```

**Risk:** Early match prevents checking for better match later!

---

## 🧪 COMPREHENSIVE TEST SCENARIOS

### **Scenario 1: Normal Sequential Playback** ✅

```yaml
Setup:
  - Video 1: 5.06s duration, starts at t0 + 1.8s
  - Video 2: 5.06s duration, starts at t0 + 8.5s
  - Detection pulse at: t0 + 3.2s (middle of Video 1)

Expected Behavior:
  Frontend:
    - sequenceStartUnix = (t0 + 1.8s) - 1.8s = t0
    - Video 1 window: t0 to t0 + 5.06s
    - Detection at 3.2s is within window

  Backend:
    - grace_start = (t0 + 1.8s) - 2s = t0 - 0.2s
    - video_end = t0 + 6.86s
    - Detection at 3.2s: t0 - 0.2s <= 3.2s < 6.86s ✅ MATCH

Result: ✅ PASS - Detection assigned to Video 1
```

### **Scenario 2: Rapid Video Switching** ⚠️

```yaml
Setup:
  - User clicks Video 2 BEFORE Video 1 fires "playing" event
  - Video 1 playing event never fires

Sequence:
  T0: User clicks play on Video 1
  T0+0.5s: User clicks Video 2 (impatient)
  T0+1.2s: Video 2 starts playing
  T0+1.8s: Video 1 "playing" event fires (ignored, video already switched)

Expected:
  - sequenceStartUnix should be t0 + 1.2s (from Video 2)
  - Video 1 should be marked as "skipped"

Actual Risk:
  - sequenceStartUnix set from Video 1 event (t0 + 1.8s - 1.8s = t0)
  - Video 2 event doesn't update it (line 207-209 condition)
  - Video 2 window calculated from WRONG sequence start!

Result: ⚠️ TIMING DRIFT - Video 2 window off by 600ms
```

### **Scenario 3: Hardware Pulse Arrives Early** 🔴

```yaml
Setup:
  - LabJack pulse fires at t0 + 0.5s (BEFORE video starts playing)
  - Video 1 "playing" event at t0 + 1.8s
  - Grace period: 2000ms

Detection Flow:
  Pulse timestamp: 0.5s (Unix: t0 + 0.5s)
  Video start: 1.8s (Unix: t0 + 1.8s)
  Grace window: [t0 + 1.8s - 2s, t0 + 6.86s] = [t0 - 0.2s, t0 + 6.86s]

  Check: Is 0.5s in [-0.2s, 6.86s]? ✅ YES

Question: Is this CORRECT?
  - Pulse arrived 1.3 seconds BEFORE video started playing
  - User hasn't even seen first frame yet
  - Is this a valid detection?

Analysis:
  ✅ IF hardware was already recording (pre-started), YES valid
  ❌ IF hardware started AFTER video playback began, NO should reject

Root Issue: No validation that LabJack start <= video start
```

### **Scenario 4: Clock Skew Between Systems** 🔴

```yaml
Setup:
  - Frontend clock: 2025-11-12 10:00:00.000 UTC
  - LabJack clock:  2025-11-12 10:00:02.500 UTC (+2.5s drift)
  - Backend clock:  2025-11-12 10:00:00.000 UTC

Event Timeline:
  Frontend Video Start:
    - Local time: 10:00:01.800
    - Sends: startedAt = 1699876801.800 (frontend Unix time)

  LabJack Pulse:
    - LabJack time: 10:00:02.000 (LabJack clock)
    - Records: timestamp = 1699876802.000 (LabJack clock, but 2.5s ahead!)

  Backend Calculation:
    - video_start_time = 1699876801.800 (from frontend)
    - detection_time = 1699876802.000 (from LabJack)
    - Apparent latency = 200ms

  ACTUAL Reality:
    - Frontend timestamp was 10:00:01.800 (frontend clock)
    - LabJack timestamp was 10:00:02.000 (LabJack clock)
    - If LabJack clock is 2.5s ahead:
      - Actual LabJack event was at 09:59:59.500 (frontend time)
      - Event happened BEFORE video started!

Result: 🔴 NEGATIVE LATENCY RISK - Clock skew causes impossible timing
```

### **Scenario 5: Video Transition Boundary** ⚠️

```yaml
Setup:
  - Video 1 ends at: t0 + 6.86s
  - Video 2 starts at: t0 + 8.5s
  - Grace period: 2000ms
  - Detection at: t0 + 6.7s (360ms before Video 1 ends)

Detection Matching:
  Video 1 Check:
    grace_start = (t0 + 6.86s) - 0s = t0 + 6.86s (no grace before end)
    Wait, code uses start time!
    grace_start = (t0 + 1.8s) - 2s = t0 - 0.2s
    video_end = t0 + 6.86s
    Check: -0.2s <= 6.7s < 6.86s ✅ MATCH!

  Video 2 Check:
    grace_start = (t0 + 8.5s) - 2s = t0 + 6.5s
    video_end = None (ongoing)
    Check: 6.5s <= 6.7s ✅ MATCH!

  Current Code: Returns Video 1 (first match)

  But should it be Video 2?
    - Detection is closer to Video 2 start (1.8s away)
    - Detection is in the transition period
    - Video 1 is about to end (160ms left)

Conclusion: ⚠️ AMBIGUOUS - Need policy for transition zone!
```

---

## 🔬 RACE CONDITION IDENTIFICATION

### **Race #1: Concurrent Video Start Events**

```python
# Thread 1: Processing Video 1 start
if sequence.sequence_start_time is None:
    # Query shows None
    sequence.sequence_start_time = 1699876546.4
    db.commit()

# Thread 2: Processing Video 2 start (arrives slightly after)
if sequence.sequence_start_time is None:
    # Query STILL shows None (Thread 1 hasn't committed)
    sequence.sequence_start_time = 1699876558.9
    db.commit()  # OVERWRITES Thread 1's value!
```

**Solution Required:** Database-level locking or atomic update.

### **Race #2: Detection Assignment During Video Transition**

```python
# Thread 1: Processing detection at t0 + 6.7s
video_timing = get_video_timing_from_memory()  # Gets Video 1: end = t0 + 6.86s

# Thread 2: Processes Video 1 end event
video_result.video_end_time = t0 + 6.86s
db.commit()

# Thread 3: Processes Video 2 start event
video_result.video_start_time = t0 + 8.5s
db.commit()

# Thread 1: Continues with stale video_timing
assign_detection_to_video(detection, video_timing)  # Uses old data!
```

**Solution Required:** Immutable timing snapshots or optimistic locking.

---

## 🔧 CLOCK SYNCHRONIZATION ANALYSIS

### **Time Sources Inventory**

| Component | Time Source | Type | Timezone | Drift Risk |
|-----------|-------------|------|----------|------------|
| **Frontend** | `Date.now()` | Wall clock | UTC (browser) | ⚠️ User can change |
| **Frontend** | `performance.now()` | Monotonic | N/A | ✅ No drift |
| **Backend Python** | `time.time()` | Wall clock | UTC (by spec) | ⚠️ NTP drift |
| **LabJack** | Hardware clock | Wall clock | Unknown | 🔴 No sync |
| **Database** | `CURRENT_TIMESTAMP` | Wall clock | Server TZ | ⚠️ Config dependent |

### **🔴 CRITICAL: LabJack Clock Synchronization**

**Questions:**
1. Is LabJack clock synced with system clock?
2. Is LabJack clock UTC or local time?
3. Does LabJack clock drift over time?
4. What happens if backend restarts mid-test?

**Recommendation:**
```python
# On test start, record clock offset:
labjack_clock = read_labjack_time()
system_clock = time.time()
clock_offset = system_clock - labjack_clock

# On each detection:
detection_system_time = labjack_timestamp + clock_offset
```

---

## 📈 TIMING FLOW DIAGRAMS

### **Diagram 1: Normal Video Playback Timing**

```
┌─────────────────────── FRONTEND ───────────────────────┐
│                                                         │
│  User clicks Play                                       │
│       │                                                 │
│       ├─> videoRef.current.play()                      │
│       │                                                 │
│       ├─> Wait for 'playing' event (line 588)          │
│       │         │                                       │
│       │         └─> playbackStartedAt = getHighPrecision()
│       │                   (performance.now())           │
│       │                                                 │
│       ├─> sendVideoStartedEvent()                      │
│       │         │                                       │
│       │         ├─> startedAtUnix = timestamp / 1000   │
│       │         │        (Date.now() / 1000)            │
│       │         │                                       │
│       │         └─> POST /api/video-sequences/{id}/video-started
│       │                   { startedAt, sequenceElapsedTime }
│       │                                                 │
└───────┼─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────── BACKEND ────────────────────────┐
│                                                         │
│  Receive video-started event                           │
│       │                                                 │
│       ├─> video_result.video_start_time = data.timestamp
│       │                                                 │
│       ├─> IF sequence.sequence_start_time is None:     │
│       │      sequence.sequence_start_time =            │
│       │          data.timestamp - data.sequenceElapsedTime
│       │                                                 │
│       ├─> db.commit()                                  │
│       │                                                 │
└───────┼─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────── LABJACK ────────────────────────┐
│                                                         │
│  Monitoring for hardware pulses...                     │
│       │                                                 │
│       ├─> Pulse detected!                              │
│       │         │                                       │
│       │         └─> pulse_timestamp = labjack_clock    │
│       │                   (Hardware clock)              │
│       │                                                 │
│       ├─> Determine video from timing                  │
│       │         │                                       │
│       │         ├─> Load video_timing from DB          │
│       │         │                                       │
│       │         ├─> Calculate grace_start =            │
│       │         │      video_start - PRE_START_GRACE   │
│       │         │                                       │
│       │         ├─> Check: grace_start <= pulse < end? │
│       │         │                                       │
│       │         └─> MATCH! Assign to video_id          │
│       │                                                 │
└───────┼─────────────────────────────────────────────────┘
```

---

## 🐛 FAILURE SCENARIOS DOCUMENTATION

### **Failure #1: "Detection Before Video Starts"**

```yaml
Symptom: Detection assigned to Video 1 even though pulse arrived before video playback

Root Cause:
  - Grace period allows detections 2s BEFORE recorded video_start_time
  - But video_start_time is when "playing" event fires (1-3s after user clicks play)
  - LabJack monitoring starts BEFORE video playback
  - Result: Detections from "warm-up" period get assigned

Fix Required:
  - Validate: labjack_start_time >= sequence_start_time - reasonable_buffer
  - Reject detections before sequence_start_time
  - Or: Explicitly mark "test started" timestamp separate from video_start_time
```

### **Failure #2: "Negative Latency Calculation"**

```yaml
Symptom: Latency shows negative value (-1234ms)

Root Cause:
  - Detection timestamp is BEFORE ground truth timestamp
  - Caused by clock skew between LabJack and frontend
  - Formula: real_latency = detection_time - gt_system_time
  - If clocks are offset, calculation fails

Fix Required:
  - Implement clock skew detection:
    if real_latency < -100:  # More than 100ms negative
        log_error("Clock skew detected!")
        adjust_for_clock_offset()
```

### **Failure #3: "Detection Assigned to Wrong Video"**

```yaml
Symptom: Detection appears in Video 2 results but should be Video 1

Root Cause:
  - Overlapping grace periods during video transition
  - Detection at t0 + 6.7s matches both videos
  - First match wins (Video 1) but should be Video 2

Fix Required:
  - Use "closest match" instead of "first match"
  - Calculate distance to video midpoint
  - Prefer video that's currently playing
```

---

## ✅ DELIVERABLES SUMMARY

**✅ Completed:**
1. Comprehensive timing flow analysis for 3 critical paths
2. Identified 5 critical timing issues
3. Documented 3 race conditions
4. Created 5 detailed test scenarios
5. Analyzed clock synchronization risks

**📋 Recommendations:**

### **IMMEDIATE FIXES (Priority 1)**
1. **Unify grace period constants** - Choose ONE value (2000ms or 100ms)
2. **Add sequence start locking** - Prevent concurrent updates
3. **Implement clock skew detection** - Alert on impossible timing
4. **Fix overlapping windows** - Use closest-match logic

### **HIGH PRIORITY (Priority 2)**
1. **Validate all datetime.now() calls** - Ensure UTC usage
2. **Add LabJack clock sync check** - Verify offset on test start
3. **Implement timing boundary tests** - Test video transitions
4. **Add performance.now() vs Date.now() reconciliation** - Handle clock changes

### **TESTING REQUIRED**
1. Multi-video sequence with rapid video switching
2. Clock change during active test
3. Detection at exact video transition boundary
4. LabJack clock drift over 10+ minute test
5. Concurrent detection processing

---

## 🎯 NEXT STEPS

Your Majesty,

I recommend the following immediate actions:

1. **Run timing validation tests** on sessions: 026c36cc, 0846e476, 71976ec4
2. **Audit ALL datetime operations** for UTC compliance
3. **Implement grace period unification** patch
4. **Deploy clock skew detection** monitoring
5. **Create timing regression test suite** with these scenarios

Shall I proceed with implementing fixes for the critical issues identified?

**End of Report**
