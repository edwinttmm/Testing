# Quick Cache Fix - TL;DR

## Problem
Browser showing old JavaScript even after rebuild and restart.

## Immediate Fix (Choose ONE)

### Option 1: Nuclear Clear (Most Reliable)
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Run the nuclear clear script
npm run cache:clear

# Start on new port
PORT=3001 npm start

# Open browser: http://localhost:3001
# Enable DevTools > Network > "Disable cache"
# Hard refresh: Ctrl+Shift+R
```

### Option 2: Verify Fix is Built
```bash
# Check if your code is in the build
npm run verify:fix

# If found: It's ONLY a cache issue
# If not found: Need to rebuild
```

### Option 3: Test Production Build
```bash
# Build and serve production bundle
npm run build
npx serve -s build -l 3002

# Open INCOGNITO: http://localhost:3002
```

---

## Browser Steps (CRITICAL)

1. Close ALL browser tabs/windows
2. Open DevTools (F12) BEFORE navigating
3. Network tab → Check "Disable cache"
4. Application tab → Service Workers → "Bypass for network"
5. Navigate to site
6. Hard refresh: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)

---

## Verification

### Check if Fix is Loaded
```javascript
// Browser console
console.log('Version check:', localStorage.getItem('app_build_version'));

// Check Network tab
// Look for main.*.js
// Size should show actual bytes, NOT "(disk cache)"
```

### Check Build Contains Fix
```bash
# Search for your code in build
grep -r "videoSequenceId" build/static/js/
# Should return results if fix is present
```

---

## New NPM Scripts

```bash
npm run cache:clear          # Clear all caches and rebuild
npm run cache:clear-full     # Also clear npm cache (slower)
npm run verify:fix           # Check if fix is in build
npm run deploy:prod          # Full production deployment workflow
```

---

## If Nothing Works

### Last Resort
```bash
# Kill everything
pkill -9 -f "node.*3000"

# Nuclear clear
rm -rf node_modules/.cache/ build/

# Rebuild
npm run build

# Start on different port
PORT=3005 npm start

# Open in INCOGNITO mode: http://localhost:3005
```

### Alternative Testing
```bash
# Bypass dev server entirely
npm run build
python3 -m http.server 8080 --directory build

# Open: http://localhost:8080
```

---

## What Was Changed

### Files Updated
1. `craco.config.js` - Added aggressive no-cache headers
2. `package.json` - Added cache clearing scripts
3. `public/index.html` - Added cache-busting meta tags
4. `scripts/inject-build-time.js` - Auto version injection
5. `scripts/nuclear-cache-clear.sh` - One-command cache clear
6. `scripts/verify-fix.sh` - Verify fix is in build

### Key Changes
- Dev server now sends `Cache-Control: no-cache, no-store, must-revalidate`
- Build process injects unique timestamp for version tracking
- Automatic version check script clears cache on version mismatch
- URL parameters include `?v=%BUILD_TIME%` for cache busting

---

## Architecture Decisions

### Why Aggressive No-Cache?
- Guarantees developers see fresh code
- Prevents cache-related debugging nightmares
- Slightly slower loads acceptable in dev

### Why Build-Time Injection?
- Unique version per build
- Automatic cache invalidation
- No manual versioning needed

### Why Multiple Scripts?
- Different use cases (quick fix vs full clear)
- Debugging options (verify without deploying)
- Production deployment workflow

---

## Success Metrics

After fix:
- ✅ New code loads on first hard refresh
- ✅ DevTools Network shows actual file size, not cache
- ✅ Version number in console matches build
- ✅ All team members can reproduce

---

## Support

If still having issues:

1. Check running processes: `lsof -i :3000`
2. View console errors in DevTools
3. Test API separately: `curl http://localhost:8000/api/health`
4. Check backend logs for errors

---

**Full Documentation**: See `CACHE_BUSTING_DEPLOYMENT_STRATEGY.md`
