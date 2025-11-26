# Frontend Recall Display Fix - Quick Instructions

## Problem
Frontend displays **"Recall 100.0%"** when actual recall is **35%**

## Location
**File:** `/frontend/src/pages/EnhancedResults.tsx`
**Line:** 878

## Current Code (WRONG)
```typescript
recall: latencyValidationResults.pass_rate / 100,  // ❌ Shows 100%
```

## Fixed Code (CORRECT)
```typescript
recall: (totalTruePositives + totalFalseNegatives) > 0
  ? (totalTruePositives / (totalTruePositives + totalFalseNegatives))
  : latencyValidationResults.pass_rate / 100,  // ✅ Shows 35%
```

## Explanation
- **Problem:** Reading from first video's metrics (100%) instead of session-wide metrics
- **Solution:** Calculate recall from aggregated true positives and false negatives
- **Formula:** `Recall = TP / (TP + FN)`
- **Example:** `85 / (85 + 157) = 85 / 242 = 0.3512 = 35.12%`

## Variables Available
The variables `totalTruePositives` and `totalFalseNegatives` are already computed in the component around line 1118. They represent session-wide aggregated metrics, not per-video metrics.

## Testing
After applying the fix:
1. Start a test session with ground truth data
2. Complete the test
3. Navigate to results page
4. Verify recall displays correctly:
   - If 85 TP and 157 FN → Should show "Recall 35.1%"
   - NOT "Recall 100.0%"

## Verification
```typescript
// In browser console:
console.log('TP:', totalTruePositives);  // e.g., 85
console.log('FN:', totalFalseNegatives); // e.g., 157
console.log('Recall:', totalTruePositives / (totalTruePositives + totalFalseNegatives));
// Expected: 0.3512 (35.12%)
```

## Impact
- **Before:** Wrong metrics → Wrong decisions
- **After:** Correct metrics → Correct decisions
- **Priority:** HIGH - Affects all test interpretations

## Related Files
- Backend API: No changes needed (already returns correct data)
- Detection Service: No changes needed
- EnhancedResults.tsx: Line 878 only

## Complete Fix Context
```typescript
// Around line 873-880 in EnhancedResults.tsx
<ComparisonMetricsCard
  metrics={{
    accuracy: latencyValidationResults.pass_rate / 100,
    precision: latencyValidationResults.pass_rate / 100,
    // OLD (line 878):
    // recall: latencyValidationResults.pass_rate / 100,

    // NEW (line 878):
    recall: (totalTruePositives + totalFalseNegatives) > 0
      ? (totalTruePositives / (totalTruePositives + totalFalseNegatives))
      : latencyValidationResults.pass_rate / 100,

    f1Score: latencyValidationResults.pass_rate / 100,
    truePositives: latencyValidationResults.passed_detections,
    // ... rest of metrics
  }}
  title="LabJack Timing Performance"
  validationType="labjack"
/>
```

## Deployment
```bash
# After fix
npm run build
npm run deploy
```

## Questions?
See complete implementation guide:
- `/backend/docs/DUAL_FIX_IMPLEMENTATION.md`
- `/backend/reports/DUAL_FIX_DELIVERY_REPORT.md`
