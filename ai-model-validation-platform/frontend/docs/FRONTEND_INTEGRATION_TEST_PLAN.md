# Frontend Integration Test Plan
**Complete Verification Checklist for All Frontend Fixes**

## Executive Summary

This document provides a comprehensive test plan to verify that all frontend fixes work together correctly. The fixes address:
1. **Ground Truth Metrics Display** - Using backend-calculated values, not recalculating
2. **Multi-Video Aggregation** - Summing metrics across all videos in a sequence
3. **Field Name Normalization** - Handling both snake_case and camelCase variants
4. **Lazy Loading & Data Flow** - Proper detection loading per video
5. **Latency Field Standardization** - Using `actual_latency_ms` consistently

---

## Test Scenario 1: Single Video Session

### Setup
- Session with **1 video**
- Backend provides `ground_truth_comparison` at session level
- Detection events have `actual_latency_ms` field (30-150ms range)

### Expected Behavior

#### ✅ Ground Truth Cards Display
```typescript
// Backend Response Structure
{
  "ground_truth_comparison": {
    "true_positives": 59,
    "false_positives": 6,
    "false_negatives": 455,
    "precision": 90.8,
    "recall": 11.5,
    "f1_score": 20.4
  }
}

// Expected UI Display
- F1 Score: 20.4% (displayed prominently)
- Precision: 90.8% (TP/Total Detections)
- Recall: 11.5% (TP/Ground Truth Events)
- TP: 59, FP: 6, FN: 455
```

**Verification Points:**
- [ ] Ground truth cards show **exact** backend values (no recalculation)
- [ ] Precision formula: `59 / (59 + 6) = 90.8%`
- [ ] Recall formula: `59 / (59 + 455) = 11.5%`
- [ ] F1 Score formula: `2 * (90.8 * 11.5) / (90.8 + 11.5) = 20.4%`
- [ ] No discrepancies between displayed and backend values

#### ✅ Latency Display
```typescript
// Detection Event Structure
{
  "actual_latency_ms": 87.5,  // PRIMARY field
  "detection_time_ms": 87.5,  // Fallback
  "voltage": 3.3,
  "passed": true
}

// Expected UI Display
- Detection Latency: 87ms (avg across all detections)
- Range: 30-150ms
- Each detection row shows actual_latency_ms value
```

**Verification Points:**
- [ ] Latency values in 30-150ms range (not 870ms)
- [ ] `actual_latency_ms` field used (not deprecated fields)
- [ ] No startup delay included in detection latency
- [ ] Video startup delay shown separately (if available)

#### ✅ Detection Table
```typescript
// Expected Columns & Data
| # | Video | Time | Voltage | Latency | Matched GT | Result |
|---|-------|------|---------|---------|------------|--------|
| 1 | V1    | 2.5s | 3.3V    | 87ms    | GT-001     | PASS   |
| 2 | V1    | 5.1s | 3.3V    | 92ms    | -          | FAIL   |
```

**Verification Points:**
- [ ] All detection fields display correctly
- [ ] `sequence_id` present (no nulls)
- [ ] `video_id` present (no nulls)
- [ ] Latency shows `actual_latency_ms` values
- [ ] Video column shows "V1" or video name
- [ ] Ground truth match IDs displayed when available

---

## Test Scenario 2: Multi-Video Sequence

### Setup
- Session with **2 videos** (Video 1 + Video 2)
- Backend provides `per_video_results` with individual metrics
- Each video has its own `ground_truth_comparison`

### Expected Behavior

#### ✅ Aggregated Metrics Section
```typescript
// Backend Response Structure
{
  "per_video_results": [
    {
      "video_id": "vid-001",
      "video_name": "video1.mp4",
      "ground_truth_comparison": {
        "true_positives": 25,
        "false_positives": 3,
        "false_negatives": 200
      }
    },
    {
      "video_id": "vid-002",
      "video_name": "video2.mp4",
      "ground_truth_comparison": {
        "true_positives": 34,
        "false_positives": 3,
        "false_negatives": 255
      }
    }
  ]
}

// Expected Aggregated Display
- Total TP: 25 + 34 = 59
- Total FP: 3 + 3 = 6
- Total FN: 200 + 255 = 455
- Aggregated Precision: 59 / (59 + 6) = 90.8%
- Aggregated Recall: 59 / (59 + 455) = 11.5%
- Aggregated F1: 20.4%
```

