#!/bin/bash
# IMMEDIATE CACHE FIX - Run this right now
# No arguments needed, just execute: ./FIX_CACHE_NOW.sh

set -e

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  🚀 IMMEDIATE CACHE FIX"
echo "════════════════════════════════════════════════════════════════"
echo ""

cd "$(dirname "$0")"

# Step 1: Kill running processes
echo "⏹️  Step 1/5: Stopping running dev servers..."
pkill -f "craco" 2>/dev/null && echo "   ✓ Killed craco" || echo "   ℹ No craco processes"
pkill -f "webpack-dev-server" 2>/dev/null && echo "   ✓ Killed webpack" || echo "   ℹ No webpack processes"
pkill -f "node.*3000" 2>/dev/null && echo "   ✓ Killed node on port 3000" || echo "   ℹ No node on 3000"

sleep 1

# Step 2: Clear caches
echo ""
echo "🗑️  Step 2/5: Clearing all caches..."
rm -rf node_modules/.cache/ 2>/dev/null && echo "   ✓ Cleared node_modules/.cache" || true
rm -rf build/ 2>/dev/null && echo "   ✓ Cleared build/" || true
rm -rf .cache/ 2>/dev/null && echo "   ✓ Cleared .cache/" || true

# Step 3: Rebuild
echo ""
echo "🔨 Step 3/5: Rebuilding application..."
npm run build 2>&1 | tail -10

# Step 4: Verify fix is present
echo ""
echo "🔍 Step 4/5: Verifying fix is in build..."

if [ -f "scripts/verify-fix.sh" ]; then
  bash scripts/verify-fix.sh
else
  # Manual verification
  if grep -rq "videoSequenceId" build/static/js/ 2>/dev/null; then
    echo "   ✅ Fix found in build!"
  else
    echo "   ⚠️  Warning: Fix not found in build"
  fi
fi

# Step 5: Instructions
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ CACHE CLEARED & REBUILT"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📋 NEXT STEPS:"
echo ""
echo "1️⃣  Start dev server on NEW port:"
echo "   PORT=3001 npm start"
echo ""
echo "2️⃣  In browser (BEFORE navigating):"
echo "   • Open DevTools (F12)"
echo "   • Network tab → Enable 'Disable cache'"
echo "   • Application tab → Service Workers → 'Bypass for network'"
echo ""
echo "3️⃣  Navigate to:"
echo "   http://localhost:3001"
echo ""
echo "4️⃣  Hard refresh:"
echo "   • Windows/Linux: Ctrl+Shift+R"
echo "   • Mac: Cmd+Shift+R"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "🔥 ALTERNATIVE: Test production build immediately:"
echo "   npx serve -s build -l 3002"
echo "   Then open INCOGNITO: http://localhost:3002"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
