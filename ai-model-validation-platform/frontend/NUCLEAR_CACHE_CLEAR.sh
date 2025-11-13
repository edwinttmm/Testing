#!/bin/bash

echo "🔥 NUCLEAR BROWSER CACHE CLEAR 🔥"
echo "=================================="
echo ""

echo "Step 1: Close ALL Chrome/Firefox windows"
read -p "Press Enter when all browser windows are closed..."

echo ""
echo "Step 2: Clearing Chrome cache..."
rm -rf ~/.cache/google-chrome/Default/Cache/*
rm -rf ~/.cache/google-chrome/Default/Code\ Cache/*
rm -rf ~/.cache/google-chrome/Default/Service\ Worker/*
rm -rf ~/.config/google-chrome/Default/Service\ Worker/*
echo "✅ Chrome cache cleared"

echo ""
echo "Step 3: Clearing Firefox cache..."
rm -rf ~/.cache/mozilla/firefox/*/cache2/*
rm -rf ~/.mozilla/firefox/*/storage/*
echo "✅ Firefox cache cleared"

echo ""
echo "Step 4: Clearing system DNS cache..."
sudo systemd-resolve --flush-caches 2>/dev/null || true
echo "✅ DNS cache cleared"

echo ""
echo "=================================="
echo "✅ ALL CACHES CLEARED"
echo "=================================="
echo ""
echo "NOW DO THIS:"
echo "1. Open browser in INCOGNITO/PRIVATE mode"
echo "2. Press F12 (DevTools)"
echo "3. Go to Application tab → Service Workers → Unregister all"
echo "4. Go to Network tab → Check 'Disable cache'"
echo "5. Navigate to http://localhost:3000"
echo "6. Hard refresh: Ctrl+Shift+R"
echo ""
echo "Or just use this URL in incognito:"
echo "http://localhost:3000?nocache=$(date +%s)"