**Verification Points:**
- [ ] "Aggregated Across All Videos" section appears
- [ ] Ground truth metrics sum correctly from both videos
- [ ] **TP = Video1 TP + Video2 TP** (25 + 34 = 59)
- [ ] **FP = Video1 FP + Video2 FP** (3 + 3 = 6)
- [ ] **FN = Video1 FN + Video2 FN** (200 + 255 = 455)
- [ ] Precision/Recall/F1 calculated from summed values
- [ ] No duplicate counting of detections

#### ✅ Video Selector Dropdown
```typescript
// Expected UI
Select Video: [Video 1: video1.mp4 ▼]
  ├─ Video 1: video1.mp4 (28/228 detections • 85.2ms avg) [COMPLETED]
  └─ Video 2: video2.mp4 (37/292 detections • 89.7ms avg) [COMPLETED]
```

**Verification Points:**
- [ ] Both videos listed in dropdown
- [ ] Each video shows detection count
- [ ] Each video shows average latency
- [ ] Status badge (COMPLETED/PASS/FAIL) displayed
- [ ] Selecting video loads its specific data

#### ✅ Per-Video Ground Truth Metrics
```typescript
// When Video 1 Selected
- Video 1 Ground Truth Metrics:
  - F1 Score: 18.2%
  - Precision: 89.3% (25 TP / 28 Total)
  - Recall: 11.1% (25 TP / 225 GT Events)
  - TP: 25, FP: 3, FN: 200

// When Video 2 Selected
- Video 2 Ground Truth Metrics:
  - F1 Score: 19.1%
  - Precision: 91.9% (34 TP / 37 Total)
  - Recall: 11.8% (34 TP / 289 GT Events)
  - TP: 34, FP: 3, FN: 255
```

**Verification Points:**
- [ ] Switching videos updates ground truth cards
- [ ] Each video shows **its own** metrics (not aggregated)
- [ ] Detection table filters to selected video only
- [ ] Timeline updates to show selected video's detections
- [ ] No cross-video data contamination

---

## Test Scenario 3: Field Name Normalization

### Setup
- Backend sends `snake_case` fields
- Frontend must accept both `snake_case` and `camelCase`

### Expected Behavior

#### ✅ Detection Event Field Mapping
```typescript
// Backend Sends (snake_case)
{
  "actual_latency_ms": 87.5,
  "sequence_id": "seq-123",
  "video_id": "vid-001",
  "ground_truth_match_id": "gt-456",
  "validation_result": "PASS"
}

// Frontend Normalizes To (both variants)
{
  // Snake case (original)
  "actual_latency_ms": 87.5,
  "sequence_id": "seq-123",
  "video_id": "vid-001",
  "ground_truth_match_id": "gt-456",
  "validation_result": "PASS",

  // Camel case (aliases)
  "actualLatencyMs": 87.5,
  "sequenceId": "seq-123",
  "videoId": "vid-001",
  "groundTruthMatchId": "gt-456",
  "validationResult": "PASS"
}
```

**Verification Points:**
- [ ] `hilResultsNormalization.ts` creates both field variants
- [ ] TypeScript types accept both `actual_latency_ms` and `actualLatencyMs`
- [ ] No "undefined" errors in browser console
- [ ] Optional chaining used: `detection?.actual_latency_ms ?? detection?.actualLatencyMs`
- [ ] UI displays all fields correctly regardless of field name variant

#### ✅ Console Error Check
```bash
# Open Browser DevTools Console
# Expected: NO errors about undefined fields

✅ GOOD:
- All data displays correctly
- No TypeScript errors
- No undefined field warnings

❌ BAD:
- "Cannot read property 'actual_latency_ms' of undefined"
- "field.subfield is undefined"
- TypeScript type errors in console
```

**Verification Points:**
- [ ] Zero console errors related to field names
- [ ] All data displays without fallback to defaults
- [ ] Type safety maintained throughout data flow
- [ ] No runtime type coercion warnings

---

## Test Scenario 4: Detection Window Validation

### Setup
- Backend now clamps detections to video playback window
- `video_start_timestamp_epoch_sec` defines window start
- No detections before video start time

### Expected Behavior

#### ✅ Detection Timing Constraints
```typescript
// Video Metadata
{
  "video_start_timestamp_epoch_sec": 1735950000,
  "duration_seconds": 120.5,
  "fps": 24
}

// Valid Detection (within window)
{
  "timestamp": 1735950005.5,  // 5.5s after video start ✅
  "video_relative_timestamp": 5.5,
  "sequence_id": "seq-123",
  "video_id": "vid-001"
}

// Invalid Detection (before video start) - SHOULD NOT EXIST
{
  "timestamp": 1735949995,  // 5s BEFORE video start ❌
  "sequence_id": null,      // Would be null due to clamping
  "video_id": null
}
```

