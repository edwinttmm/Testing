# HIL Test Session Monitoring Integration Guide

## Overview

This guide explains the fixed HIL (Hardware-in-the-Loop) test session workflow that properly integrates with the dedicated LabJack monitoring service. The solution addresses the issue where HIL test sessions were completing with 0 detections due to monitoring service conflicts.

## Architecture

### Components

1. **Dedicated Monitoring Service** (`dedicated_monitoring_service.py`)
   - Runs as separate process to prevent device conflicts
   - Handles LabJack hardware access exclusively
   - Stores detection events directly to database
   - Communicates via Unix domain sockets (IPC)

2. **IPC Communication Layer** (`monitoring_service_client.py`)
   - Client for main application to communicate with monitoring service
   - Handles connection retries and error recovery
   - Provides high-level monitoring operations

3. **Process Manager** (`monitoring_process_manager.py`)
   - Manages monitoring service lifecycle
   - Provides health monitoring and auto-restart
   - Handles graceful shutdown and recovery

4. **Fixed Test Sessions Router** (`test_sessions_fixed.py`)
   - Updated session endpoints with proper monitoring integration
   - IPC-based monitoring control
   - Comprehensive error handling and fallback behavior

5. **Management Endpoints** (`monitoring_service_endpoints.py`)
   - API endpoints for monitoring service management
   - Health checks and status monitoring
   - Service lifecycle control

## Key Fixes

### 1. Session Start Process

**Before (Problematic):**
```python
# Direct hardware access causing conflicts
labjack_monitoring_service.start_monitoring(session_id)
```

**After (Fixed):**
```python
# IPC communication with dedicated service
monitoring_result = await monitoring_service_manager.start_session_monitoring(
    session_id=session_id,
    sample_rate=10,
    wait_for_service=True
)
```

### 2. Monitoring Service Isolation

- **Dedicated Process**: Monitoring runs in separate process
- **Device Exclusivity**: Only monitoring service accesses LabJack hardware
- **IPC Communication**: Main application communicates via Unix sockets
- **Conflict Prevention**: No simultaneous hardware access

### 3. Robust Error Handling

- **Service Availability Checks**: Verify service before starting sessions
- **Fallback Mechanisms**: Legacy monitoring if dedicated service fails
- **Graceful Degradation**: Sessions proceed without monitoring if necessary
- **Comprehensive Logging**: Detailed error reporting and status tracking

### 4. Proper Session Completion

- **Detection Event Aggregation**: Counts detections from database
- **TestResult Creation**: Comprehensive result generation with metrics
- **Service Cleanup**: Proper monitoring service shutdown
- **Status Tracking**: Monitoring service usage tracking

## Usage

### 1. Start Monitoring Service

#### Automatic Startup (Recommended)
```bash
# Start as managed subprocess with auto-restart
python scripts/start_monitoring_service.py --mode subprocess --auto-restart --daemon
```

#### Manual Startup
```bash
# Start directly
python services/dedicated_monitoring_service.py
```

### 2. API Integration

#### Check Service Health
```bash
curl -X GET "http://localhost:8000/api/monitoring/service/health"
```

#### Start Test Session with Monitoring
```bash
curl -X POST "http://localhost:8000/api/test-sessions/{session_id}/start"
```

#### Get Session Status with Monitoring Info
```bash
curl -X GET "http://localhost:8000/api/test-sessions/{session_id}/status"
```

### 3. Service Management

#### Ensure Service Availability
```bash
curl -X POST "http://localhost:8000/api/monitoring/service/ensure-available"
```

#### Restart Service
```bash
curl -X POST "http://localhost:8000/api/monitoring/service/restart"
```

## Configuration

### Environment Variables

```bash
# Monitoring service configuration
MONITORING_SOCKET_PATH="/tmp/monitoring_service.sock"
MONITORING_DB_PATH="dev_database.db"
MONITORING_SAMPLE_RATE=10
MONITORING_VOLTAGE_THRESHOLD=3.0

# Process management
MONITORING_MAX_RESTART_ATTEMPTS=3
MONITORING_HEALTH_CHECK_INTERVAL=10
MONITORING_RESTART_DELAY=5
```

### Service Settings

```python
# monitoring_process_manager.py
class MonitoringProcessManager:
    def __init__(self):
        self._health_check_interval = 10.0  # seconds
        self._max_restart_attempts = 3
        self._restart_delay = 5.0  # seconds
```

