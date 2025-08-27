# VRU Platform Comprehensive Testing Suite

This directory contains a comprehensive testing suite for the VRU (Vehicle-Road-User) validation platform, designed to ensure robust performance across all system components.

## 🚀 Quick Start

### Run Complete Test Suite
```bash
cd /home/user/Testing/ai-model-validation-platform/backend/tests
python run_vru_comprehensive_tests.py
```

### Run Specific Test Categories
```bash
# Integration tests only
python run_vru_comprehensive_tests.py --integration

# Performance benchmarks only  
python run_vru_comprehensive_tests.py --performance

# Production server validation
python run_vru_comprehensive_tests.py --production --server 155.138.239.131
```

## 📁 Test Suite Structure

```
tests/
├── test_vru_complete_integration.py     # Main integration test suite
├── performance/
│   └── test_vru_performance_benchmarks.py  # Performance & load testing
├── fixtures/
│   └── test_data_generator.py          # Test data generation utilities
├── run_vru_comprehensive_tests.py      # Test orchestrator & runner
└── artifacts_<timestamp>/              # Generated test artifacts
```

## 🧪 Test Components

### 1. Integration Tests (`test_vru_complete_integration.py`)
- **ML Inference Engine**: Tests YOLO-based VRU detection pipeline
- **Camera Systems**: WebSocket communication and real-time streaming
- **Validation Engine**: Ground truth validation workflows
- **Project Management**: CRUD operations and video library management
- **End-to-End Workflows**: Complete VRU validation scenarios
- **Production Integration**: Tests against production server (155.138.239.131)

**Key Test Classes:**
- `TestMLInferenceEngine`: ML model performance and accuracy
- `TestCameraSystemAndWebSocket`: Real-time communication testing
- `TestValidationEngine`: Validation metrics and workflows
- `TestProjectManagement`: Project and video management
- `TestEndToEndWorkflows`: Complete system integration
- `TestProductionIntegration`: Production server validation

### 2. Performance Benchmarks (`performance/test_vru_performance_benchmarks.py`)
- **ML Performance**: Inference speed across different video resolutions
- **Memory Management**: Memory usage monitoring and stress testing
- **CPU Load Testing**: Multi-core performance under sustained load
- **Database Performance**: Query optimization and connection pooling
- **WebSocket Scalability**: Concurrent connection handling
- **Resource Limits**: System behavior at capacity limits

**Benchmark Categories:**
- Single/Multi-stream video processing
- Concurrent user simulation (5-50 users)
- Memory stress testing (up to 1GB allocation)
- CPU intensive workload testing
- Database operation throughput

### 3. Test Data Generation (`fixtures/test_data_generator.py`)
- **Synthetic Video Creation**: Generates realistic VRU scenarios
- **Ground Truth Annotations**: Precise object detection labels
- **Environmental Conditions**: Weather/lighting variations
- **Edge Cases**: Occlusion, scale, and motion blur scenarios
- **Performance Datasets**: High-density object scenarios

**Generated Test Scenarios:**
- Single object tracking (pedestrian, cyclist, vehicle, motorcycle)
- Multi-object interactions
- Environmental challenges (rain, snow, night, overcast)
- Performance stress scenarios (20+ concurrent objects)

## 🔧 Configuration

### Test Configuration Options
```python
@dataclass
class VRUTestConfig:
    test_timeout: int = 300              # 5 minutes per test
    performance_threshold_ms: int = 1000  # Max processing time
    memory_limit_mb: int = 512           # Memory usage limit
    concurrent_connections: int = 10      # WebSocket load testing
    production_server: str = "155.138.239.131"
    production_port: int = 8000
```