**Verification Points:**
- [ ] No detections with timestamp < `video_start_timestamp_epoch_sec`
- [ ] All detections have valid `sequence_id` (not null)
- [ ] All detections have valid `video_id` (not null)
- [ ] Detection count matches expected for video duration
- [ ] Timeline visualization shows detections within video bounds

#### ✅ Multi-Video Detection Assignment
```typescript
// Video 1 Window: 1735950000 - 1735950065 (65s)
// Video 2 Window: 1735950066 - 1735950186 (120s)

// Video 1 Detections
- Count: 28 detections
- All have video_id = "vid-001"
- All have sequence_id = "seq-123"
- Timestamps: 1735950000 - 1735950065

// Video 2 Detections
- Count: 37 detections
- All have video_id = "vid-002"
- All have sequence_id = "seq-123"
- Timestamps: 1735950066 - 1735950186
```

**Verification Points:**
- [ ] Video 1 detections: `video_id = "vid-001"`
- [ ] Video 2 detections: `video_id = "vid-002"`
- [ ] No overlap in detection timestamps between videos
- [ ] Each video's detections isolated correctly
- [ ] Switching videos updates detection table with correct video's data

---

## Integration Risk Analysis

### Risk 1: Data Flow Breaks

**Scenario:** Backend → API → Normalization → Display
**Failure Mode:** Data lost or transformed incorrectly at any step

**Test:**
```typescript
// 1. Check Network Tab (DevTools)
GET /api/hil-results/enhanced?session_id=XXX
Response: { ground_truth_comparison: { true_positives: 59, ... } }

// 2. Check React DevTools
HILResults Component State:
- enhancedResults.ground_truth_comparison.true_positives === 59 ✅

// 3. Check DOM
<Typography>59</Typography> in Ground Truth TP card ✅
```

**Verification Points:**
- [ ] Backend response matches API documentation
- [ ] React state contains all backend fields
- [ ] DOM displays exact backend values
- [ ] No intermediate transformation errors

### Risk 2: Type Safety Failures

**Scenario:** TypeScript doesn't catch field name mismatches
**Failure Mode:** Runtime errors due to undefined fields

**Test:**
```typescript
// TypeScript should allow both:
const latency1 = detection.actual_latency_ms;  // ✅
const latency2 = detection.actualLatencyMs;    // ✅

// Should NOT error:
const latency = detection.actual_latency_ms ?? detection.actualLatencyMs;  // ✅
```

**Verification Points:**
- [ ] `enhanced-results.ts` types accept both field variants
- [ ] No TypeScript compilation errors
- [ ] Optional chaining prevents runtime crashes
- [ ] Fallback values used appropriately

### Risk 3: Lazy Loading Race Conditions

**Scenario:** Multi-video sequence loads one video at a time
**Failure Mode:** Aggregated metrics incomplete due to missing data

**Test:**
```typescript
// Check aggregatedMetrics calculation
const videos = effectivePerVideoSummaries;  // Should have ALL videos loaded

// Verify:
console.log('Videos loaded:', videos.length);  // Should be 2
console.log('Video 1 TP:', videos[0].ground_truth_comparison.true_positives);  // 25
console.log('Video 2 TP:', videos[1].ground_truth_comparison.true_positives);  // 34
console.log('Aggregated TP:', totalTruePositives);  // 59 = 25 + 34 ✅
```

**Verification Points:**
- [ ] All videos loaded before aggregation
- [ ] `useEffect` preloads all video data
- [ ] `videoGroundTruthMap` populated for all videos
- [ ] `videoDetectionMap` populated for all videos
- [ ] Aggregation waits for complete data

### Risk 4: Backward Compatibility

**Scenario:** Old sessions without new fields
**Failure Mode:** UI crashes or displays incorrectly

**Test:**
```typescript
// Old Session (no ground_truth_comparison)
{
  "session_id": "old-session-123",
  "detection_events": [...],
  // NO ground_truth_comparison field ❌
}

// Expected Behavior:
- Ground truth cards: Hidden or show "No Data" ✅
- Latency cards: Display from detection events ✅
- Detection table: Works with available fields ✅
- No console errors ✅
```

**Verification Points:**
- [ ] Old sessions load without crashing
- [ ] Missing fields handled gracefully
- [ ] Fallback values displayed
- [ ] No "Cannot read property of undefined" errors
- [ ] Optional chaining protects against null/undefined

---

## Manual Testing Instructions

### Step 1: Single Video Session Test

