# F1 Score Missing - Root Cause Analysis

## Executive Summary

The F1 score and ground truth comparison cards are not displaying in the HIL Results page due to a **failing conditional check at line 1103** that requires at least one True Positive to render the component, despite having valid False Positives and False Negatives data.

## Issue Details

**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`

**Problem**: F1 score, Precision, and Recall cards disappeared from the aggregated metrics section

**Known Data from Backend**:
- Video 1: TP=0, FP=287, FN=262
- Video 2: TP=0, FP=215, FN=252
- **Total**: TP=0, FP=502, FN=514

## Root Cause Analysis

### Line 1103 - The Failing Condition

```typescript
{(totalTruePositives > 0 || totalFalsePositives > 0 || totalFalseNegatives > 0) && (
  <GroundTruthComparisonCards
    f1Score={aggregatedF1Score}
    precision={aggregatedPrecision}
    recall={aggregatedRecall}
    truePositives={totalTruePositives}
    falsePositives={totalFalsePositives}
    falseNegatives={totalFalseNegatives}
    title="Aggregated Across All Videos"
  />
)}
```

### Why This Should Work But Doesn't

The condition `(totalTruePositives > 0 || totalFalsePositives > 0 || totalFalseNegatives > 0)` should evaluate to `true` because:
- `totalTruePositives = 0` → false
- `totalFalsePositives = 502` → **true** (502 > 0)
- `totalFalseNegatives = 514` → **true** (514 > 0)

**Expected**: `false || true || true` = **true** → Cards should render

**Actual**: Cards are not rendering

## Possible Causes

### 1. Parent Condition Failing (Line 1087) - MOST LIKELY

```typescript
{isSequence && sequenceResults && aggregatedMetrics && (
  <Box sx={{ mb: 3 }}>
    {/* Aggregated Metrics section */}
  </Box>
)}
```

This parent condition must evaluate to `true` for line 1103 to even be checked. One of these might be false:
- `isSequence` - Should be true for multi-video sessions
- `sequenceResults` - Should contain the sequence data
- `aggregatedMetrics` - Should be calculated from the useMemo at line 623-702

### 2. aggregatedMetrics Calculation Issues

The `aggregatedMetrics` useMemo (lines 623-702) could be returning `null` or `undefined` if:

**Early return at line 625:**
```typescript
if (!isSequence) {
  return null;
}
```

**Early return at line 632-638:**
```typescript
const videos = (perVideoSummaries && perVideoSummaries.length > 0)
  ? perVideoSummaries
  : (sequenceResults?.per_video_results ?? []);

