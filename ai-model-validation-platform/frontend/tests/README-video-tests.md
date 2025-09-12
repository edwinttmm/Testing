# Video Playback System Testing Suite

## 🎬 Overview

This comprehensive testing suite validates the enhanced video playback system, ensuring robust performance across different browsers, network conditions, and use cases. The test suite covers all aspects of video functionality from basic playback to advanced features like LabJack hardware synchronization.

## 📋 Test Coverage

### Core Functionality Tests
- ✅ **Sequential Video Playback**: End-to-end playlist execution
- ✅ **Video Queue Management**: Add/remove/reorder videos in playlist  
- ✅ **User Controls**: Play, pause, stop, skip, seek functionality
- ✅ **Fullscreen Support**: Cross-browser fullscreen API compatibility
- ✅ **Video Transitions**: Smooth transitions between videos with configurable latency
- ✅ **Progress Tracking**: Accurate progress reporting and state management

### Error Handling & Recovery Tests  
- ✅ **Missing Videos**: Graceful handling of 404 errors
- ✅ **Corrupted Files**: Decode error recovery and user notification
- ✅ **Network Issues**: Timeout handling and retry logic
- ✅ **Memory Management**: Leak prevention and cleanup validation
- ✅ **Browser Compatibility**: Feature detection and graceful degradation

### Performance & Optimization Tests
- ✅ **Loading Performance**: Video load time optimization
- ✅ **Memory Usage**: Memory consumption monitoring and management
- ✅ **Concurrent Videos**: Multiple video instance performance
- ✅ **Large File Handling**: Performance with high-resolution/long videos
- ✅ **Preloading Strategies**: Efficient video buffering techniques

### Browser Compatibility Tests
- ✅ **Chrome**: Standard fullscreen API, H.264/WebM support
- ✅ **Firefox**: Mozilla fullscreen API, AV1 codec support  
- ✅ **Safari**: WebKit fullscreen API, H.264-only support
- ✅ **Edge**: Modern Edge features and Windows optimizations
- ✅ **Mobile Browsers**: Touch controls and autoplay policies

### LabJack Hardware Integration Tests
- ✅ **Device Connection**: T4/T7/T8 device detection and configuration
- ✅ **Data Synchronization**: Video-sensor timestamp correlation
- ✅ **High-Speed Acquisition**: Sub-millisecond precision timing
- ✅ **Multi-Device Support**: Synchronization across multiple LabJack units
- ✅ **Real-Time Performance**: Buffer management and data streaming

## 🧪 Test Files

| Test File | Description | Priority | Duration |
|-----------|-------------|----------|----------|
| `video-playback-comprehensive.test.tsx` | Core playback functionality | High | ~2min |
| `video-browser-compatibility.test.tsx` | Cross-browser feature support | High | ~1.5min |
| `video-performance-benchmarks.test.tsx` | Performance optimization | Medium | ~3min |
| `video-labjack-integration.test.tsx` | Hardware synchronization | Medium | ~2.5min |
| `video-system-integration.test.tsx` | Existing system integration | High | ~1min |

## 🚀 Running Tests

### Quick Test Commands

```bash
# Run all video tests
npm run test:video

# Run comprehensive playback tests with coverage
npm run test:video-comprehensive

# Run browser compatibility tests
npm run test:video-browser-compat

# Run performance benchmarks
npm run test:video-performance

# Run LabJack integration tests
npm run test:video-labjack

# Run complete test suite with automated runner
npm run test:video-all

# Run tests in parallel with coverage reporting
npm run test:video-all-coverage
```

### Advanced Test Execution

```bash
# Sequential execution (for debugging)
npm run test:video-all -- --sequential

# Verbose output with detailed logging
npm run test:video-all -- --verbose

# Custom timeout (in milliseconds)
npm run test:video-all -- --timeout 900000

# Skip coverage reporting
npm run test:video-all -- --no-coverage
```

### Manual Jest Execution

```bash
# Run specific test file
npx jest tests/video-playback-comprehensive.test.tsx --verbose

# Run with coverage
npx jest tests/video-*.test.tsx --coverage --coverageDirectory=coverage/video-tests

# Debug mode
npx jest tests/video-playback-comprehensive.test.tsx --verbose --no-cache --runInBand
```

## 📊 Test Scenarios

The test suite includes comprehensive scenarios defined in `video-test-scenarios.json`:

### Happy Path Scenarios
- **Sequential Playback**: 3 videos playing in sequence with fullscreen
- **User Interaction**: Pause/resume/skip controls during playback
- **Queue Management**: Add/remove/reorder videos in playlist

### Error Scenarios  
- **Missing Videos**: Handle 404 errors and skip to next video
- **Corrupted Files**: Decode errors with retry logic
- **Network Issues**: Slow connections and timeout handling

### Performance Scenarios
- **Large Files**: 100MB+ video files with memory monitoring
- **Multiple Instances**: 5+ concurrent video players
- **Memory Stress**: 50+ sequential video loads

### Browser Compatibility
- **Chrome**: Standard APIs and modern codec support
- **Firefox**: Mozilla APIs and advanced codec support  
- **Safari**: WebKit APIs and limited codec support
- **Edge**: Modern features with Windows optimizations

