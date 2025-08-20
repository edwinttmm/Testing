// Clear browser cache for stale video references
// Run this in browser console to clear stale video data

console.log('🧹 Clearing stale video cache and localStorage...');

// Clear localStorage video-related data
const keysToRemove = [];
for (let i = 0; i < localStorage.length; i++) {
  const key = localStorage.key(i);
  if (key && (key.includes('video') || key.includes('3aa9fc60-f281-4eb2-90c2-b8caae792f40'))) {
    keysToRemove.push(key);
  }
}

keysToRemove.forEach(key => {
  localStorage.removeItem(key);
  console.log(`🧹 Removed localStorage key: ${key}`);
});

// Clear sessionStorage
const sessionKeysToRemove = [];
for (let i = 0; i < sessionStorage.length; i++) {
  const key = sessionStorage.key(i);
  if (key && (key.includes('video') || key.includes('3aa9fc60-f281-4eb2-90c2-b8caae792f40'))) {
    sessionKeysToRemove.push(key);
  }
}

sessionKeysToRemove.forEach(key => {
  sessionStorage.removeItem(key);
  console.log(`🧹 Removed sessionStorage key: ${key}`);
});

// Clear API cache if available
if (window && window.apiCache) {
  window.apiCache.clear();
  console.log('🧹 Cleared API cache');
}

console.log('✅ Cache clearing completed. Please refresh the page.');
console.log('Valid video IDs in database: test-video-5-04s, 83e45e59-eff7-4509-9dae-49a7cc22c363, c31e41da-4012-4784-916d-4b16be496bd7');

// Force a page refresh after a short delay
setTimeout(() => {
  window.location.reload();
}, 1000);