```bash
# 1. Start backend and frontend
cd backend && uvicorn main:app --reload
cd frontend && npm start

# 2. Navigate to single-video test session
http://localhost:3000/hil-results/abc123

# 3. Verify Ground Truth Cards
✅ F1 Score, Precision, Recall displayed
✅ TP/FP/FN breakdown shown
✅ Values match backend API response

# 4. Verify Detection Table
✅ All detections listed
✅ Latency column shows actual_latency_ms
✅ No null sequence_id or video_id
✅ Ground truth match column populated

# 5. Open Browser Console
✅ No errors or warnings
✅ No undefined field messages
```

### Step 2: Multi-Video Sequence Test

```bash
# 1. Navigate to multi-video test session
http://localhost:3000/hil-results/def456

# 2. Verify Aggregated Section
✅ "Aggregated Across All Videos" section appears
✅ Total TP = Video1 TP + Video2 TP
✅ Total FP = Video1 FP + Video2 FP
✅ Total FN = Video1 FN + Video2 FN
✅ Overall pass rate calculated correctly

# 3. Verify Video Selector
✅ Both videos listed
✅ Selecting Video 1 shows Video 1 data only
✅ Selecting Video 2 shows Video 2 data only
✅ Detection table updates on video change

# 4. Verify Per-Video Metrics
✅ Each video shows its own ground truth metrics
✅ Detection count per video is accurate
✅ Latency per video is accurate
✅ No cross-video data contamination
```

### Step 3: Field Name Compatibility Test

```bash
# 1. Check Network Tab (DevTools → Network)
# 2. Find API call: /api/hil-results/enhanced
# 3. View Response JSON

# Verify backend sends snake_case:
{
  "actual_latency_ms": 87.5,
  "sequence_id": "seq-123",
  "video_id": "vid-001"
}

# 4. Check React DevTools
# 5. Find HILResults component state
# 6. Verify state has both field variants:

enhancedResults.detection_events[0] = {
  actual_latency_ms: 87.5,      // ✅ snake_case
  actualLatencyMs: 87.5,         // ✅ camelCase
  sequence_id: "seq-123",        // ✅ snake_case
  sequenceId: "seq-123",         // ✅ camelCase
}

# 7. Check browser console
✅ No TypeScript errors
✅ No undefined field warnings
```

### Step 4: Detection Window Validation Test

```bash
# 1. Check database for video metadata
SELECT video_start_timestamp_epoch_sec, duration_seconds
FROM videos WHERE id = 'vid-001';

# Result: start=1735950000, duration=65s

# 2. Check detections for this video
SELECT timestamp, sequence_id, video_id
FROM detection_events
WHERE video_id = 'vid-001'
ORDER BY timestamp;

# Verify:
✅ All timestamps >= 1735950000
✅ All timestamps <= 1735950065 (start + duration)
✅ No null sequence_id
✅ No null video_id

# 3. Check frontend detection table
✅ Detection count matches backend
✅ All detections within video duration
✅ Timeline shows detections within bounds
```

---

## Expected Behavior Documentation

### Ground Truth Metrics Flow

```
Backend Calculation (services/ground_truth_matching_service.py)
  ↓
  Calculates TP/FP/FN based on detection-to-GT matching
  ↓
  Returns ground_truth_comparison object
  ↓
API Response (/api/hil-results/enhanced)
  ↓
  Includes ground_truth_comparison in response
  ↓
Frontend Normalization (utils/hilResultsNormalization.ts)
  ↓
  Creates both snake_case and camelCase variants
  ↓
React State (pages/HILResults.tsx)
  ↓
  Stores in enhancedResults.ground_truth_comparison
  ↓
Display (components/GroundTruthComparisonCards.tsx)
  ↓
  Shows backend values directly (NO recalculation)
```

### Multi-Video Aggregation Flow

```
Backend Per-Video Results
  ↓
  Each video has its own ground_truth_comparison
  ↓
Frontend Aggregation (useMemo)
  ↓
  Sums TP/FP/FN across all videos
  ↓
  totalTP = video1.TP + video2.TP + ... + videoN.TP
  totalFP = video1.FP + video2.FP + ... + videoN.FP
  totalFN = video1.FN + video2.FN + ... + videoN.FN
  ↓
  Calculates aggregate precision/recall/F1
  ↓
Display in "Aggregated Across All Videos" section
```

### Latency Display Logic

