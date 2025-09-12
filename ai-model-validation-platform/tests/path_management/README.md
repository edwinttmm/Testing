# Path Management Test Suite

Comprehensive test suite for path management fixes in the AI Model Validation Platform. Tests path resolution robustness across different deployment scenarios, working directory contexts, and error conditions.

## 🧪 Test Categories

### Unit Tests
- **`test_path_resolver.py`** - Core PathResolver functionality
- **`test_environment_detector.py`** - Environment detection accuracy
- **`test_path_validation_normalization.py`** - Path validation and normalization

### Integration Tests
- **`test_ground_truth_path_processing.py`** - Ground truth service with path scenarios
- **`test_working_directory_contexts.py`** - Different working directory contexts
- **`test_error_handling_missing_files.py`** - Error handling for missing files
- **`test_path_migration.py`** - Relative to absolute path migration
- **`test_container_deployment_simulation.py`** - Container deployment scenarios
- **`test_cross_platform_compatibility.py`** - Cross-platform path compatibility

## 🚀 Quick Start

### Run All Tests
```bash
cd tests/path_management
python test_runner.py
```

### Run Specific Categories
```bash
# Unit tests only
python test_runner.py --unit

# Integration tests only
python test_runner.py --integration
```

### Run by Pattern or Markers
```bash
# Tests matching pattern
python test_runner.py --pattern "path_resolution"

# Tests with specific markers
python test_runner.py --markers unit path_resolution
```

### Validate Test Environment
```bash
python test_runner.py --validate
```

## 📋 Test Coverage Areas

### 1. Path Resolution Utilities (`test_path_resolver.py`)
- ✅ Default path resolution across environments
- ✅ Custom path overrides
- ✅ Environment variable resolution
- ✅ Directory creation and permissions
- ✅ Caching mechanisms
- ✅ Fallback strategies
- ✅ Path validation and access testing

### 2. Environment Detection (`test_environment_detector.py`)
- ✅ Docker container detection
- ✅ Kubernetes pod detection
- ✅ WSL environment detection
- ✅ Local development detection
- ✅ Cloud provider detection
- ✅ Service mode detection
- ✅ Confidence scoring

### 3. Ground Truth Processing Integration (`test_ground_truth_path_processing.py`)
- ✅ Local development absolute paths
- ✅ Docker container relative paths
- ✅ Environment variable path resolution
- ✅ Cross-environment compatibility
- ✅ Missing file error handling
- ✅ Screenshot path resolution
- ✅ Path normalization
- ✅ Concurrent processing safety

### 4. Working Directory Contexts (`test_working_directory_contexts.py`)
- ✅ Project root directory context
- ✅ Backend subdirectory context
- ✅ Deep nested path context
- ✅ Working directory change impact
- ✅ Custom path independence
- ✅ Environment variable interaction
- ✅ Directory creation from different contexts

### 5. Error Handling (`test_error_handling_missing_files.py`)
- ✅ Missing video file handling
- ✅ Inaccessible file handling
- ✅ Directory creation failures
- ✅ Non-existent parent directories
- ✅ Circular path references
- ✅ Invalid path characters
- ✅ Write access failures
- ✅ Error recovery mechanisms

### 6. Path Migration (`test_path_migration.py`)
- ✅ Relative to absolute conversion
- ✅ Different working directory migration
- ✅ Docker migration scenarios
- ✅ Legacy configuration migration
- ✅ Database migration simulation
- ✅ Backward compatibility
- ✅ Cross-platform migration
- ✅ Migration validation

### 7. Container Deployment (`test_container_deployment_simulation.py`)
- ✅ Docker container path resolution
- ✅ Kubernetes pod scenarios
- ✅ Cloud container services (AWS ECS, GCP Cloud Run)
- ✅ Volume mount handling
- ✅ Multi-stage build paths
- ✅ Docker Compose integration
- ✅ Security and permissions
- ✅ Network storage integration

### 8. Path Validation (`test_path_validation_normalization.py`)
- ✅ Valid path validation
- ✅ Invalid path handling
- ✅ Path length limits
- ✅ Special character handling
- ✅ Unicode filename support
- ✅ Case sensitivity handling
- ✅ Path separator normalization
- ✅ Security sanitization

### 9. Cross-Platform Compatibility (`test_cross_platform_compatibility.py`)
- ✅ Linux path handling
- ✅ Windows path handling (drive letters, separators)
- ✅ macOS path handling
- ✅ Case sensitivity differences
- ✅ Home directory expansion
- ✅ Unicode filename support
- ✅ Long path support
- ✅ Platform-specific edge cases

