# AI Model Validation Platform - Connectivity Test Suite

This directory contains comprehensive connectivity tests to validate that the AI Model Validation Platform is accessible and functional on both localhost and the external Vultr server IP address.

## Overview

The test suite validates:
- **Frontend accessibility**: http://127.0.0.1:3000 and http://155.138.239.131:3000
- **Backend API**: http://127.0.0.1:8000 and http://155.138.239.131:8000
- **WebSocket connections** from external IP
- **API communication** between frontend and backend
- **CORS headers** configuration
- **Database security** (ensuring external access is blocked)
- **Performance characteristics** of external connections

## Test Scripts

### 1. Comprehensive Connectivity Test (`comprehensive_connectivity_test.py`)
**Primary connectivity validation script**

Tests all basic connectivity requirements:
- HTTP connectivity to all endpoints
- WebSocket connection establishment
- Socket.IO integration
- CORS header validation
- Database security (ports should be blocked externally)
- Concurrent connection handling
- Performance metrics collection

**Usage:**
```bash
python comprehensive_connectivity_test.py
```

**Outputs:**
- `connectivity_test_results.json` - Detailed test results
- `connectivity_test_report.txt` - Human-readable report
- `connectivity_test.log` - Execution logs

### 2. Frontend-Backend Integration Test (`frontend_backend_integration_test.py`)
**End-to-end integration validation**

Tests the complete frontend-backend communication flow:
- Frontend application loading
- API communication from browser context
- WebSocket connections from frontend
- Data flow integration
- Cross-origin request handling
- Socket.IO real-time communication

**Features:**
- Uses Selenium WebDriver for browser automation
- Tests actual frontend-backend data flow
- Validates CORS configuration in real browser context
- Measures integration performance

**Usage:**
```bash
python frontend_backend_integration_test.py
```

**Outputs:**
- `frontend_backend_integration_results.json`
- `frontend_backend_integration_report.txt`
- `frontend_backend_integration.log`

### 3. Performance and Load Test (`performance_load_test.py`)
**Performance characteristics and load handling**

Comprehensive performance testing:
- Response time analysis
- Throughput testing under load
- Concurrent connection handling
- Network latency measurement
- Bandwidth utilization
- WebSocket performance under load
- Comparative analysis (localhost vs external)

**Features:**
- Concurrent user simulation (1-100 users)
- Network latency breakdown (DNS, TCP, HTTP)
- Throughput and bandwidth measurement
- Performance comparison between environments

**Usage:**
```bash
python performance_load_test.py
```

**Outputs:**
- `performance_test_results.json`
- `performance_test_report.txt`
- `performance_metrics.json`
- `performance_test.log`

### 4. Continuous Health Monitor (`continuous_health_monitor.py`)
**Ongoing health monitoring system**

Real-time monitoring capabilities:
- Continuous health checks
- Performance metrics tracking
- Alert notifications (email/webhook)
- Historical data logging
- ASCII dashboard display
- Automated recovery suggestions

**Features:**
- Configurable monitoring intervals
- Multiple alert channels
- Real-time dashboard
- Historical reporting
- Automatic cleanup of old logs

**Usage:**
```bash
# Start continuous monitoring
python continuous_health_monitor.py

# Generate historical report (24 hours)
python continuous_health_monitor.py --report 24

# Custom monitoring interval
python continuous_health_monitor.py --interval 30
```

**Configuration:**
Edit `health_monitor_config.json` to configure:
- Monitoring intervals
- Alert thresholds
- Email notifications
- Webhook integrations

### 5. Master Test Runner (`run_all_tests.py`)
**Orchestrates all test suites**

Centralized test execution:
- Runs all test suites in sequence
- Analyzes results across all tests
- Generates comprehensive reports
- Handles test dependencies and timeouts
- Provides executive summary

**Usage:**
```bash
# Run all tests
python run_all_tests.py

# Run only critical tests (quick mode)
python run_all_tests.py --quick

# Run specific test suites
python run_all_tests.py --suites comprehensive_connectivity performance_load

# Use custom configuration
python run_all_tests.py --config my_test_config.json
```

**Outputs:**
- `connectivity_test_results_TIMESTAMP.json`
- `connectivity_test_report_TIMESTAMP.html`
- `master_connectivity_test.log`

## Documentation

### `CONNECTIVITY_DOCUMENTATION.md`
Complete documentation of all accessible URLs, endpoints, and network configurations:

- **All accessible endpoints** with full URLs
- **Network requirements** and port configurations
- **Security considerations** and firewall rules
- **Authentication methods** and CORS settings
- **Troubleshooting guide** for common issues
- **Deployment considerations** and environment variables

## Installation and Dependencies

### Required Python Packages
```bash
pip install requests aiohttp websocket-client python-socketio psutil numpy matplotlib selenium
```

### Optional Dependencies
- **Chrome/ChromeDriver** (for frontend integration tests)
- **Email configuration** (for health monitoring alerts)
- **Webhook endpoints** (for alert notifications)

