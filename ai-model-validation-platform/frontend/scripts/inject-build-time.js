#!/usr/bin/env node
/**
 * Build Time Injection Script
 *
 * Injects unique build timestamp into HTML to force cache busting
 * Run automatically after build: npm run build
 */

const fs = require('fs');
const path = require('path');

const buildTime = Date.now();
const buildDir = path.join(__dirname, '../build');
const htmlPath = path.join(buildDir, 'index.html');

console.log('🔧 Injecting build time for cache busting...');

if (!fs.existsSync(buildDir)) {
  console.error('❌ Build directory not found. Run npm run build first.');
  process.exit(1);
}

if (!fs.existsSync(htmlPath)) {
  console.error('❌ index.html not found in build directory.');
  process.exit(1);
}

try {
  let html = fs.readFileSync(htmlPath, 'utf8');

  // Replace %BUILD_TIME% placeholder with actual timestamp
  const originalHtml = html;
  html = html.replace(/%BUILD_TIME%/g, buildTime);

  // Add build time meta tag if not present
  if (!html.includes('data-build-time')) {
    html = html.replace(
      '<head>',
      `<head>\n    <meta name="build-time" content="${buildTime}" data-build-time="${buildTime}">`
    );
  }

  // Add version check script
  const versionScript = `
    <script>
      // Cache busting version check
      (function() {
        const BUILD_VERSION = '${buildTime}';
        const STORAGE_KEY = 'app_build_version';

        try {
          const stored = localStorage.getItem(STORAGE_KEY);

          if (stored && stored !== BUILD_VERSION) {
            console.log('🔄 New version detected, clearing cache...', {
              old: stored,
              new: BUILD_VERSION
            });

            // Clear all caches
            localStorage.clear();
            sessionStorage.clear();

            // Unregister service workers
            if ('serviceWorker' in navigator) {
              navigator.serviceWorker.getRegistrations().then(function(registrations) {
                registrations.forEach(function(registration) {
                  registration.unregister();
                });
              });
            }

            localStorage.setItem(STORAGE_KEY, BUILD_VERSION);

            // Force reload from server
            window.location.reload(true);
            return;
          }

          localStorage.setItem(STORAGE_KEY, BUILD_VERSION);
          console.log('✅ App version:', BUILD_VERSION);

        } catch (error) {
          console.warn('Version check failed:', error);
        }
      })();
    </script>
  `;

  // Inject version script before closing head tag
  if (!html.includes('app_build_version')) {
    html = html.replace('</head>', `${versionScript}\n  </head>`);
  }

  // Write updated HTML
  if (html !== originalHtml) {
    fs.writeFileSync(htmlPath, html);
    console.log('✅ Build time injected:', buildTime);
    console.log('✅ Version check script added');
    console.log('📦 Bundle ready for deployment with cache busting');
  } else {
    console.log('ℹ️  No changes needed (already injected)');
  }

  // Also update manifest.json if it exists
  const manifestPath = path.join(buildDir, 'manifest.json');
  if (fs.existsSync(manifestPath)) {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    manifest.version = buildTime.toString();
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
    console.log('✅ Manifest updated with version:', buildTime);
  }

  process.exit(0);

} catch (error) {
  console.error('❌ Error injecting build time:', error);
  process.exit(1);
}