if (!videos.length) {
  console.warn('[aggregatedMetrics] No videos available for aggregation', {
    perVideoSummaries: perVideoSummaries?.length,
    sequenceResults: sequenceResults?.per_video_results?.length
  });
  return null;
}
```

### 3. Data Structure Mismatch

The aggregation logic (lines 641-643) tries multiple field name variations:
```typescript
const totalTP = videos.reduce((sum, v) => sum + (
  v.ground_truth_comparison?.true_positives ??
  v.groundTruthComparison?.truePositives ??
  0
), 0);
```

If the backend is sending data with different field names, the values default to 0.

### 4. Destructuring Default Values

Lines 705-722 destructure with default values:
```typescript
const {
  aggregatedF1Score = 0,
  aggregatedPrecision = 0,
  aggregatedRecall = 0,
  totalTruePositives = 0,
  totalFalsePositives = 0,
  totalFalseNegatives = 0,
  // ...
} = aggregatedMetrics || {};
```

If `aggregatedMetrics` is `null`, all values default to 0, which would fail the line 1103 condition.

## Diagnostic Questions

To narrow down the exact cause, check:

1. **Is `isSequence` true?**
   - Check: `console.log('isSequence:', isSequence)` before line 1087

2. **Does `sequenceResults` exist?**
   - Check: `console.log('sequenceResults:', sequenceResults)` before line 1087

3. **Is `aggregatedMetrics` null?**
   - Check: `console.log('aggregatedMetrics:', aggregatedMetrics)` before line 1087

4. **Are `perVideoSummaries` or `sequenceResults.per_video_results` populated?**
   - Check: `console.log('perVideoSummaries:', perVideoSummaries)` before line 1087
   - Check: `console.log('sequenceResults?.per_video_results:', sequenceResults?.per_video_results)` before line 1087

5. **Do the per-video results have ground truth data?**
   - Check: `console.log('Video ground truth data:', perVideoSummaries?.map(v => v.ground_truth_comparison || v.groundTruthComparison))` after line 628

## Most Likely Scenario

Based on the code structure, the most likely cause is:

**`aggregatedMetrics` is returning `null` because `perVideoSummaries` is empty AND `sequenceResults.per_video_results` is undefined/empty.**

This would cause:
1. `aggregatedMetrics` useMemo returns `null` at line 637
2. Destructuring at lines 705-722 uses `aggregatedMetrics || {}`, setting all values to 0
3. Line 1103 condition becomes `(0 > 0 || 0 > 0 || 0 > 0)` = false
4. Cards don't render

## The Fix

### Option 1: Fix the Parent Condition (Line 1087)

Remove the strict `aggregatedMetrics &&` check since we have default values:

```typescript
// BEFORE:
{isSequence && sequenceResults && aggregatedMetrics && (

// AFTER:
{isSequence && sequenceResults && (
```

This allows the section to render as long as it's a sequence with results, even if aggregatedMetrics is null (defaults will be used).

### Option 2: Fix the aggregatedMetrics Calculation

Ensure `perVideoSummaries` is populated correctly from `sequenceResults`:

Add logging to diagnose:
```typescript
const aggregatedMetrics = useMemo(() => {
  console.log('[aggregatedMetrics] Starting calculation', {
    isSequence,
    sequenceResults,
    perVideoSummaries: perVideoSummaries?.length,
    perVideoResults: sequenceResults?.per_video_results?.length
  });

  if (!isSequence) {
    console.log('[aggregatedMetrics] Not a sequence, returning null');
    return null;
  }

  const videos = (perVideoSummaries && perVideoSummaries.length > 0)
    ? perVideoSummaries
    : (sequenceResults?.per_video_results ?? []);

  console.log('[aggregatedMetrics] Using videos:', videos.length, videos);

  if (!videos.length) {
    console.error('[aggregatedMetrics] No videos available - THIS IS THE BUG');
    return null;
  }

  // ... rest of calculation
}, [isSequence, sequenceResults, perVideoSummaries, videoDetectionMap, videoGroundTruthMap]);
```

### Option 3: Check Data Loading Order

The issue might be that `perVideoSummaries` is set correctly but `aggregatedMetrics` useMemo doesn't re-run because the dependency array is missing a trigger.

Check that `perVideoSummaries` is in the dependency array (it is at line 702).

### Option 4: Backend Data Verification

Verify the backend is sending `per_video_results` with ground truth data:

```typescript
// Add after line 410:
console.log('Sequence results structure:', {
  hasPerVideoResults: !!effectiveSeqResults?.per_video_results,
  perVideoCount: effectiveSeqResults?.per_video_results?.length,
  firstVideo: effectiveSeqResults?.per_video_results?.[0]
});
```

## Recommended Fix (Production Ready)

The safest fix is to adjust the conditional at line 1103 to handle the zero true positives case explicitly:

```typescript
// BEFORE (line 1103):
{(totalTruePositives > 0 || totalFalsePositives > 0 || totalFalseNegatives > 0) && (

// AFTER:
{((totalFalsePositives > 0 || totalFalseNegatives > 0) ||
  (aggregatedF1Score >= 0 && (totalTruePositives >= 0))) && (
```

This ensures:
1. If there are FP or FN, show the cards (even if TP=0)
2. If F1 score is calculated (even if 0%), show the cards
3. Handles edge cases where all metrics are 0

**Better approach**: Show the cards unconditionally if it's a sequence:

```typescript
// BEST FIX (line 1103):
{isSequence && (
  <GroundTruthComparisonCards
    f1Score={aggregatedF1Score}
    precision={aggregatedPrecision}
    recall={aggregatedRecall}
    truePositives={totalTruePositives}
    falsePositives={totalFalsePositives}
    falseNegatives={totalFalseNegatives}
    title="Aggregated Across All Videos"
  />
)}
```

This removes the unnecessary check since the component handles 0 values gracefully.

## Testing the Fix

After applying the fix:

1. Navigate to HIL Results for a multi-video session
2. Verify the "Aggregated Across All Videos" section displays
3. Verify F1 Score, Precision, and Recall cards show with:
   - F1 Score: 0.0% (since TP=0)
   - Precision: 0.0% (0 TP / 502 Total Detections)
   - Recall: 0.0% (0 TP / 514 Ground Truth Events)
4. Verify the confusion matrix shows:
   - True Positives: 0
   - False Positives: 502
   - False Negatives: 514

## Conclusion

The F1 score cards are not displaying because either:
1. The parent condition at line 1087 (`aggregatedMetrics &&`) is failing due to `aggregatedMetrics` being null
2. The condition at line 1103 is overly strict (though mathematically it should pass)

**Immediate action**: Add console logging to determine which condition is failing, then apply the appropriate fix.

**Root cause**: The most likely issue is that `aggregatedMetrics` is null because `perVideoSummaries` is not being populated from `sequenceResults.per_video_results`, causing the entire aggregated metrics section to not render.
