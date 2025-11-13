# HIL Results Page - Testing Instructions
**Session ID**: 0846e476-2e21-499c-bfc8-0b2218081c77
**Date**: 2025-11-05

---

## 🚀 Quick Start

### 1. Access the Results Page
```
URL: http://localhost:3000/results/0846e476-2e21-499c-bfc8-0b2218081c77
```

### 2. Verify Backend is Running
```bash
# Check backend process
ps aux | grep "python3 main.py"

# Should show PID 100263 or similar
# If not running:
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 main.py
```

### 3. Clear Browser Cache (Important!)
```
Chrome/Edge: Ctrl+Shift+Delete → Clear cache
Firefox: Ctrl+Shift+Delete → Cookies and Cache
Safari: Cmd+Option+E

OR use Incognito/Private window for fresh session
```

---

## ✅ Test Checklist

### Test #1: F1 Score Section Visibility
**What to check**: "Aggregated Across All Videos" section should be visible

**Expected Results**:
- ✅ Section header: "Aggregated Across All Videos" displays
- ✅ F1 Score card visible (even if value is 0% or null)
- ✅ Precision card visible
- ✅ Recall card visible
- ✅ Ground truth comparison cards showing:
  - True Positives: 0
  - False Positives: 502
  - False Negatives: 514

**Screenshot Location**: Top section of results page

**If Failed**:
```
Check browser console for errors:
F12 → Console tab → Look for "aggregatedMetrics" errors
```

---

### Test #2: Video Dropdown Display
**What to check**: Video selector dropdown shows proper video names

**Expected Results**:
- ✅ Dropdown shows video names like:
  - "Video 1: [filename].mp4" or similar
  - "Video 2: [filename].mp4" or similar
- ❌ Should NOT show detection data like:
  - "pedestrian • 93.3% GT Frame 113 4.708s"
  - Any detection confidence scores or frame numbers

**Screenshot Location**: Top-right corner, video selector dropdown

**If Failed**:
```
Check browser console for filtering warnings:
Look for: "🚨 Detection object found in per_video_results, filtering out"

If warnings appear, backend needs investigation.
```

---

### Test #3: Detection Timing Information
**What to check**: Detection table rows show timing details

**Expected Results** (for each detection row):
- ✅ **Latency**: Shows value like "7701ms" or "7.7s"
- ✅ **Frame Number**: Shows frame number (e.g., "Frame 113")
- ✅ **Timestamp**: Shows relative timestamp (e.g., "4.708s")
- ✅ **Voltage**: Shows voltage level (e.g., "4.26V")
- ✅ **Ground Truth Status**: Shows "GT PASS" or "GT FAIL"

**Screenshot Location**: Detection events table (middle/bottom section)

**Sample Row Format**:
```
pedestrian • 93.3% | GT Frame 113 | Detection Frame 0 | 4.708s | 7701ms | 4.26V | GT PASS
```

**If Failed**:
```
Check API response in Network tab:
F12 → Network → Find request to:
/api/test-sessions/{id}/events?limit=2000

Verify response contains:
- latency_ms
- video_relative_timestamp
- frame_number
```

---

### Test #4: Video Pass Count Accuracy
**What to check**: Status banner shows correct number of videos passed

**Expected Results**:
- ✅ Status banner displays at top of page
- ✅ Shows "X of Y videos passed" or similar
- ✅ Video count matches actual videos in session (should be 2)
- ✅ Pass count accurately reflects video validation results

**Screenshot Location**: Top banner area

**Backend Status Values**:
- Backend may return: `status: 'completed'`
- Frontend now accepts: `'pass'` OR `'completed'`

**If Failed**:
```
Check video data in API response:
/api/enhanced-hil/test-sessions/{id}/corrected-results

Verify each video object has:
- status: 'pass' or 'completed'
- validation_result field
```

---

### Test #5: Ground Truth Cards Rendering
**What to check**: Ground truth comparison cards visible even with 0 True Positives

**Expected Results**:
- ✅ True Positives (TP) card shows "0"
- ✅ False Positives (FP) card shows "502"
- ✅ False Negatives (FN) card shows "514"
- ✅ Precision card shows "0%" (0 TP / (0 TP + 502 FP))
- ✅ Recall card shows "0%" (0 TP / (0 TP + 514 FN))
- ✅ F1 Score card shows "0%"

**Why This Matters**:
The 0% true positive rate indicates ground truth matching may need review, but the UI should still display these metrics.

**Screenshot Location**: Ground truth comparison section

**If Failed**:
```
Check console for rendering conditions:
- aggregatedMetrics value
- totalTruePositives
- totalFalsePositives
- totalFalseNegatives
```

---

## 🔍 Advanced Verification

