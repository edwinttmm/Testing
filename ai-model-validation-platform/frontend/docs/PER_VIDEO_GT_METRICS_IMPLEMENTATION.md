# Per-Video Ground Truth Metrics Implementation

## Summary

Successfully implemented per-video ground truth metrics display in the frontend UI. The UI now shows ground truth performance metrics (Precision, Recall, F1 Score, TP/FP/FN) for each individual video in multi-video test sequences.

## Changes Made

### 1. Type Definitions (`frontend/src/types/enhanced-results.ts`)

**Added GroundTruthMetrics interface:**
```typescript
export interface GroundTruthMetrics {
  total_ground_truth?: number;
  totalGroundTruth?: number;
  true_positives?: number;
  truePositives?: number;
  false_positives?: number;
  falsePositives?: number;
  false_negatives?: number;
  falseNegatives?: number;
  precision?: number;
  recall?: number;
  f1_score?: number;
  f1Score?: number;
}
```

**Updated PerVideoResult interface:**
```typescript
export interface PerVideoResult {
  // ... existing fields ...
  ground_truth_metrics?: GroundTruthMetrics;
  groundTruthMetrics?: GroundTruthMetrics;
  // ... rest of fields ...
}
```

### 2. Component Updates (`frontend/src/components/GroundTruthComparisonCards.tsx`)

**Enhanced GroundTruthComparisonCards component:**
- Made `totalGroundTruth` optional (calculated from TP + FN if not provided)
- Added `title` prop for customizable headings
- Default title: "Ground Truth Comparison - Model Performance"
- Supports per-video custom titles like "Ground Truth Metrics - Video 1"

**Updated props interface:**
```typescript
interface GroundTruthComparisonCardsProps {
  precision: number;
  recall: number;
  f1Score: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  totalGroundTruth?: number;  // Now optional
  title?: string;              // New customizable title
}
```

### 3. UI Display (`frontend/src/pages/HILResults.tsx`)

**Added per-video ground truth metrics section:**
- Displays when a video is selected in multi-video sequences
- Shows full GroundTruthComparisonCards component with video-specific metrics
- Located below the video status chips, above the timeline
- Conditional rendering: only shows if `selectedVideoSummary.ground_truth_metrics` exists

**Implementation location:**
```tsx
{(isSequence && selectedVideoId) && (
  <Box sx={{ mb: 3 }}>
    <Stack direction="row" spacing={1} flexWrap="wrap">
      {/* Status chips */}
    </Stack>

    {/* Per-Video Ground Truth Metrics */}
    {selectedVideoSummary?.ground_truth_metrics && (
      <Box sx={{ mt: 3 }}>
        <GroundTruthComparisonCards
          precision={selectedVideoSummary.ground_truth_metrics.precision ?? 0}
          recall={selectedVideoSummary.ground_truth_metrics.recall ?? 0}
          f1Score={selectedVideoSummary.ground_truth_metrics.f1_score ?? selectedVideoSummary.ground_truth_metrics.f1Score ?? 0}
          truePositives={selectedVideoSummary.ground_truth_metrics.true_positives ?? selectedVideoSummary.ground_truth_metrics.truePositives ?? 0}
          falsePositives={selectedVideoSummary.ground_truth_metrics.false_positives ?? selectedVideoSummary.ground_truth_metrics.falsePositives ?? 0}
          falseNegatives={selectedVideoSummary.ground_truth_metrics.false_negatives ?? selectedVideoSummary.ground_truth_metrics.falseNegatives ?? 0}
          totalGroundTruth={selectedVideoSummary.ground_truth_metrics.total_ground_truth ?? selectedVideoSummary.ground_truth_metrics.totalGroundTruth}
          title={`Ground Truth Metrics - ${selectedVideoSummary.videoName ?? selectedVideoSummary.video_name ?? 'Selected Video'}`}
        />
      </Box>
    )}
  </Box>
)}
```

## Backend Data Expectations

The frontend expects the backend to provide the following structure in the API response:

```typescript
{
  per_video_results: [
    {
      video_id: "string",
      video_name: "string",
      ground_truth_metrics: {
        total_ground_truth: number,
        true_positives: number,
        false_positives: number,
        false_negatives: number,
        precision: number,      // percentage (0-100)
        recall: number,         // percentage (0-100)
        f1_score: number        // percentage (0-100)
      }
    }
  ]
}
```

## UI Behavior

### Display Hierarchy

1. **Aggregated Overall Metrics** (all videos combined)
   - Shown at the top for multi-video sequences
   - Uses aggregated TP/FP/FN across all videos

2. **Per-Video Metrics** (selected video)
   - Shown when a video is selected from the dropdown
   - Displays ground truth metrics specific to that video
   - Custom title includes video name

3. **Signal Quality Metrics**
   - Shown below ground truth metrics
   - Hardware status, latency, detection rates

### Field Name Support

The implementation supports both snake_case and camelCase field names from the backend:
- `ground_truth_metrics` and `groundTruthMetrics`
- `true_positives` and `truePositives`
- `false_positives` and `falsePositives`
- `false_negatives` and `falseNegatives`
- `f1_score` and `f1Score`
- `total_ground_truth` and `totalGroundTruth`

## Verification

### Build Status
✅ **TypeScript compilation successful**
- No type errors
- Build size: 38.88 kB (main bundle)
- Total optimized production build created

### Files Modified
1. `/frontend/src/types/enhanced-results.ts` - Added GroundTruthMetrics interface
2. `/frontend/src/components/GroundTruthComparisonCards.tsx` - Enhanced with optional props
3. `/frontend/src/pages/HILResults.tsx` - Added per-video GT metrics display

## Testing Recommendations

1. **Single Video Test**
   - Verify ground truth metrics still display correctly
   - Check that existing overall metrics remain unchanged

2. **Multi-Video Sequence Test**
   - Select different videos from dropdown
   - Verify per-video metrics update correctly
   - Confirm metrics match backend data

3. **Edge Cases**
   - Video with no ground truth data (should not crash)
   - Video with partial ground truth metrics
   - Missing fields (should use defaults/fallbacks)

## Next Steps

1. Backend should populate `ground_truth_metrics` field in `PerVideoResult` objects
2. Test with real multi-video test data
3. Verify metrics calculations match expected values
4. Consider adding per-video metrics export functionality
