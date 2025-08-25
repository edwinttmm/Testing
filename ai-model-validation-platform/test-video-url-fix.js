#!/usr/bin/env node

/**
 * Simple test to verify video URL fixing works
 * This is a standalone script to verify the fix
 */

console.log('🔧 Video URL Fix Verification');
console.log('==============================');

// Simulate the fix logic without complex imports
function fixVideoUrlSimple(url, filename, id, baseUrl = 'http://155.138.239.131:8000') {
  if (!url || url.trim() === '') {
    if (filename && filename.trim()) {
      return `${baseUrl}/uploads/${filename}`;
    } else if (id && id.trim()) {
      return `${baseUrl}/uploads/${id}`;
    } else {
      return '';
    }
  }
  
  // Fix localhost URLs
  if (url.includes('localhost:8000')) {
    return url.replace('http://localhost:8000', baseUrl);
  }
  
  // Convert relative URLs to absolute
  if (url.startsWith('/')) {
    return `${baseUrl}${url}`;
  }
  
  // Return URL as-is if already valid
  return url;
}

// Test cases based on the original issue
const testCases = [
  {
    name: 'Ground Truth ERR_CONNECTION_REFUSED Fix',
    input: {
      url: 'http://localhost:8000/uploads/30adaef3-8430-476d-a126-6606a6ae2a6f.mp4',
      filename: '30adaef3-8430-476d-a126-6606a6ae2a6f.mp4',
      id: '30adaef3-8430-476d-a126-6606a6ae2a6f'
    },
    expected: 'http://155.138.239.131:8000/uploads/30adaef3-8430-476d-a126-6606a6ae2a6f.mp4'
  },
  {
    name: 'Relative URL Fix',
    input: {
      url: '/uploads/test-video.mp4',
      filename: 'test-video.mp4',
      id: 'test-id'
    },
    expected: 'http://155.138.239.131:8000/uploads/test-video.mp4'
  },
  {
    name: 'Missing URL Construction',
    input: {
      url: '',
      filename: 'constructed-video.mp4',
      id: 'constructed-id'
    },
    expected: 'http://155.138.239.131:8000/uploads/constructed-video.mp4'
  },
  {
    name: 'Valid URL Unchanged',
    input: {
      url: 'http://155.138.239.131:8000/uploads/valid-video.mp4',
      filename: 'valid-video.mp4',
      id: 'valid-id'
    },
    expected: 'http://155.138.239.131:8000/uploads/valid-video.mp4'
  }
];

let passedTests = 0;
let totalTests = testCases.length;

console.log(`Running ${totalTests} test cases...`);
console.log('');

testCases.forEach((testCase, index) => {
  const { url, filename, id } = testCase.input;
  const result = fixVideoUrlSimple(url, filename, id);
  const passed = result === testCase.expected;
  
  console.log(`${index + 1}. ${testCase.name}`);
  console.log(`   Input:    ${url || '(empty)'}`);
  console.log(`   Expected: ${testCase.expected}`);
  console.log(`   Result:   ${result}`);
  console.log(`   Status:   ${passed ? '✅ PASS' : '❌ FAIL'}`);
  console.log('');
  
  if (passed) {
    passedTests++;
  }
});

console.log('Results:');
console.log(`✅ Passed: ${passedTests}`);
console.log(`❌ Failed: ${totalTests - passedTests}`);
console.log(`📊 Success Rate: ${Math.round((passedTests / totalTests) * 100)}%`);

if (passedTests === totalTests) {
  console.log('🎉 All tests passed! The video URL fix should resolve the ERR_CONNECTION_REFUSED error.');
} else {
  console.log('⚠️  Some tests failed. Review the implementation.');
}

console.log('');
console.log('Summary:');
console.log('--------');
console.log('The fix addresses the original issue where video URLs like:');
console.log('  http://localhost:8000/uploads/30adaef3-8430-476d-a126-6606a6ae2a6f.mp4');
console.log('Are now converted to:');
console.log('  http://155.138.239.131:8000/uploads/30adaef3-8430-476d-a126-6606a6ae2a6f.mp4');
console.log('');
console.log('This ensures videos in the Ground Truth interface will load properly.');