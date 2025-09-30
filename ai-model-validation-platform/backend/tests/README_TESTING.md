# LabJack Hybrid Logging System - Comprehensive Test Suite

## Overview

This comprehensive test suite validates the hybrid LabJack logging system that delivers **1000Hz continuous voltage detection with microsecond precision timing** instead of the previous throttled 18.8Hz events. The test suite ensures the system meets all performance, reliability, and accuracy requirements for Hardware-in-the-Loop (HIL) validation testing.

## Test Architecture

### Test Categories

The test suite is organized into the following categories using pytest markers:

#### `@pytest.mark.hardware`
Tests requiring real LabJack hardware devices. These tests:
- Validate actual hardware connectivity and communication
- Test 1000Hz sampling rate accuracy with real timing constraints
- Verify voltage detection precision and threshold sensitivity
- Validate hardware failure detection and recovery mechanisms

**Run with**: `pytest -m hardware --hardware`

#### `@pytest.mark.integration`
Integration tests using mock services to validate complete workflows:
- End-to-end pipeline from detection to database to frontend
- Video timing synchronization accuracy
- WebSocket streaming and real-time updates
- Database integration and data persistence

**Run with**: `pytest -m integration`

#### `@pytest.mark.performance`
Performance benchmarking tests that measure:
- 1000Hz sampling rate precision and consistency
- Smart compression effectiveness (5-20x ratios)
- Sub-millisecond timing accuracy
- Memory usage under high-frequency data streams
- CPU utilization during concurrent operations

**Run with**: `pytest -m performance --performance`

## Key Test Files

### Core Test Suites

1. **`test_labjack_hybrid_logging_system.py`** - Main comprehensive test suite
2. **`test_performance_benchmarks.py`** - Performance benchmarking suite
3. **`test_hardware_integration_suite.py`** - Hardware-specific validation
4. **`test_end_to_end_validation.py`** - Complete workflow validation

### Configuration Files

- **`conftest.py`** - Shared fixtures and test configuration
- **`pytest.ini`** - PyTest configuration and settings

## Running Tests

### Prerequisites

1. **Python Environment**: Python 3.8+
2. **Dependencies**: Install test dependencies
   ```bash
   pip install pytest pytest-asyncio pytest-mock psutil numpy
   ```
3. **LabJack Hardware** (optional): For hardware-specific tests

### Test Execution Commands

#### Run All Tests (Excluding Hardware)
```bash
pytest tests/ -v
```

#### Run Hardware Tests (Requires LabJack Device)
```bash
pytest tests/ -m hardware --hardware -v
```

#### Run Performance Benchmarks
```bash
pytest tests/ -m performance --performance -v -s
```

#### Run Integration Tests Only
```bash
pytest tests/ -m integration -v
```

#### CI/CD Compatible (No Hardware)
```bash
pytest tests/ -m "not hardware" -v --tb=short
```

## Test Requirements Validation

### Core Requirements

The test suite validates the following core user requirements:

✅ **1000Hz Continuous Sampling**: Tests verify the system captures voltage data at exactly 1000Hz with microsecond precision timestamps

✅ **Smart Compression (5-20x)**: Performance tests validate compression ratios between 5x-20x while preserving all detection events

✅ **Sub-millisecond Timing**: Precision tests confirm timing accuracy within 1ms for all detection events

✅ **Real-time Frontend Display**: Integration tests validate WebSocket streaming and frontend visualization of continuous data

✅ **Export Functionality**: Data integrity tests confirm large dataset export capability with preserved accuracy

✅ **Hardware Failure Recovery**: Fallback tests validate graceful handling of hardware disconnection and reconnection

### Performance Benchmarks

| Metric | Target | Test Validation |
|--------|--------|-----------------|
| Sampling Rate | 1000Hz ± 5% | Hardware tests measure actual vs requested rates |
| Timing Precision | < 1ms error | Performance tests validate microsecond accuracy |
| Compression Ratio | 5x - 20x | Benchmarks test various detection frequencies |
| Processing Latency | < 100ms | Integration tests measure end-to-end latency |
| Memory Usage | < 500MB | Performance tests monitor resource consumption |
| WebSocket Latency | < 500ms | Frontend tests measure real-time streaming |

This comprehensive test suite ensures the LabJack hybrid logging system delivers reliable, accurate, high-performance voltage detection capabilities that meet all user requirements for continuous 1000Hz monitoring with microsecond precision.