### System Requirements
- Python 3.8+
- Network access to test targets
- Chrome browser (for Selenium tests)
- Sufficient disk space for logs and reports

## Configuration

### Test Configuration (`test_config.json`)
```json
{
  "test_suites": {
    "comprehensive_connectivity": {
      "enabled": true,
      "timeout": 300,
      "critical": true
    },
    "performance_load": {
      "enabled": true,
      "timeout": 900,
      "critical": false
    }
  },
  "environments": {
    "localhost": {
      "frontend_url": "http://127.0.0.1:3000",
      "backend_url": "http://127.0.0.1:8000"
    },
    "external": {
      "frontend_url": "http://155.138.239.131:3000",
      "backend_url": "http://155.138.239.131:8000"
    }
  }
}
```

### Health Monitor Configuration (`health_monitor_config.json`)
```json
{
  "monitoring": {
    "interval": 60,
    "timeout": 30,
    "enable_alerts": true
  },
  "alerts": {
    "email": {
      "enabled": false,
      "smtp_server": "smtp.gmail.com",
      "recipients": ["admin@example.com"]
    }
  }
}
```

## Usage Examples

### Quick Connectivity Check
```bash
# Run basic connectivity tests only
python run_all_tests.py --quick
```

### Full Performance Analysis
```bash
# Run comprehensive performance testing
python performance_load_test.py
```

### Continuous Monitoring Setup
```bash
# Start 24/7 health monitoring
python continuous_health_monitor.py --interval 300  # Check every 5 minutes
```

### Integration Testing Only
```bash
# Test frontend-backend integration
python frontend_backend_integration_test.py
```

## Interpreting Results

### Success Criteria
- **Frontend accessible** on both localhost and external IP
- **Backend API responding** on both environments
- **WebSocket connections** established successfully
- **CORS headers** configured properly
- **Database ports** blocked from external access
- **Performance** within acceptable thresholds

### Common Issues and Solutions

1. **Connection Refused Errors**
   - Check if services are running: `docker ps`
   - Verify port bindings: `netstat -tlnp`
   - Check firewall rules: `ufw status`

2. **CORS Errors**
   - Verify CORS configuration in backend
   - Check Origin headers in requests
   - Ensure preflight requests are handled

3. **Poor External Performance**
   - Check network latency: `ping 155.138.239.131`
   - Monitor bandwidth utilization
   - Consider CDN or edge caching

4. **WebSocket Connection Issues**
   - Verify WebSocket URL format
   - Check proxy configuration
   - Validate authentication requirements

## Reporting

### JSON Results Format
```json
{
  "timestamp": "2025-08-24T...",
  "localhost": {
    "frontend": {"success": true, "response_time": 45.2},
    "backend": {"success": true, "response_time": 23.1}
  },
  "external": {
    "frontend": {"success": true, "response_time": 156.8},
    "backend": {"success": true, "response_time": 89.3}
  },
  "summary": {
    "overall_status": "healthy",
    "recommendations": ["All tests passed"]
  }
}
```

### HTML Reports
Interactive HTML reports include:
- Executive summary with metrics
- Detailed test results
- Performance charts
- Recommendations
- Error details and logs

## Security Considerations

### Database Security Testing
The tests verify that database ports (PostgreSQL 5432, Redis 6379) are **NOT** accessible from external IPs, which is correct for security.

### Authentication Testing
Tests validate that protected endpoints properly require authentication while public endpoints remain accessible.

### CORS Validation
Ensures that cross-origin requests are properly configured without being overly permissive.

## Continuous Integration

### GitHub Actions Integration
```yaml
- name: Run Connectivity Tests
  run: |
    cd backend/tests/connectivity
    python run_all_tests.py --quick
```

### Pre-deployment Validation
```bash
# Validate before deployment
python run_all_tests.py --suites comprehensive_connectivity frontend_backend_integration
```

## Monitoring and Alerting

### Production Monitoring
Use the continuous health monitor for ongoing production monitoring:

```bash
# Production monitoring configuration
python continuous_health_monitor.py \
  --config production_monitor_config.json \
  --interval 120  # 2-minute checks
```

### Alert Thresholds
- **Response Time Warning**: >2000ms
- **Response Time Critical**: >5000ms
- **Error Rate Warning**: >5%
- **Error Rate Critical**: >10%
- **Consecutive Failures**: ≥3

## Support and Troubleshooting

For issues with the connectivity tests:

1. **Check Prerequisites**: Ensure all dependencies are installed
2. **Review Logs**: Check generated `.log` files for details
3. **Verify Network**: Test basic network connectivity manually
4. **Check Configuration**: Validate URL configurations
5. **Run Individual Tests**: Use specific test scripts for debugging

## Contributing

When adding new connectivity tests:

1. Follow the existing test structure
2. Include both localhost and external IP testing
3. Add appropriate error handling and logging
4. Update documentation and README
5. Include performance metrics where relevant
6. Add to the master test runner configuration

---

**Last Updated**: 2025-08-24  
**Version**: 1.0.0