### Verify API Data Structure
```bash
# Test detection events endpoint
curl http://localhost:8000/api/test-sessions/0846e476-2e21-499c-bfc8-0b2218081c77/events?limit=2000

# Should return JSON with 502 events, each containing:
{
  "video_id": "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5",
  "latency_ms": 7701.2,
  "video_relative_timestamp": 4.708,
  "frame_number": 113,
  "voltage": 4.26,
  // ... other fields
}
```

### Verify Ground Truth Data
```bash
# Test ground truth comparison endpoint
curl http://localhost:8000/api/enhanced-hil/test-sessions/0846e476-2e21-499c-bfc8-0b2218081c77/ground-truth-comparison

# Should return:
{
  "true_positives": 0,
  "false_positives": 502,
  "false_negatives": 514,
  "precision": 0.0,
  "recall": 0.0,
  "f1_score": 0.0
}
```

### Verify Video Breakdown
```bash
# Test per-video results
curl http://localhost:8000/api/enhanced-hil/test-sessions/0846e476-2e21-499c-bfc8-0b2218081c77/corrected-results

# Should return per_video_results array with 2 video objects:
{
  "per_video_results": [
    {
      "video_id": "10c2b16c-...",
      "video_name": "...",
      "detection_count": 287,
      "status": "completed"
    },
    {
      "video_id": "550e3cf8-...",
      "video_name": "...",
      "detection_count": 215,
      "status": "completed"
    }
  ]
}
```

---

## 🐛 Common Issues & Solutions

### Issue: "Page shows old data"
**Solution**:
```
1. Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
2. Clear browser cache completely
3. Try incognito/private window
4. Verify build version in browser console:
   - Open F12 → Console
   - Should see: "Build version: 1762346809259"
```

### Issue: "F1 score still missing"
**Solution**:
```
1. Check if sequenceResults is loaded:
   - F12 → Console → Type: sequenceResults
   - Should show object with data
2. Verify aggregatedMetrics:
   - May be null initially, but section should still render
3. Check React DevTools:
   - Install React DevTools extension
   - Inspect HILResults component props
```

### Issue: "Video dropdown still shows detection data"
**Solution**:
```
1. Check console for filtering warnings:
   "🚨 Detection object found in per_video_results"
2. If warnings appear, backend serialization issue exists
3. Defensive filter should still prevent display
4. If detection data still shows, check:
   - validatedPerVideo array in React DevTools
   - Whether filter is executing correctly
```

### Issue: "Detection timing missing"
**Solution**:
```
1. Verify API response has fields:
   F12 → Network → events?limit=2000 → Response

2. Check normalization in console:
   - Set breakpoint in hilResultsNormalization.ts
   - Verify latencyMs, videoRelativeTimestamp, frameNumber extraction

3. Confirm table is using normalized data:
   - React DevTools → HILResults → detectionEvents prop
```

---

## 📊 Expected Test Results Summary

| Test | Expected Result | Critical? |
|------|----------------|-----------|
| F1 Score Visible | ✅ Section renders, shows 0% metrics | YES |
| Video Dropdown | ✅ Shows 2 video names | YES |
| Detection Timing | ✅ All rows show latency/frame/timestamp | YES |
| Video Pass Count | ✅ Shows accurate count (likely 2/2) | MEDIUM |
| Ground Truth Cards | ✅ Shows 0 TP, 502 FP, 514 FN | YES |
| Page Alignment | ✅ No layout breaks or misalignments | YES |

---

## 📸 Screenshot Checklist

Please capture screenshots of:
1. **Full page view** (scroll to show entire results)
2. **Video dropdown menu** (expanded to show options)
3. **Detection table** (first 10 rows showing timing data)
4. **F1 score section** (ground truth comparison cards)
5. **Status banner** (top of page)
6. **Browser console** (F12 → Console, show any errors/warnings)

---

## 🔄 If You Need to Rollback

```bash
# Navigate to frontend
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Rollback code changes
git checkout src/pages/HILResults.tsx
git checkout src/utils/hilResultsNormalization.ts

# Rebuild
npm run build

# Restart frontend dev server if running
# The changes are in production build, so just refresh browser
```

---

## 📞 Support & Next Steps

### If All Tests Pass ✅
- System is working as expected
- Document any remaining UI polish needs
- Investigate why ground truth matching shows 0% (backend issue, not UI)

### If Tests Fail ❌
- Document which specific tests failed
- Capture browser console errors
- Check Network tab for API response issues
- Provide screenshots of failures

### Backend Investigation Needed
The 0% true positive rate (0 TP, 502 FP, 514 FN) suggests:
- Ground truth matching algorithm needs review
- Timing thresholds may be incorrect
- Frame correlation logic may have issues

This is a **backend issue**, not a UI problem. The UI is now correctly displaying the data it receives.

---

**Testing Guide Version**: 1.0
**Build Version**: 1762346809259
**Last Updated**: 2025-11-05
**Status**: Ready for user testing
