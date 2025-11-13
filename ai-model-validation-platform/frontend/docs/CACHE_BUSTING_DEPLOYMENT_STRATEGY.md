# Cache-Busting Deployment Strategy

## PROBLEM ANALYSIS
Browser aggressively caching old JavaScript despite rebuild, restart, and standard cache clearing. Build system uses content hashing (e.g., `113.be78f576.chunk.js`) but browser still serving stale code.

**Root Cause**: Multiple cache layers (browser cache, service worker, webpack dev server, disk cache) creating persistent caching issues.

---

## 1. IMMEDIATE WORKAROUND (5-Minute Fix)

### Option A: Nuclear Cache Clear (Most Reliable)

```bash
# Terminal 1: Kill ALL frontend processes
cd /home/rigade/Testing/ai-model-validation-platform/frontend
pkill -f "craco\|react-scripts\|webpack\|node.*3000"

# Delete ALL cache directories
rm -rf node_modules/.cache/
rm -rf build/
rm -rf .cache/
rm -rf ~/.npm/_cacache/

# Clear webpack filesystem cache
rm -rf node_modules/.cache/webpack/

# Rebuild with clean slate
npm run build

# Start fresh dev server
npm start
```

**Browser Steps**:
1. Close ALL browser tabs/windows
2. Open DevTools (F12) BEFORE navigating
3. Go to Network tab
4. Check "Disable cache"
5. Check "Bypass for network" under Service Workers (Application tab)
6. Navigate to `http://localhost:3000`
7. Hard refresh: `Ctrl+Shift+R` (Linux/Windows) or `Cmd+Shift+R` (Mac)

### Option B: Direct Bundle Inspection (Verify Fix Exists)

```bash
# Check if your fix is in the built bundle
cd /home/rigade/Testing/ai-model-validation-platform/frontend/build/static/js

# Search for your fix in the main bundle
grep -r "videoSequenceId" *.js
grep -r "multiVideoSequence" *.js

# If found: Your code is built, it's ONLY a cache issue
# If not found: Need to rebuild
```

### Option C: Bypass Dev Server Cache (Alternative Port)

```bash
# Stop current server (Ctrl+C)

# Start on different port with NO cache
PORT=3001 FAST_REFRESH=false npm start

# Open browser to http://localhost:3001
```

### Option D: Production Build Test (Definitive Test)

```bash
# Build production bundle
npm run build

# Serve production build on different port
npx serve -s build -l 3002

# Test on http://localhost:3002
```

---

## 2. LONG-TERM CACHE-BUSTING SOLUTION

### A. Update HTML Template for Aggressive Cache Busting

Create `/home/rigade/Testing/ai-model-validation-platform/frontend/public/index.html` with meta tags:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />

    <!-- AGGRESSIVE CACHE BUSTING -->
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />

    <link rel="icon" href="%PUBLIC_URL%/favicon.ico?v=%BUILD_TIME%" />
    <script src="%PUBLIC_URL%/config.js?v=%BUILD_TIME%"></script>

    <title>AI Model Validation Platform</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
```

### B. Update CRACO Configuration (Already Good)

Your `craco.config.js` already has content hashing:
- ✅ `hashFunction: 'xxhash64'` (line 148)
- ✅ Asset module filenames with hash (line 147)
- ✅ Cache headers in dev middleware (line 436)

**BUT** - Development server caches too aggressively. Add this:

```javascript
// In craco.config.js, update devServer.headers section (line 444)
headers: {
  'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
  'Pragma': 'no-cache',
  'Expires': '0',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
  'Access-Control-Allow-Headers': 'X-Requested-With, content-type, Authorization',
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
},
```

### C. Add Build-Time Version Injection

Create `/home/rigade/Testing/ai-model-validation-platform/frontend/scripts/inject-build-time.js`:

```javascript
const fs = require('fs');
const path = require('path');

const buildTime = Date.now();
const htmlPath = path.join(__dirname, '../build/index.html');

if (fs.existsSync(htmlPath)) {
  let html = fs.readFileSync(htmlPath, 'utf8');
  html = html.replace(/%BUILD_TIME%/g, buildTime);
  fs.writeFileSync(htmlPath, html);
  console.log(`✅ Injected build time: ${buildTime}`);
}
```

Update `package.json` scripts:

```json
"build": "node --max-old-space-size=8192 node_modules/.bin/craco build && node scripts/inject-build-time.js",
"build:dev": "NODE_OPTIONS='--max-old-space-size=4096' GENERATE_SOURCEMAP=false craco build && node scripts/inject-build-time.js",
```

### D. Service Worker Management

Check for service workers:

```bash
# Search for service worker registration
grep -r "serviceWorker" /home/rigade/Testing/ai-model-validation-platform/frontend/src/