## 🏗️ Test Architecture

### Fixtures (conftest.py)
- **Environment Info**: Pre-configured environment scenarios
- **Temp Workspaces**: Isolated test environments
- **Mock Data**: Video files and test data
- **Clean Environment**: Isolated environment variables

### Test Markers
- `unit` - Unit tests
- `integration` - Integration tests
- `path_resolution` - Path resolution focused
- `cross_platform` - Cross-platform compatibility
- `error_handling` - Error handling scenarios
- `container` - Container deployment
- `migration` - Migration scenarios

### Test Organization
```
tests/path_management/
├── conftest.py                              # Shared fixtures
├── test_runner.py                           # Test runner script
├── unit/
│   └── path_resolution/
│       ├── test_path_resolver.py
│       └── test_environment_detector.py
├── integration/
│   └── path_scenarios/
│       └── test_ground_truth_path_processing.py
├── test_working_directory_contexts.py
├── test_error_handling_missing_files.py
├── test_path_migration.py
├── test_container_deployment_simulation.py
├── test_path_validation_normalization.py
└── test_cross_platform_compatibility.py
```

## 📊 Test Execution Options

### Standard Pytest
```bash
# Run all tests with pytest directly
pytest -v

# Run specific test file
pytest test_path_resolver.py -v

# Run tests by marker
pytest -m "unit and path_resolution" -v

# Run with coverage
pytest --cov=config --cov-report=html
```

### Custom Test Runner
```bash
# All tests with summary report
python test_runner.py

# Quiet mode
python test_runner.py --quiet

# No output capture (see print statements)
python test_runner.py --no-capture

# Validate environment setup
python test_runner.py --validate
```

## 🔧 Environment Setup

### Prerequisites
- Python 3.8+
- pytest
- Backend modules accessible
- Write permissions in test directories

### Install Dependencies
```bash
pip install pytest pytest-cov pytest-mock
```

### Environment Variables (Optional)
```bash
export AIVALIDATION_UPLOAD_DIRECTORY="/custom/uploads"
export AIVALIDATION_LOG_DIRECTORY="/custom/logs"
# ... other path overrides
```

## 📈 Test Results

### Success Criteria
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ No regressions in path resolution
- ✅ Cross-platform compatibility maintained
- ✅ Error handling robust
- ✅ Container deployment ready

### Performance Benchmarks
- Path resolution: < 10ms per operation
- Environment detection: < 100ms
- Validation suite: < 5 minutes total

### Coverage Goals
- Unit tests: > 95% code coverage
- Integration tests: > 80% scenario coverage
- Error paths: > 90% error condition coverage

## 🐛 Debugging Failed Tests

### Common Issues
1. **Import Errors**: Check Python path setup
2. **Permission Errors**: Ensure write access to temp directories
3. **Platform Differences**: Some tests may be platform-specific
4. **Environment Variables**: Clean environment between tests

### Debugging Commands
```bash
# Run single test with detailed output
pytest test_path_resolver.py::TestPathResolver::test_specific_method -v -s

# Run with debugger
pytest --pdb test_path_resolver.py -k "test_specific_method"

# Show all print statements
pytest -s test_file.py
```

### Log Analysis
Test results are saved in `results/` directory with detailed logs and timing information.

## 🔄 Continuous Integration

### GitHub Actions Integration
```yaml
- name: Run Path Management Tests
  run: |
    cd tests/path_management
    python test_runner.py --validate
    python test_runner.py
```

### Pre-commit Hooks
```bash
# Run tests before commit
python tests/path_management/test_runner.py --unit
```

## 🧩 Extending Tests

### Adding New Test Cases
1. Choose appropriate test file or create new one
2. Use existing fixtures from `conftest.py`
3. Add relevant markers
4. Update test runner categories if needed

### Creating Platform-Specific Tests
```python
@pytest.mark.skipif(os.name == 'nt', reason="Unix-only test")
def test_unix_specific_feature():
    pass

@pytest.mark.skipif(os.name != 'nt', reason="Windows-only test")  
def test_windows_specific_feature():
    pass
```

## 📚 References

- [pytest Documentation](https://docs.pytest.org/)
- [Python pathlib](https://docs.python.org/3/library/pathlib.html)
- [OS Path Module](https://docs.python.org/3/library/os.path.html)
- [Platform Module](https://docs.python.org/3/library/platform.html)

---

This comprehensive test suite ensures the path management fixes are robust, reliable, and ready for production deployment across all supported environments and platforms.