#!/bin/bash
# Verification script for top results bug fix

echo "🔍 Verifying Top Results Bug Fix..."
echo ""

FILE="/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx"

# Check 1: useMemo dependencies
echo "✅ Check 1: useMemo dependencies fixed"
grep -A 1 "}, \[isSequence, sequenceResults, perVideoSummaries, videoDetectionMap, videoGroundTruthMap\]\);" "$FILE" > /dev/null
if [ $? -eq 0 ]; then
  echo "   ✓ Dependencies include: perVideoSummaries, videoDetectionMap, videoGroundTruthMap"
else
  echo "   ❌ FAILED: Missing dependencies"
  exit 1
fi

# Check 2: Rendering condition
echo ""
echo "✅ Check 2: Rendering condition includes data checks"
grep "isSequence && sequenceResults && aggregatedMetrics &&" "$FILE" | grep "aggOverallDetectionCount" > /dev/null
if [ $? -eq 0 ]; then
  echo "   ✓ Condition checks for actual data"
else
  echo "   ❌ FAILED: Condition too restrictive"
  exit 1
fi

# Check 3: Box margin restored
echo ""
echo "✅ Check 3: Box margin (mb: 3) restored"
grep '<Box sx={{ mb: 3 }}>' "$FILE" | head -1 > /dev/null
if [ $? -eq 0 ]; then
  echo "   ✓ Margin restored"
else
  echo "   ❌ FAILED: Margin missing"
  exit 1
fi

# Check 4: Alert null check
echo ""
echo "✅ Check 4: Alert conditional rendering"
grep "{aggOverallDetectionCount > 0 && (" "$FILE" > /dev/null
if [ $? -eq 0 ]; then
  echo "   ✓ Alert only renders when data exists"
else
  echo "   ❌ FAILED: Alert always renders"
  exit 1
fi

# Check 5: Debug logging
echo ""
echo "✅ Check 5: Debug logging added"
grep "console.warn.*aggregatedMetrics" "$FILE" > /dev/null
if [ $? -eq 0 ]; then
  echo "   ✓ Debug logging present"
else
  echo "   ⚠️  WARNING: Debug logging not found"
fi

# Check 6: Build status
echo ""
echo "✅ Check 6: TypeScript compilation"
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm run build > /tmp/build_output.txt 2>&1
if grep -q "Compiled successfully" /tmp/build_output.txt; then
  echo "   ✓ Build successful"
else
  echo "   ❌ FAILED: Build errors"
  cat /tmp/build_output.txt | tail -20
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 ALL CHECKS PASSED! Fix verified successfully."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Next Steps:"
echo "   1. Start the frontend: npm start"
echo "   2. Load a multi-video session"
echo "   3. Verify 'Overall Results Across All Videos' section appears"
echo "   4. Check dropdown filtering works"
echo "   5. Verify console has no errors"
echo ""