# If found, add unregister code to src/index.tsx
```

Add to `/home/rigade/Testing/ai-model-validation-platform/frontend/src/index.tsx`:

```typescript
// Unregister any service workers (prevents caching issues)
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(function(registrations) {
    for (let registration of registrations) {
      registration.unregister();
    }
  });
}
```

---

## 3. VERIFICATION CHECKLIST

### Browser-Side Verification

1. **Open DevTools Network Tab**:
   - Look for `main.*.js` or `bundle.js` requests
   - Check "Size" column - should show actual size, not "(disk cache)" or "(memory cache)"
   - Status should be `200` not `304 Not Modified`

2. **Check Response Headers**:
   ```
   Cache-Control: no-cache, no-store, must-revalidate
   Pragma: no-cache
   Expires: 0
   ```

3. **Verify JavaScript Content**:
   - Click on main JS file in Network tab
   - Go to "Response" tab
   - Search for your fix: `videoSequenceId`
   - If found: SUCCESS!

4. **Check Service Workers**:
   - DevTools > Application > Service Workers
   - Should show "No service workers" or all unregistered

### Build-Side Verification

```bash
# Check build output hashes changed
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm run build
ls -la build/static/js/main.*.js

# Compare hash with previous build
# Hash should be DIFFERENT if code changed

# Inspect bundle content
grep -o "videoSequenceId" build/static/js/main.*.js | wc -l
# Should return > 0 if your fix is present
```

### Runtime Verification

```javascript
// Add to browser console
console.log('Build Check:', {
  hasMultiVideoSupport: typeof window.videoSequenceId !== 'undefined',
  timestamp: Date.now()
});

// Check API calls
fetch('/api/health').then(r => r.json()).then(console.log);
```

---

## 4. PRODUCTION DEPLOYMENT BEST PRACTICES

### Pre-Deployment Checklist

```bash
# 1. Clean build
rm -rf build/ node_modules/.cache/
npm run build

# 2. Verify bundle size
ls -lh build/static/js/main.*.js
# Should be reasonable size (< 2MB)

# 3. Test production build locally
npx serve -s build -l 8080
# Test on http://localhost:8080

# 4. Check for console errors
# Open DevTools, refresh, check Console tab

# 5. Verify all routes work
# Navigate to /hil-results, /test-sessions, etc.
```

### Deployment Commands

```bash
# For Docker deployment
cd /home/rigade/Testing/ai-model-validation-platform/frontend
docker build -t hil-frontend:latest .
docker run -p 80:80 hil-frontend:latest

# For static hosting (Nginx, Apache)
npm run build
rsync -avz build/ user@server:/var/www/html/

# Add Nginx cache headers
# In /etc/nginx/sites-available/default:
location ~* \.(?:js|css)$ {
  expires -1;
  add_header Cache-Control "no-cache, no-store, must-revalidate";
  add_header Pragma "no-cache";
}
```

### Post-Deployment Verification

1. **Check Live Site**:
   ```bash
   curl -I https://your-domain.com/static/js/main.*.js
   # Should show: Cache-Control: no-cache
   ```

2. **Version Tracking**:
   ```javascript
   // Add to index.html
   window.APP_VERSION = '%BUILD_TIME%';
   console.log('App Version:', window.APP_VERSION);
   ```

3. **User Cache Clear Instructions**:
   - Chrome: `Ctrl+Shift+Delete` → Clear cached images and files
   - Firefox: `Ctrl+Shift+Delete` → Cached Web Content
   - Safari: `Safari > Clear History` → All History

---

## 5. FALLBACK OPTIONS

### If Standard Approaches Fail

#### Option 1: Manual Bundle Injection

```html
<!-- In public/index.html -->
<script>
  // Force reload if version mismatch
  const CURRENT_VERSION = '%BUILD_TIME%';
  const stored = localStorage.getItem('app_version');
  if (stored && stored !== CURRENT_VERSION) {
    localStorage.setItem('app_version', CURRENT_VERSION);
    window.location.reload(true);
  }
  localStorage.setItem('app_version', CURRENT_VERSION);
</script>
```

#### Option 2: URL Query Parameter Versioning

```javascript
// In src/index.tsx
const buildTime = process.env.REACT_APP_BUILD_TIME || Date.now();