```
Detection Event Structure:
{
  "actual_latency_ms": 87.5,     // PRIMARY - True detection latency
  "detection_time_ms": 87.5,     // FALLBACK
  "voltage": 3.3
}

Frontend Extraction (normalizeDetectionEvent):
  ↓
  const latency = detection.actual_latency_ms
                  ?? detection.actualLatencyMs
                  ?? detection.latency_ms;  // Legacy fallback
  ↓
Display in Detection Latency Card:
  ↓
  Shows average of actual_latency_ms across all detections
  ↓
  "Detection Latency: 87ms" (30-150ms range expected)
```

---

## Integration Test Checklist

### Data Integrity
- [ ] Backend API returns expected structure
- [ ] All required fields present in API response
- [ ] Field values within expected ranges
- [ ] No null/undefined required fields
- [ ] Field name consistency (snake_case from backend)

### Frontend Normalization
- [ ] `hilResultsNormalization.ts` creates both field variants
- [ ] TypeScript types accept both snake_case and camelCase
- [ ] Optional chaining prevents crashes
- [ ] Fallback values work correctly
- [ ] No type coercion warnings

### UI Display
- [ ] Ground truth cards show backend values (no recalculation)
- [ ] Multi-video aggregation sums correctly
- [ ] Latency displays actual_latency_ms values
- [ ] Detection table shows all fields
- [ ] Video selector works for multi-video sequences
- [ ] Timeline visualization renders correctly

### Error Handling
- [ ] Old sessions without new fields load correctly
- [ ] Missing optional fields handled gracefully
- [ ] Network errors don't crash UI
- [ ] Loading states displayed appropriately
- [ ] Error messages are user-friendly

### Browser Console
- [ ] Zero console errors
- [ ] Zero console warnings
- [ ] No undefined field messages
- [ ] No TypeScript type errors
- [ ] No React hook dependency warnings

### Performance
- [ ] Initial page load < 2 seconds
- [ ] Video switching < 500ms
- [ ] Detection table renders smoothly (even with 100+ detections)
- [ ] No unnecessary re-renders
- [ ] Lazy loading works correctly

---

## Known Issues & Workarounds

### Issue 1: Stale Detection Count After Video Switch
**Symptom:** Detection count doesn't update immediately when switching videos
**Workaround:** `videoLoadingState` tracks loading, shows spinner until data loaded
**Verification:** Check for `CircularProgress` component in detection table during load

### Issue 2: Aggregated Metrics Calculate Before Data Loaded
**Symptom:** Aggregated metrics show 0 TP/FP/FN on initial load
**Workaround:** `useEffect` preloads all video data before calculating aggregates
**Verification:** Check `effectivePerVideoSummaries.length === expected video count`

### Issue 3: Field Name Variants Cause Type Errors
**Symptom:** TypeScript errors about missing properties
**Workaround:** Types accept both snake_case and camelCase, normalization creates both
**Verification:** No compilation errors, both field variants accessible

---

## Post-Test Validation

After completing all test scenarios, verify:

### ✅ Complete Data Flow
```typescript
// 1. Backend sends correct data
API Response → ground_truth_comparison: { true_positives: 59, ... }

// 2. Frontend normalizes correctly
React State → ground_truth_comparison: {
  true_positives: 59,
  truePositives: 59  // camelCase alias
}

// 3. UI displays accurately
DOM → <Typography>59</Typography> in TP card
```

### ✅ Multi-Video Aggregation
```typescript
// Verify sum calculation
Video 1 TP: 25
Video 2 TP: 34
Aggregated TP: 59 ✅ (25 + 34)
```

### ✅ Field Name Handling
```typescript
// Both work without errors
detection.actual_latency_ms  // ✅
detection.actualLatencyMs    // ✅
```

### ✅ Backward Compatibility
```typescript
// Old sessions work
Session without ground_truth_comparison → Cards hidden, no crash ✅
Session with legacy fields → Fallback values used ✅
```

---

## Conclusion

This test plan ensures all frontend fixes integrate correctly:
1. **Ground truth metrics** display backend-calculated values
2. **Multi-video aggregation** sums metrics across all videos
3. **Field normalization** handles both snake_case and camelCase
4. **Lazy loading** prevents race conditions
5. **Latency standardization** uses `actual_latency_ms` consistently

**Success Criteria:**
- ✅ All test scenarios pass
- ✅ Zero console errors
- ✅ Backward compatibility maintained
- ✅ Type safety enforced
- ✅ Performance acceptable (<2s load time)

**Next Steps:**
1. Run manual tests on development environment
2. Verify with real test sessions (single & multi-video)
3. Check browser console for errors
4. Document any issues found
5. Create automated integration tests (Playwright/Cypress)
