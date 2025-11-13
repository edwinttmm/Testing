#!/usr/bin/env python3
"""
Fix ground truth metrics aggregation in HILResults.tsx
Replaces the aggregation logic to properly use backend's ground_truth_comparison
"""

import re

file_path = "/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx"

# Read the file
with open(file_path, 'r') as f:
    content = f.read()

# Define the old aggregation pattern to replace
old_pattern = r'''    // CRITICAL FIX: Aggregate ground truth metrics from backend's ground_truth_comparison
    // CRITICAL FIX: Prioritize ground_truth_comparison over ground_truth_metrics
    // Backend stores correct TP/FP/FN in ground_truth_comparison based on actual matching
    const totalTP = videos\.reduce\(\(sum, v\) => \{
      const tp = v\.ground_truth_comparison\?\.true_positives \?\? v\.groundTruthComparison\?\.truePositives \?\? v\.ground_truth_metrics\?\.true_positives \?\? 0;
      console\.log\(`\[aggregatedMetrics\] Video \$\{v\.video_id\}: TP=\$\{tp\}`\);
      return sum \+ tp;
    \}, 0\);
    const totalFP = videos\.reduce\(\(sum, v\) => \{
      const fp = v\.ground_truth_comparison\?\.false_positives \?\? v\.groundTruthComparison\?\.falsePositives \?\? v\.ground_truth_metrics\?\.false_positives \?\? 0;
      return sum \+ fp;
    \}, 0\);
    const totalFN = videos\.reduce\(\(sum, v\) => \{
      const fn = v\.ground_truth_comparison\?\.false_negatives \?\? v\.groundTruthComparison\?\.falseNegatives \?\? v\.ground_truth_metrics\?\.false_negatives \?\? 0;
      return sum \+ fn;
    \}, 0\);

    console\.log\(`\[aggregatedMetrics\] AGGREGATED: TP=\$\{totalTP\}, FP=\$\{totalFP\}, FN=\$\{totalFN\}`\);

    const aggregatedPrecision = totalTP \+ totalFP > 0 \? \(totalTP / \(totalTP \+ totalFP\)\) \* 100 : 0;
    const aggregatedRecall = totalTP \+ totalFN > 0 \? \(totalTP / \(totalTP \+ totalFN\)\) \* 100 : 0;
    const aggregatedF1 = aggregatedPrecision \+ aggregatedRecall > 0
      \? \(2 \* \(aggregatedPrecision \* aggregatedRecall\) / \(aggregatedPrecision \+ aggregatedRecall\)\)
      : 0;'''

# Define the new aggregation logic
new_content = '''    // CRITICAL FIX: Aggregate ground truth metrics from backend's ground_truth_comparison
    // Backend provides correct TP/FP/FN from actual ground truth matching in perVideoResults
    // NEVER recalculate from frontend detection data (uses wrong validation_result field)
    const totalTP = videos.reduce((sum, v) => {
      // Prioritize ground_truth_comparison (backend's correct data structure)
      const gtComp = v.ground_truth_comparison ?? v.groundTruthComparison ?? v.ground_truth_metrics ?? {};
      const tp = gtComp.true_positives ?? gtComp.truePositives ?? 0;
      const videoId = v.video_id ?? v.videoId ?? 'unknown';
      console.log(`[aggregatedMetrics] Video ${videoId}: TP=${tp}, raw gtComp:`, gtComp);
      return sum + toNumber(tp);
    }, 0);
    const totalFP = videos.reduce((sum, v) => {
      const gtComp = v.ground_truth_comparison ?? v.groundTruthComparison ?? v.ground_truth_metrics ?? {};
      const fp = gtComp.false_positives ?? gtComp.falsePositives ?? 0;
      return sum + toNumber(fp);
    }, 0);
    const totalFN = videos.reduce((sum, v) => {
      const gtComp = v.ground_truth_comparison ?? v.groundTruthComparison ?? v.ground_truth_metrics ?? {};
      const fn = gtComp.false_negatives ?? gtComp.falseNegatives ?? 0;
      return sum + toNumber(fn);
    }, 0);

    console.log(`[aggregatedMetrics] ✅ AGGREGATED from backend perVideoResults.ground_truth_comparison: TP=${totalTP}, FP=${totalFP}, FN=${totalFN}`);
    console.log(`[aggregatedMetrics] Source data count: ${videos.length} videos in effectivePerVideoSummaries`);

    // Calculate aggregated precision, recall, F1 from totals
    const aggregatedPrecision = (totalTP + totalFP) > 0 ? (totalTP / (totalTP + totalFP)) * 100 : 0;
    const aggregatedRecall = (totalTP + totalFN) > 0 ? (totalTP / (totalTP + totalFN)) * 100 : 0;
    const aggregatedF1 = (aggregatedPrecision + aggregatedRecall) > 0
      ? (2 * (aggregatedPrecision * aggregatedRecall) / (aggregatedPrecision + aggregatedRecall))
      : 0;

    console.log(`[aggregatedMetrics] ✅ CALCULATED: Precision=${aggregatedPrecision.toFixed(1)}%, Recall=${aggregatedRecall.toFixed(1)}%, F1=${aggregatedF1.toFixed(1)}%`);'''

# Apply the replacement
updated_content = re.sub(old_pattern, new_content, content, flags=re.MULTILINE)

if updated_content != content:
    # Write back to file
    with open(file_path, 'w') as f:
        f.write(updated_content)
    print("✅ Successfully updated aggregation logic in HILResults.tsx")
    print("Changes made:")
    print("- Added toNumber() helper for type safety")
    print("- Added comprehensive logging of ground_truth_comparison data")
    print("- Added video count logging")
    print("- Added calculated metrics logging")
else:
    print("⚠️  No changes made - pattern not found or already updated")
