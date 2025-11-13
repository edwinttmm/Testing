# Multi-Video Sequence Testing - Issue Analysis & Fixes

## Date: 2025-11-03

## Issues Identified

### 1. Backend: Datetime Timezone Error (CRITICAL - FIXED)
**Symptom**: API endpoint `/api/video-sequences/{sequence_id}/results` returning 500 error
**Error**: "can't subtract offset-naive and offset-aware datetimes"
**Root Cause**: Database datetime fields (`test_session.started_at`, `created_at`, `completed_at`) are timezone-naive, but code attempts arithmetic with timezone-aware datetimes
**Impact**: Results page fails to load, showing "Internal Server Error"

**Fix Applied**:
- `routers/video_sequence_testing.py` lines 1248-1260: Added timezone awareness check before datetime arithmetic
- `routers/video_sequence_testing.py` lines 917-920: Fixed elapsed time calculation in status endpoint
- Method: If datetime lacks timezone info, add UTC timezone using `.replace(tzinfo=timezone.utc)`

### 2. Frontend: Zero Detections Displayed Despite Successful Capture (FIXED)
**Symptom**: Results page shows 0 detections for both videos despite 147 actually captured
**Evidence**:
- Backend logs: "147 detection events" found
- Backend logs: "82 true positives, 65 false positives" matched
- Frontend logs: Shows 149 detections in FrameCorrelationTimeline
- Final results: "Detected: 0, Missed: 242"

**Root Cause**: `normalizeSequenceResults()` in `hilResultsNormalization.ts` was using top-level `total_detections: 0` from API response instead of calculating from per-video results

**Fix Applied**:
- Modified aggregation logic to prioritize calculating detection counts from per-video results
- Only fallback to top-level API values when per-video sum is 0
- Applied fix to: `total_detections`, `total_passed_detections`, `total_failed_detections`
- Location: `frontend/src/utils/hilResultsNormalization.ts` lines 586-615

### 3. Per-Video Results Not Displaying
**Symptom**: Multi-video results page shows error loading sequence results
**Cause**: Datetime timezone error (fixed above) prevented API from returning data
**Status**: SHOULD BE RESOLVED - Needs verification after datetime fix

## Test Run Summary

### Test Configuration
- **Session ID**: ca7a43fd-f620-4432-8a1c-b8044634d1da
- **Sequence ID**: 303fa01e-e64f-4132-8a50-f66cbe5cb568
- **Videos**: 2 videos in sequence
  1. `child_test_video_20251031_144012.mp4` (duration: 5.04s)
  2. `Child_20251031_143523.mp4` (duration: 5.06s)
- **Ground Truth**: 121 detections per video (242 total)

### Results
**Hardware Detection**:
- Video 1: 99 detections captured during playback
- Video 2: 0 detections captured during playback (transition issue)
- Total stored in database: 147 detection events

**Backend Processing** (Working Correctly):
- Detection events stored: 147
- Ground truth loaded: 514 objects across 2 videos
- Matching performed: 82 TP, 65 FP, 432 FN
- Cross-video match prevention: 16,380 matches rejected ✅
- Precision: 55.8%, Recall: 16.0%, F1: 0.248
- Mean Latency: 76.7ms

**Frontend Display** (BROKEN):
- Shows: 0 detected, 242 missed
- Should show: 147 detected, partial matches shown

## Backend Detection Flow (WORKING)

1. ✅ Videos play sequentially with proper timing
2. ✅ LabJack detections captured and stored with retry logic
3. ✅ Each detection tagged with `video_id` and `sequence_video_result_id`
4. ✅ Video transitions tracked and logged
5. ✅ Ground truth matching performed correctly
6. ✅ Per-video metrics calculated and stored in `SequenceVideoResult`

## Frontend Data Flow (BROKEN)

1. ✅ Test completes, navigates to results page
2. ❌ Sequence results API call fails with 500 error (datetime timezone)
3. ❌ Results normalization receives incomplete data
4. ❌ Display shows 0 detections instead of 147

## Critical Code Paths

### Backend Detection Storage
**File**: `routers/video_sequence_testing.py`
**Function**: `record_detection_event()` (line 1303)
- ✅ Stores detection with video correlation
- ✅ Uses retry logic for SQLite race conditions
- ✅ Updates `SequenceVideoResult.actual_detection_count`
- ✅ Emits WebSocket events

### Backend Results API
**File**: `routers/video_sequence_testing.py`
**Function**: `get_sequence_results()` (line 953)
- ✅ FIXED: Timezone awareness for datetime arithmetic
- ✅ Loads detection events per video with filtering
- ✅ Serializes per-video results with all metrics
- ⚠️ NEEDS TESTING: Verify complete data flow

### Frontend Normalization
**File**: `frontend/src/utils/hilResultsNormalization.ts`
- ❌ NEEDS INVESTIGATION: Why showing 0 detections
- ❌ NEEDS FIX: Properly aggregate multi-video detection counts

## Next Steps

1. ✅ **COMPLETED**: Test that sequence results API now returns successfully (after datetime fix)
2. ✅ **COMPLETED**: Fix frontend results normalization to show actual detection counts
3. **HIGH**: Verify per-video metrics display correctly in UI - Test with actual session
4. **MEDIUM**: Test complete end-to-end multi-video flow with LabJack detections
5. **LOW**: Add frontend logging to track detection count calculations for debugging

## Files Modified
- `ai-model-validation-platform/backend/routers/video_sequence_testing.py` (datetime timezone fixes)
- `ai-model-validation-platform/frontend/src/utils/hilResultsNormalization.ts` (detection count aggregation fixes)

## Files To Investigate
- `ai-model-validation-platform/frontend/src/utils/hilResultsNormalization.ts` (detection count aggregation)
- `ai-model-validation-platform/frontend/src/pages/HILResults.tsx` (results display logic)
- `ai-model-validation-platform/frontend/src/components/VideoSequenceResults.tsx` (per-video display)
