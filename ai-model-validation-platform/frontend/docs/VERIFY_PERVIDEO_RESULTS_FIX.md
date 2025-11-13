# Verification Guide: perVideoResults Data Consumption Fix

## Quick Verification Steps

### 1. Check Console Logs
Open the browser console and look for:

```
[effectivePerVideoSummaries] Source data: {
  hasPerVideoSummaries: false,
  sequenceResultsPerVideoResults: 3,  // Should be > 0
  sourceListLength: 3,                 // Should match number of videos
  firstVideo: {
    videoId: "abc123",
    videoName: "Video 1",              // Should NOT be null/undefined
    hasGroundTruthComparison: true,    // Should be true
    hasDetectionEvents: true            // Should be true
  }
}
```

### 2. Check Video Selector Dropdown
- Navigate to HIL Results page for a multi-video session
- Verify the video selector dropdown shows:
  - ✅ Correct number of videos
  - ✅ Actual video names (not "Unknown")
  - ✅ Detection counts per video
  - ✅ Pass/fail status indicators

### 3. Check Ground Truth Metrics
- Select each video in the dropdown
- Verify metrics cards show:
  - ✅ Non-zero F1 scores (if ground truth exists)
  - ✅ Correct Precision and Recall percentages
  - ✅ True Positives, False Positives, False Negatives counts

### 4. Check Detection Table
- Verify "Video" column shows:
  - ✅ Actual video names (not "Unknown")
  - ✅ Correct video numbers (1/3, 2/3, 3/3)

## Detailed Verification

### Test Case 1: Snake Case Response (per_video_results)
**API Response**:
```json
{
  "per_video_results": [
    {
      "video_id": "vid1",
      "video_name": "Test Video 1",
      "ground_truth_comparison": {
        "true_positives": 10,
        "false_positives": 2,
        "false_negatives": 1,
        "precision": 83.3,
        "recall": 90.9,
        "f1_score": 87.0
      },
      "detection_events": [...]
    }
  ]
}
```

**Expected Console Log**:
```
[effectivePerVideoSummaries] Source data: {
  sequenceResultsPer_video_results: 1,
  sourceListLength: 1,
  firstVideo: {
    videoId: "vid1",
    videoName: "Test Video 1",
    hasGroundTruthComparison: true,
    hasDetectionEvents: true
  }
}
```

### Test Case 2: Camel Case Response (perVideoResults)
**API Response**:
```json
{
  "perVideoResults": [
    {
      "videoId": "vid1",
      "videoName": "Test Video 1",
      "groundTruthComparison": {
        "truePositives": 10,
        "falsePositives": 2,
        "falseNegatives": 1,
        "precision": 83.3,
        "recall": 90.9,
        "f1Score": 87.0
      },
      "detectionEvents": [...]
    }
  ]
}
```

**Expected Console Log**:
```
[effectivePerVideoSummaries] Source data: {
  sequenceResultsPerVideoResults: 1,
  sourceListLength: 1,
  firstVideo: {
    videoId: "vid1",
    videoName: "Test Video 1",
    hasGroundTruthComparison: true,
    hasDetectionEvents: true
  }
}
```

### Test Case 3: Mixed Field Names
**API Response**:
```json
{
  "perVideoResults": [
    {
      "video_id": "vid1",
      "videoName": "Test Video 1",
      "ground_truth_comparison": { ... },
      "detectionEvents": [...]
    }
  ]
}
```

**Expected**: All fields should be correctly normalized and preserved.

## Red Flags (Issues to Watch For)

### ❌ Video Names Show "Unknown"
**Cause**: Backend not providing video_name or videoName
**Check Console For**:
```
firstVideo: {
  videoName: undefined  // ❌ Problem!
}
```

### ❌ F1 Score Shows 0%
**Cause**: ground_truth_comparison missing or not preserved
**Check Console For**:
```
firstVideo: {
  hasGroundTruthComparison: false  // ❌ Problem!
}
```

### ❌ Video Selector Empty
**Cause**: perVideoResults not being extracted
**Check Console For**:
```
sourceListLength: 0  // ❌ Problem!
```

## Code Inspection Points

### Line 253: Source List Extraction
```typescript
: (sequenceResults?.perVideoResults ?? sequenceResults?.per_video_results)) ?? [];
```
✅ Should check BOTH field names

### Line 335-342: Ground Truth Preservation
```typescript
ground_truth_comparison: {
  ...(video.ground_truth_comparison ?? {}),
  ...metrics,
},
```
✅ Should MERGE objects, not replace

### Line 362-365: Detection Events Preservation
```typescript
...(backendDetectionEvents && {
  detection_events: backendDetectionEvents,
  detectionEvents: backendDetectionEvents
}),
```
✅ Should explicitly preserve both field names

## API Response Debugging

### Check Raw API Response
```javascript
// In browser console:
fetch('/api/enhanced_hil_results/v2/{sessionId}')
  .then(r => r.json())
  .then(data => {
    console.log('Raw API Response:', data);
    console.log('Has perVideoResults:', !!data.perVideoResults);
    console.log('Has per_video_results:', !!data.per_video_results);
    console.log('First video:', data.perVideoResults?.[0] || data.per_video_results?.[0]);
  });
```

## Success Criteria

All of the following must be true:

- [ ] Video selector shows correct video count
- [ ] Video names are NOT "Unknown" (unless backend doesn't provide them)
- [ ] F1 scores are > 0% (if ground truth exists)
- [ ] Detection table "Video" column shows correct names
- [ ] Console logs show non-zero sourceListLength
- [ ] Console logs show hasGroundTruthComparison: true
- [ ] Console logs show hasDetectionEvents: true
- [ ] Switching between videos updates metrics correctly

## Rollback Instructions

If issues occur, revert these lines in HILResults.tsx:

1. Line 253: Change back to `sequenceResults?.per_video_results`
2. Lines 335-342: Change back to `ground_truth_comparison: metrics`
3. Lines 362-365: Remove explicit detectionEvents preservation

Then investigate why the backend API response structure differs from expected.