### Environment Variables
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/vru_test"
export ML_MODEL_PATH="/path/to/yolo/models"
export TEST_ARTIFACTS_DIR="/path/to/test/artifacts"
```

## 📊 Test Reports and Artifacts

### Generated Artifacts
- `vru_comprehensive_test_report.json`: Detailed JSON report
- `VRU_Test_Report.txt`: Human-readable summary
- `integration_test_results.json`: Pytest JSON report
- `performance_test_output.txt`: Performance benchmark results
- `system_health.json`: System resource snapshots
- `test_data/`: Generated test videos and annotations

### Report Contents
- **Execution Summary**: Success rates, timing, overall status
- **Performance Metrics**: Throughput, latency, resource usage
- **System Information**: Hardware specs, software versions
- **Detailed Results**: Per-test status and error messages
- **Recommendations**: Optimization suggestions based on results

## 🎯 Test Scenarios

### ML Inference Testing
```python
# Test different video processing scenarios
scenarios = [
    {"name": "hd_single_stream", "resolution": (1920, 1080), "fps": 30},
    {"name": "4k_processing", "resolution": (3840, 2160), "fps": 30},
    {"name": "multi_stream", "streams": 4, "resolution": (1280, 720)}
]
```

### Performance Benchmarking
```python
# Concurrent user simulation
user_loads = [5, 15, 30, 50]  # Simulated concurrent users
test_duration = 60  # seconds per load test
```

### Production Validation
```python
# Production server endpoints testing
endpoints = [
    "/health",      # System health check
    "/projects",    # Project management API
    "/",           # Root endpoint
]
```

## 🔍 Monitoring and Metrics

### Real-time Monitoring
- **System Resources**: CPU, Memory, Disk I/O
- **Network Performance**: Latency, throughput, connection counts
- **Application Metrics**: Request/response times, error rates
- **ML Performance**: Inference speed, detection accuracy

### Performance Thresholds
- ML Inference: < 1000ms per video frame
- API Response: < 500ms for most endpoints
- Memory Usage: < 512MB baseline
- CPU Usage: < 85% sustained load
- WebSocket: Support 50+ concurrent connections

## 🚨 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure all dependencies installed
   pip install -r requirements.txt
   ```

2. **Database Connectivity**
   ```bash
   # Check database health
   python -c "from database import get_database_health; print(get_database_health())"
   ```

3. **Production Server Access**
   ```bash
   # Test network connectivity
   curl -f http://155.138.239.131:8000/health
   ```

4. **Memory Issues**
   ```bash
   # Monitor system resources during tests
   htop  # or top on systems without htop
   ```

### Debug Mode
```bash
# Run tests with verbose output
python run_vru_comprehensive_tests.py --timeout 3600 --no-cleanup
```

## 📈 Performance Optimization

### Recommendations Based on Test Results

1. **ML Inference Optimization**
   - Use GPU acceleration when available
   - Implement batch processing for multiple streams
   - Consider model quantization for edge deployment

2. **Database Performance**
   - Optimize query patterns based on load test results
   - Implement connection pooling
   - Consider read replicas for scaled deployments

3. **WebSocket Scalability**
   - Implement connection load balancing
   - Use Redis for session state management
   - Monitor connection lifecycle performance

4. **Memory Management**
   - Implement streaming for large video files
   - Use memory pooling for frequent allocations
   - Monitor for memory leaks in long-running processes

## 🔗 Integration Points

### External Systems
- **Production Server**: 155.138.239.131:8000
- **Database**: PostgreSQL/SQLite (configurable)
- **ML Models**: YOLO-based detection pipeline
- **File Storage**: Local/cloud storage for video files

### API Contracts
- RESTful APIs for project management
- WebSocket for real-time communication
- File upload endpoints for video processing
- Validation result APIs

## 📝 Contributing

### Adding New Tests
1. Create test file in appropriate directory
2. Follow naming convention: `test_<component>_<functionality>.py`
3. Include comprehensive docstrings and type hints
4. Add test to orchestrator pipeline if needed

### Test Data Guidelines
- Use realistic VRU scenarios
- Include edge cases and error conditions
- Generate proper ground truth annotations
- Consider performance implications of test data size

---

**Last Updated**: 2025-08-27  
**Version**: 1.0.0  
**Production Server**: 155.138.239.131:8000