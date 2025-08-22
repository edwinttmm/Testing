# AI Model Validation Platform - Comprehensive Test Suite

## Overview

This comprehensive test suite validates the complete AI Model Validation Platform workflow, covering all critical user scenarios, edge cases, and performance requirements. The test suite is designed to ensure reliability, performance, and user experience across the entire platform.

## Test Categories

### 🔧 Unit Tests
- **Video Upload Process** (`unit/video-upload.test.ts`)
  - Small and large file uploads
  - Progress tracking and chunking
  - Error handling and validation
  - Concurrent upload operations
  - File format validation

- **Video Player Functionality** (`unit/video-player-functionality.test.tsx`)
  - Playback controls (play, pause, seek, volume)
  - Annotation display and interaction
  - Frame-by-frame navigation
  - Canvas rendering optimization
  - Error recovery mechanisms

### 🔗 Integration Tests
- **Project Video Workflow** (`integration/project-video-workflow.test.ts`)
  - Project creation and management
  - Video-project linking
  - Data consistency validation
  - Concurrent operations handling

- **Ground Truth Annotations** (`integration/ground-truth-annotations.test.ts`)
  - Annotation creation and editing
  - Validation workflows
  - Export/import functionality
  - Session management
  - Multi-user collaboration

- **Database Persistence** (`integration/database-persistence.test.py`)
  - Transaction integrity
  - Cascade delete operations
  - Foreign key constraints
  - Concurrent access handling
  - Data consistency checks

- **Frontend-Backend Data Flow** (`integration/frontend-backend-dataflow.test.ts`)
  - API communication patterns
  - State synchronization
  - Real-time updates
  - Cache management
  - Error propagation

- **Error Scenarios and Recovery** (`integration/error-scenarios-recovery.test.ts`)
  - Network failure handling
  - Server error responses
  - Validation error recovery
  - Resource cleanup
  - User experience during failures

### 🎭 End-to-End Tests
- **Complete User Workflow** (`e2e/complete-user-workflow.test.ts`)
  - Full user journey testing
  - Multi-user collaboration scenarios
  - Large file handling
  - Cross-browser compatibility
  - Accessibility compliance

### ⚡ Performance Tests
- **Large File Upload** (`performance/large-file-upload.test.ts`)
  - Upload performance benchmarks
  - Memory usage monitoring
  - Concurrent upload handling
  - Network adaptation
  - Progress reporting accuracy

## Quick Start

### Prerequisites
```bash
# Install dependencies
npm install
pip install -r requirements.txt

# Install Playwright for E2E tests
npx playwright install

# Set up test database
createdb test_ai_validation
```

### Running All Tests
```bash
# Run the comprehensive test suite
./tests/comprehensive-suite/run-all-tests.sh
```

### Running Individual Test Categories
```bash
# Unit tests
npm run test tests/comprehensive-suite/unit/

# Integration tests
npm run test tests/comprehensive-suite/integration/
python -m pytest tests/comprehensive-suite/integration/

# E2E tests
npx playwright test tests/comprehensive-suite/e2e/

# Performance tests
npm run test tests/comprehensive-suite/performance/
```

## Test Configuration

### Environment Variables
```bash
# API Configuration
export REACT_APP_API_URL=http://localhost:8000
export REACT_APP_WS_URL=ws://localhost:8000

# Database Configuration
export DATABASE_URL=postgresql://test:test@localhost/test_db
export REDIS_URL=redis://localhost:6379/1

# Test Configuration
export TEST_TIMEOUT=30000
export TEST_VIDEO_SIZE_LIMIT=500MB
export TEST_CONCURRENT_UPLOADS=3
```

### Test Data Management

Test fixtures are located in `fixtures/test-videos.ts` and include:
- Mock video files of various sizes
- Sample annotation data
- Test project configurations
- User scenario data

## Performance Thresholds

| Test Category | Metric | Threshold |
|---------------|---------|-----------|
| Small File Upload | Time | < 5 seconds |
| Large File Upload | Time | < 60 seconds |
| Video Player Load | Time | < 3 seconds |
| Annotation Rendering | FPS | > 30 FPS |
| Memory Usage | Peak | < 500 MB |
| Database Queries | Time | < 2 seconds |

## Test Reports

### HTML Report
The test runner generates a comprehensive HTML report with:
- Test execution summary
- Category-wise results
- Performance metrics
- Recommendations for improvements
- Links to detailed logs

### Log Files
Individual log files are generated for each test category:
- `unit_video_upload_TIMESTAMP.log`
- `integration_database_TIMESTAMP.log`
- `e2e_workflow_TIMESTAMP.log`
- etc.

## Continuous Integration

### GitHub Actions Workflow
```yaml
name: Comprehensive Test Suite
on: [push, pull_request]
jobs:
  comprehensive-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: ./tests/comprehensive-suite/run-all-tests.sh
```

### Local Development
```bash
# Run tests before committing
git add .
./tests/comprehensive-suite/run-all-tests.sh && git commit -m "Your commit message"
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```bash
   # Ensure test database is running
   pg_ctl status
   createdb test_ai_validation
   ```

2. **File Upload Timeouts**
   ```bash
   # Increase timeout for large files
   export TEST_TIMEOUT=60000
   ```

3. **Memory Issues During Tests**
   ```bash
   # Increase Node.js memory limit
   export NODE_OPTIONS="--max-old-space-size=4096"
   ```

4. **Video Player Tests Failing**
   ```bash
   # Ensure proper video codec support
   npm install --save-dev @types/video
   ```

### Debug Mode
```bash
# Run with debug output
DEBUG=1 ./tests/comprehensive-suite/run-all-tests.sh

# Run specific test with verbose output
npm run test tests/comprehensive-suite/unit/video-upload.test.ts -- --verbose
```

## Contributing

### Adding New Tests
1. Create test file in appropriate category directory
2. Follow naming convention: `feature-name.test.{ts,tsx,py}`
3. Add test to run-all-tests.sh script
4. Update this README with test description

### Test Categories Guidelines
- **Unit Tests**: Test individual functions/components in isolation
- **Integration Tests**: Test interactions between components/services
- **E2E Tests**: Test complete user workflows
- **Performance Tests**: Validate performance requirements

### Best Practices
- Use descriptive test names
- Include setup and teardown procedures
- Mock external dependencies appropriately
- Add performance assertions where relevant
- Document expected behavior clearly

## Architecture

```
tests/comprehensive-suite/
├── fixtures/           # Test data and utilities
├── unit/              # Unit tests
├── integration/       # Integration tests
├── e2e/              # End-to-end tests
├── performance/      # Performance tests
├── utils/            # Test utilities and helpers
├── mocks/            # Mock implementations
├── reports/          # Generated test reports
├── run-all-tests.sh  # Main test runner
└── README.md         # This file
```

## Support

For questions or issues with the test suite:
1. Check the troubleshooting section above
2. Review generated test reports and logs
3. Open an issue with detailed error information
4. Include environment details and test configuration

---

**Remember**: The test suite is designed to catch issues before they reach production. Run tests regularly during development and always before deploying changes.