#!/bin/bash
# Verify Fix Script
# Checks if your code changes are present in the build

set -e

cd "$(dirname "$0")/.."

echo "🔍 VERIFICATION SCRIPT"
echo "======================"
echo ""

# Check if build exists
if [ ! -d "build" ]; then
  echo "❌ Build directory not found. Run: npm run build"
  exit 1
fi

# Search terms (customize these to your fix)
SEARCH_TERMS=(
  "videoSequenceId"
  "multiVideoSequence"
  "sequential_display_order"
)

echo "🔎 Searching for fix indicators in build..."
echo ""

FOUND_COUNT=0
for term in "${SEARCH_TERMS[@]}"; do
  COUNT=$(grep -r "$term" build/static/js/ 2>/dev/null | wc -l)
  if [ "$COUNT" -gt 0 ]; then
    echo "✅ Found '$term': $COUNT occurrences"
    FOUND_COUNT=$((FOUND_COUNT + 1))
  else
    echo "❌ NOT found: '$term'"
  fi
done

echo ""
echo "📊 Build Statistics:"
echo "   Total JS files: $(find build/static/js -name "*.js" | wc -l)"
echo "   Total bundle size: $(du -sh build/static/js | cut -f1)"
echo ""

if [ "$FOUND_COUNT" -gt 0 ]; then
  echo "✅ SUCCESS: Fix appears to be in the build ($FOUND_COUNT/${{#SEARCH_TERMS[@]}} terms found)"
  echo ""
  echo "🎯 If browser still shows old code, it's a CACHE issue."
  echo "   Solutions:"
  echo "   1. Close ALL browser tabs"
  echo "   2. Open DevTools (F12) → Network → Enable 'Disable cache'"
  echo "   3. Hard refresh: Ctrl+Shift+R"
  echo "   4. Or use INCOGNITO mode"
  echo ""
  exit 0
else
  echo "❌ WARNING: Fix NOT found in build"
  echo ""
  echo "   Possible causes:"
  echo "   1. Code not saved"
  echo "   2. TypeScript errors preventing compilation"
  echo "   3. Import/export errors"
  echo ""
  echo "   Try:"
  echo "   npm run typecheck"
  echo "   npm run build"
  echo ""
  exit 1
fi