### LabJack Integration
- **Basic Sync**: 1kHz sampling with T7 device
- **High-Speed**: 50kHz sampling with T8 device
- **Multi-Device**: Synchronized T4/T7/T8 acquisition

## 🎯 Coverage Requirements

| Metric | Target | Current |
|--------|--------|---------|
| Lines | ≥90% | TBD |
| Functions | ≥85% | TBD |
| Branches | ≥80% | TBD |
| Statements | ≥90% | TBD |

## 📈 Performance Benchmarks

### Loading Performance Targets
- Small videos (<10MB): <2 seconds
- Medium videos (10-50MB): <5 seconds  
- Large videos (50-200MB): <15 seconds
- Ultra videos (>200MB): <30 seconds

### Memory Usage Limits
- Single video instance: <50MB
- Multiple instances (5): <200MB total
- Memory leak tolerance: <1MB per hour

### Synchronization Precision
- Basic sync (T7): ±1ms accuracy
- High-speed sync (T8): ±0.1ms accuracy  
- Multi-device sync: ±0.5ms across devices

## 🐛 Debugging Test Failures

### Common Issues

1. **Timeout Errors**
   ```bash
   # Increase timeout for slow operations
   npm run test:video-all -- --timeout 900000
   ```

2. **Mock Issues**
   ```bash
   # Clear Jest cache
   npx jest --clearCache
   # Run single test for debugging
   npx jest tests/video-playback-comprehensive.test.tsx --runInBand
   ```

3. **Memory Issues**
   ```bash
   # Run with increased memory
   node --max-old-space-size=4096 node_modules/.bin/jest
   ```

4. **Browser API Mocks**
   - Check `jsdom` environment setup
   - Verify fullscreen API mocks
   - Validate video element mocks

### Test Environment Debugging

```javascript
// Add to test file for debugging
beforeEach(() => {
  console.log('Test environment:', {
    jsdom: typeof window !== 'undefined',
    videoSupport: !!(document.createElement('video').canPlayType),
    fullscreenSupport: !!document.fullscreenEnabled
  });
});
```

## 📋 Test Maintenance

### Adding New Tests

1. **Create Test File**: Follow naming convention `video-[feature].test.tsx`
2. **Add to Runner**: Update `VideoTestRunner.testSuites` array
3. **Update Package.json**: Add new npm script if needed
4. **Document Scenarios**: Add to `video-test-scenarios.json`

### Updating Test Scenarios

1. **Modify JSON**: Update `video-test-scenarios.json`
2. **Test Validation**: Ensure scenarios are valid
3. **Update Documentation**: Reflect changes in this README

### Performance Benchmarking

1. **Baseline Metrics**: Record current performance
2. **Regression Detection**: Compare against historical data
3. **Optimization Tracking**: Monitor improvements over time

## 🔧 Configuration

### Jest Configuration (jest.config.js)

```javascript
module.exports = {
  testEnvironment: 'jsdom',
  testTimeout: 30000,
  setupFilesAfterEnv: ['<rootDir>/tests/setup-video-tests.ts'],
  moduleNameMapping: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
  collectCoverageFrom: [
    'src/components/SequentialVideoManager.tsx',
    'src/components/VideoAnnotationPlayer.tsx',
    'src/utils/videoPlaybackManager.ts',
    'src/hooks/useVideoPlayer.ts'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 85,
      lines: 90,
      statements: 90
    }
  }
};
```

### Test Environment Setup

Create `tests/setup-video-tests.ts`:

```typescript
import '@testing-library/jest-dom';

// Mock video element globally
global.HTMLMediaElement.prototype.play = jest.fn(() => Promise.resolve());
global.HTMLMediaElement.prototype.pause = jest.fn();
global.HTMLMediaElement.prototype.load = jest.fn();

// Mock fullscreen APIs
Object.defineProperty(document, 'fullscreenEnabled', { value: true });
Object.defineProperty(document, 'webkitFullscreenEnabled', { value: true });

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));
```

## 📤 Test Reports

The automated test runner generates comprehensive reports:

### Generated Files
- `coverage/video-test-report.json`: Detailed JSON report
- `coverage/video-test-report-summary.txt`: Human-readable summary  
- `coverage/video-tests/`: HTML coverage reports
- `coverage/video-tests/lcov.info`: Coverage data for CI/CD

### Report Contents
- Test execution summary
- Individual suite results  
- Performance metrics
- Coverage statistics
- Recommendations for improvement

## 🚀 Continuous Integration

### GitHub Actions Integration

```yaml
name: Video Playback Tests
on: [push, pull_request]
jobs:
  video-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run test:video-all-coverage
      - uses: codecov/codecov-action@v3
        with:
          file: ./coverage/video-tests/lcov.info
```

### Quality Gates

- ✅ All tests must pass
- ✅ Coverage must meet minimum thresholds
- ✅ Performance benchmarks must not regress >10%
- ✅ No memory leaks detected
- ✅ Browser compatibility maintained

---

## 🎯 Next Steps

1. **Run Initial Test Suite**: Execute `npm run test:video-all-coverage`
2. **Review Coverage Report**: Check generated HTML reports
3. **Address Failures**: Fix any failing tests
4. **Performance Baseline**: Record initial performance metrics
5. **CI/CD Integration**: Add to deployment pipeline

For questions or issues with the video testing suite, please refer to the test files or create an issue with the `video-testing` label.