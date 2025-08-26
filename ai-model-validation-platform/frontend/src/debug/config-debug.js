/**
 * Configuration Debug Tool
 * Run this in browser console to debug config loading
 */

console.log('=== CONFIG DEBUG START ===');

// 1. Check window.RUNTIME_CONFIG
console.log('1. Runtime Config Check:');
console.log('window.RUNTIME_CONFIG exists:', !!window.RUNTIME_CONFIG);
if (window.RUNTIME_CONFIG) {
    console.log('Runtime Config:', window.RUNTIME_CONFIG);
} else {
    console.error('❌ window.RUNTIME_CONFIG not found!');
}

// 2. Check process.env
console.log('\n2. Process.env Check:');
console.log('process exists:', typeof process !== 'undefined');
if (typeof process !== 'undefined' && process.env) {
    console.log('REACT_APP_API_URL:', process.env.REACT_APP_API_URL);
    console.log('REACT_APP_WS_URL:', process.env.REACT_APP_WS_URL);
    console.log('REACT_APP_SOCKETIO_URL:', process.env.REACT_APP_SOCKETIO_URL);
    console.log('REACT_APP_VIDEO_BASE_URL:', process.env.REACT_APP_VIDEO_BASE_URL);
} else {
    console.error('❌ process.env not accessible!');
}

// 3. Test API service configuration
console.log('\n3. API Service Debug:');
try {
    // Import apiService if available
    if (window.apiService || (typeof require !== 'undefined')) {
        console.log('API service available');
        
        // Try to get configuration
        if (window.apiService && window.apiService.getConfiguration) {
            const config = window.apiService.getConfiguration();
            console.log('API Service Config:', config);
        }
    } else {
        console.log('API service not accessible in global scope');
    }
} catch (e) {
    console.error('Error accessing API service:', e);
}

// 4. Test actual network requests
console.log('\n4. Network Request Test:');
const testUrls = [
    'http://155.138.239.131:8000/health',
    'http://localhost:8000/health'
];

testUrls.forEach(url => {
    console.log(`Testing: ${url}`);
    fetch(url, { method: 'HEAD', mode: 'no-cors' })
        .then(() => console.log(`✅ ${url} - accessible`))
        .catch(error => console.error(`❌ ${url} - ${error.message}`));
});

// 5. Check for any hardcoded localhost references in network tab
console.log('\n5. Monitor Network Tab for localhost:8000 requests');
console.log('Open DevTools Network tab and watch for any localhost:8000 requests');

console.log('=== CONFIG DEBUG END ===');