## Troubleshooting

### Common Issues

#### 1. Service Not Starting
```bash
# Check if port/socket is available
lsof -U | grep monitoring_service

# Check service logs
tail -f monitoring_service.log

# Start in debug mode
python services/dedicated_monitoring_service.py --debug
```

#### 2. IPC Communication Failures
```bash
# Test IPC connection
python scripts/start_monitoring_service.py --mode health

# Check socket permissions
ls -la /tmp/monitoring_service.sock
```

#### 3. LabJack Hardware Issues
```bash
# Check hardware connection
python -c "from services.signal_validation_wsl import signal_validation_service; print(signal_validation_service.get_labjack_status())"

# Test voltage reading
curl -X GET "http://localhost:8000/api/signal-validation/labjack/read-voltage/AIN0"
```

#### 4. Zero Detections Issue
```bash
# Check monitoring status during session
curl -X GET "http://localhost:8000/api/test-sessions/{session_id}/monitoring/status"

# Verify detection events in database
sqlite3 dev_database.db "SELECT COUNT(*) FROM detection_events WHERE test_session_id = '{session_id}';"
```

### Debug Steps

1. **Check Service Status**
   ```bash
   curl -X GET "http://localhost:8000/api/monitoring/service/status"
   ```

2. **Verify Hardware Access**
   ```bash
   python scripts/start_monitoring_service.py --mode health
   ```

3. **Test Session Flow**
   ```bash
   # Create session
   curl -X POST "http://localhost:8000/api/test-sessions" -d '{"name":"Test","project_id":"..."}'
   
   # Start with monitoring
   curl -X POST "http://localhost:8000/api/test-sessions/{session_id}/start"
   
   # Check detection count
   curl -X GET "http://localhost:8000/api/test-sessions/{session_id}/status"
   
   # Complete session
   curl -X POST "http://localhost:8000/api/test-sessions/{session_id}/complete"
   ```

## Integration Checklist

- [ ] Monitoring service starts successfully
- [ ] IPC communication works
- [ ] LabJack hardware accessible
- [ ] Test sessions start with monitoring
- [ ] Detection events stored correctly
- [ ] Session completion creates TestResults
- [ ] Error handling works properly
- [ ] Service recovery functions
- [ ] Health checks pass
- [ ] Zero detections issue resolved

## Performance Metrics

### Expected Improvements

- **Detection Rate**: 10Hz sampling (configurable)
- **Latency**: ~5ms typical LabJack response time
- **Reliability**: Auto-restart on failure
- **Conflict Resolution**: Eliminated device access conflicts
- **Error Recovery**: Graceful fallback mechanisms

### Monitoring

```python
# Service health metrics
{
    "process_running": True,
    "service_responsive": True,
    "ipc_communication": True,
    "detection_rate": 10.0,
    "memory_usage": "45MB",
    "cpu_usage": "2.1%"
}
```

## Migration Notes

### From Legacy System

1. **Replace Direct Hardware Access**
   - Remove direct LabJack calls from test session endpoints
   - Use IPC communication instead

2. **Update Error Handling**
   - Add service availability checks
   - Implement fallback mechanisms

3. **Modify Session Lifecycle**
   - Integrate monitoring service startup/shutdown
   - Update completion logic for TestResult creation

### Database Changes

No schema changes required. The solution reuses existing:
- `detection_events` table for storing detections
- `test_sessions` table for session tracking  
- `test_results` table for result storage

## Security Considerations

- **IPC Security**: Unix domain sockets restrict access to local machine
- **Process Isolation**: Monitoring service runs in separate process context
- **Resource Limits**: Process manager enforces restart limits
- **Error Boundaries**: Service failures don't crash main application

## Future Enhancements

1. **Distributed Monitoring**: Support for remote LabJack devices
2. **Protocol Extensions**: Support for additional hardware interfaces
3. **Performance Optimization**: Batched database writes
4. **Advanced Analytics**: Real-time detection analysis
5. **Configuration UI**: Web interface for monitoring service management

## Support

For issues or questions:

1. Check service logs: `monitoring_service.log`
2. Run health checks: `curl -X GET "/api/monitoring/service/health"`
3. Review this guide for troubleshooting steps
4. Check LabJack hardware documentation for device-specific issues