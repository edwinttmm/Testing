#!/bin/bash
# Nuclear Cache Clear Script
# Use when nothing else works to clear ALL caches

set -e

echo "🚨 NUCLEAR CACHE CLEAR INITIATED"
echo "=================================="

cd "$(dirname "$0")/.."

# Kill all Node processes on port 3000-3010
echo "🔫 Killing all frontend processes..."
pkill -f "craco" 2>/dev/null || true
pkill -f "react-scripts" 2>/dev/null || true
pkill -f "webpack-dev-server" 2>/dev/null || true
pkill -f "node.*300[0-9]" 2>/dev/null || true

sleep 2

# Clear all cache directories
echo "🗑️  Removing cache directories..."
rm -rf node_modules/.cache/ 2>/dev/null || true
rm -rf build/ 2>/dev/null || true
rm -rf .cache/ 2>/dev/null || true
rm -rf dist/ 2>/dev/null || true

# Clear webpack cache
echo "🗑️  Clearing webpack filesystem cache..."
rm -rf node_modules/.cache/webpack/ 2>/dev/null || true
rm -rf node_modules/.cache/babel-loader/ 2>/dev/null || true
rm -rf node_modules/.cache/terser-webpack-plugin/ 2>/dev/null || true

# Clear npm cache (optional, can be slow)
if [ "$1" == "--full" ]; then
  echo "🗑️  Clearing npm cache..."
  npm cache clean --force
fi

# Rebuild
echo "🔨 Rebuilding application..."
npm run build

# Display build info
echo ""
echo "✅ CACHE CLEARED SUCCESSFULLY"
echo "=================================="
echo ""
echo "📦 Build output:"
ls -lh build/static/js/main.*.js 2>/dev/null || echo "No main bundle found"
echo ""
echo "🚀 Ready to start dev server on new port:"
echo "   PORT=3001 npm start"
echo ""
echo "🌐 Or test production build:"
echo "   npx serve -s build -l 3002"
echo ""
echo "🔥 CRITICAL: Open browser in INCOGNITO mode for guaranteed fresh load"
echo ""
