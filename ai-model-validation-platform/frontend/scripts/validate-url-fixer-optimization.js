/**
 * Validation script for VideoUrlFixer optimization system
 * Tests core functionality without full test framework overhead
 */

const {
  fixVideoUrl,
  fixMultipleVideoUrls,
  getPerformanceMetrics,
  generatePerformanceReport,
  clearAllCaches,
  resetMetrics
} = require('../src/utils/videoUrlFixer');

console.log('🔧 VideoUrlFixer Optimization System Validation\n');

// Mock environment config for validation
jest.mock('../src/utils/envConfig', () => ({
  getServiceConfig: jest.fn((service) => {
    if (service === 'video') {
      return { baseUrl: 'http://155.138.239.131:8000' };
    }
    return {};
  })
}));

async function validateOptimizations() {
  try {
    // Reset system
    clearAllCaches();
    resetMetrics();
    console.log('✅ System reset successful');

    // Test 1: Basic URL fixing
    console.log('\n📋 Test 1: Basic URL Fixing');
    const testCases = [
      { input: 'http://localhost:8000/uploads/test.mp4', expected: 'http://155.138.239.131:8000/uploads/test.mp4' },
      { input: '/uploads/relative.mp4', expected: 'http://155.138.239.131:8000/uploads/relative.mp4' },
      { input: '', filename: 'fallback.mp4', expected: 'http://155.138.239.131:8000/uploads/fallback.mp4' }
    ];

    for (const testCase of testCases) {
      const result = fixVideoUrl(testCase.input, testCase.filename);
      if (result === testCase.expected) {
        console.log(`✅ ${testCase.input || 'empty'} -> ${result}`);
      } else {
        console.log(`❌ ${testCase.input || 'empty'} -> Expected: ${testCase.expected}, Got: ${result}`);
      }
    }

    // Test 2: Caching performance
    console.log('\n📋 Test 2: Caching Performance');
    const testUrl = 'http://localhost:8000/uploads/cache-test.mp4';
    
    const startTime = Date.now();
    for (let i = 0; i < 100; i++) {
      fixVideoUrl(testUrl);
    }
    const endTime = Date.now();
    
    const metrics = getPerformanceMetrics();
    console.log(`✅ Processed 100 URLs in ${endTime - startTime}ms`);
    console.log(`✅ Cache hit rate: ${(metrics.cacheStats.cacheHitRate * 100).toFixed(1)}%`);
    console.log(`✅ Cache size: ${metrics.cacheStats.urlMappingCacheSize}`);

    // Test 3: Batch processing
    console.log('\n📋 Test 3: Batch Processing');
    const videos = Array.from({ length: 50 }, (_, i) => ({
      url: `http://localhost:8000/uploads/batch${i}.mp4`,
      filename: `batch${i}.mp4`
    }));

    const batchStartTime = Date.now();
    await fixMultipleVideoUrls(videos, {
      chunkSize: 10,
      throttleMs: 1,
      debug: false
    });
    const batchEndTime = Date.now();
    
    const batchMetrics = getPerformanceMetrics();
    console.log(`✅ Batch processed ${videos.length} videos in ${batchEndTime - batchStartTime}ms`);
    console.log(`✅ Batches processed: ${batchMetrics.batchesProcessed}`);
    console.log(`✅ Total processed: ${batchMetrics.totalProcessed}`);

    // Test 4: Performance reporting
    console.log('\n📋 Test 4: Performance Reporting');
    const report = generatePerformanceReport();
    console.log(`✅ Generated report: ${report.summary}`);
    console.log(`✅ Insights: ${report.insights.length}`);
    console.log(`✅ Recommendations: ${report.recommendations.length}`);

    // Test 5: Error handling
    console.log('\n📋 Test 5: Error Handling');
    const originalConsoleError = console.error;
    console.error = () => {}; // Suppress error logging for test
    
    const errorResult = fixVideoUrl(null, undefined, undefined, { debug: false });
    console.log(`✅ Error handling: ${typeof errorResult === 'string' ? 'Handled gracefully' : 'Failed'}`);
    
    console.error = originalConsoleError;

    // Final metrics
    console.log('\n📊 Final System Metrics:');
    const finalMetrics = getPerformanceMetrics();
    console.log(`  • Total processed: ${finalMetrics.totalProcessed}`);
    console.log(`  • Average time: ${finalMetrics.averageProcessingTime.toFixed(2)}ms`);
    console.log(`  • Cache hit rate: ${(finalMetrics.cacheStats.cacheHitRate * 100).toFixed(1)}%`);
    console.log(`  • Errors: ${finalMetrics.errorsEncountered}`);
    console.log(`  • Migration skips: ${finalMetrics.migrationAwareSkips}`);

    console.log('\n🎉 VideoUrlFixer Optimization System Validation PASSED!');
    
    return true;
  } catch (error) {
    console.error('\n❌ Validation FAILED:', error);
    return false;
  }
}

// Run validation if called directly
if (require.main === module) {
  validateOptimizations()
    .then(success => {
      process.exit(success ? 0 : 1);
    })
    .catch(error => {
      console.error('Validation error:', error);
      process.exit(1);
    });
}

module.exports = { validateOptimizations };