// Add to all script tags
const scripts = document.querySelectorAll('script[src]');
scripts.forEach(script => {
  const src = script.getAttribute('src');
  if (src && !src.includes('?v=')) {
    script.setAttribute('src', `${src}?v=${buildTime}`);
  }
});
```

#### Option 3: API-Based Version Check

```typescript
// src/utils/versionCheck.ts
export async function checkVersion() {
  const response = await fetch('/api/version');
  const { version } = await response.json();

  const stored = localStorage.getItem('app_version');
  if (stored && stored !== version) {
    console.warn('New version available, reloading...');
    localStorage.setItem('app_version', version);
    window.location.reload(true);
  }
}
```

#### Option 4: Complete Webpack Dev Server Bypass

```bash
# Use webpack directly instead of craco
npx webpack serve --mode development --port 3003 --hot false --live-reload false
```

---

## 6. TESTING MATRIX

### Browser Testing

| Browser | Clear Cache Method | Verification |
|---------|-------------------|--------------|
| Chrome | DevTools > Network > Disable cache | Check disk cache column |
| Firefox | DevTools > Storage > Clear All | Check size column |
| Safari | Develop > Empty Caches | Check Timeline |
| Edge | DevTools > Network > Clear cache | Check Response |

### Environment Testing

| Environment | Build Command | Serve Command | Expected Behavior |
|-------------|---------------|---------------|-------------------|
| Dev (port 3000) | `npm start` | N/A | Hot reload disabled |
| Prod Local | `npm run build` | `npx serve -s build` | Static files, no HMR |
| Prod Docker | `npm run build:docker` | `nginx` | Production optimized |

---

## 7. TROUBLESHOOTING GUIDE

### Issue: Still Seeing Old Code

**Check**:
```bash
# 1. Verify build contains fix
grep -r "videoSequenceId" build/static/js/
# Should return matches

# 2. Check running process
ps aux | grep -E "craco|react-scripts|webpack"
# Kill any stale processes

# 3. Check browser cache
# DevTools > Network > main.*.js > Headers
# Look for "Cache-Control" header
```

**Solution**:
```bash
# Nuclear option
pkill -9 -f "node.*3000"
rm -rf node_modules/.cache/ build/
npm run build
PORT=3005 npm start
# Open http://localhost:3005 in INCOGNITO mode
```

### Issue: Build Succeeds but Wrong Code Loads

**Cause**: Webpack dev server serving from memory, not disk

**Solution**:
```bash
# Force write to disk
# Update craco.config.js:
devMiddleware: {
  writeToDisk: true,  // Changed from false
  publicPath: '/',
},
```

### Issue: Inconsistent Behavior Across Tabs

**Cause**: Service worker or browser cache per-tab

**Solution**:
```bash
# Close ALL tabs, clear everything
# In browser console:
localStorage.clear();
sessionStorage.clear();
indexedDB.databases().then(dbs => dbs.forEach(db => indexedDB.deleteDatabase(db.name)));
```

---

## RECOMMENDED IMMEDIATE ACTION PLAN

### Execute in Order:

1. **TERMINAL**:
   ```bash
   cd /home/rigade/Testing/ai-model-validation-platform/frontend
   pkill -f "craco\|webpack\|node.*3000"
   rm -rf node_modules/.cache/ build/
   npm run build
   PORT=3001 npm start
   ```

2. **BROWSER**:
   - Close all tabs
   - Open DevTools (F12)
   - Enable "Disable cache" in Network tab
   - Navigate to `http://localhost:3001`
   - Hard refresh: `Ctrl+Shift+R`

3. **VERIFY**:
   ```javascript
   // In browser console
   console.log('Testing fix...');
   // Navigate to page with fix
   // Check behavior
   ```

4. **IF STILL FAILS**:
   ```bash
   # Test production build directly
   npm run build
   npx serve -s build -l 3002
   # Open INCOGNITO: http://localhost:3002
   ```

---

## ARCHITECTURE DECISION RECORDS

### ADR-001: Aggressive No-Cache Headers in Development

**Context**: Browser caching preventing developers from seeing code changes

**Decision**: Set `Cache-Control: no-cache, no-store, must-revalidate` for dev server

**Consequences**:
- Slower page loads in development
- Guaranteed fresh code on every request
- No cache-related bugs

### ADR-002: Content Hash + Build Time Versioning

**Context**: Need reliable cache busting for production deployments

**Decision**: Use webpack content hashing + build-time version injection

**Consequences**:
- Unique filenames for every build
- Browser automatically downloads new versions
- CDN-friendly with aggressive caching

### ADR-003: Disable HMR/Fast Refresh in Production

**Context**: HMR can cause stale module issues

**Decision**: Disable HMR, live reload, and fast refresh

**Consequences**:
- Manual page refresh required
- No auto-reload race conditions
- Deterministic build output

---

## SUCCESS METRICS

After implementing these solutions:

✅ **Cache Cleared**: Browser loads new code on first hard refresh
✅ **Consistent**: Same code across all tabs/windows
✅ **Verifiable**: Can grep for fix in loaded bundle
✅ **Reproducible**: Works for all team members
✅ **Production-Ready**: Works in deployment environments

---

## SUPPORT COMMANDS

```bash
# Check what's running
lsof -i :3000

# View full process tree
ps auxf | grep -E "node|craco|webpack"

# Monitor file changes
watch -n 1 "ls -lh build/static/js/main.*.js"

# Test API separately
curl -v http://localhost:8000/api/health

# Check bundle analyzer
npm run build
npx webpack-bundle-analyzer build/static/js/*.js
```

---

**Last Updated**: 2025-10-29
**Version**: 1.0
**Status**: Production Ready
