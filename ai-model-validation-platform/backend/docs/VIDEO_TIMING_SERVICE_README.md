# Video Timing Service Documentation

## Overview

The Video Timing Service provides high-precision video start timing for accurate latency measurement between video playback and LabJack detection events. This service is essential for AI model validation testing where precise timing synchronization is critical.

## Key Features

- **Microsecond-precision timestamp recording** using `time.time()` and `time.time_ns()`
- **Session-based video timing storage** with in-memory cache and database persistence  
- **LabJack synchronization integration** for coordinated monitoring
- **Multiple video support per session** with video tracking
- **Thread-safe operations** using `threading.RLock`
- **Comprehensive error handling** and logging
- **REST API endpoints** for easy integration
- **Performance monitoring** and statistics

## Architecture

### Core Components

1. **VideoTimingService** - Main service class for timing operations
2. **VideoTimingData** - Data container for timing information
3. **LatencyMeasurement** - Container for latency calculation results
4. **API Routes** - REST endpoints in `/routes/video_timing.py`
5. **Database Integration** - TestSession model with `video_start_timestamp` field

### Latency Calculation Formula

```
Latency (ms) = (LabJack Detection Timestamp - Video Start Timestamp) × 1000
```

## Usage

### Basic Service Usage

```python
from services.video_timing_service import get_video_timing_service

# Get service instance
timing_service = get_video_timing_service()

# Start video timing
start_timestamp = timing_service.start_video_timing(session_id, video_id, db)

# Calculate latency when detection occurs
measurement = timing_service.calculate_latency(session_id, detection_timestamp, db)

# Get latency in milliseconds
latency_ms = measurement.latency_ms
```

### API Endpoints

#### Start Video Timing
```http
POST /api/sessions/{session_id}/start-video
Content-Type: application/json

{
  "video_id": "video-uuid",
  "sync_labjack": true
}
```

#### Get Video Timing Data
```http
GET /api/sessions/{session_id}/video-timing
```

#### Calculate Latency
```http
POST /api/sessions/{session_id}/calculate-latency
Content-Type: application/json

{
  "detection_timestamp": 1757411426.594723
}
```

#### Synchronize with LabJack
```http
POST /api/sessions/{session_id}/sync-labjack
Content-Type: application/json

{
  "start_monitoring": true
}
```

#### Clear Timing Data
```http
DELETE /api/sessions/{session_id}/clear-timing
```

#### Get Timing Statistics
```http
GET /api/sessions/{session_id}/timing-stats
```

## Database Schema

### TestSession Model Changes

```sql
ALTER TABLE test_sessions ADD COLUMN video_start_timestamp REAL;
ALTER TABLE test_sessions ADD COLUMN video_timing_metadata TEXT;

-- Indexes for performance
CREATE INDEX idx_testsession_video_timing ON test_sessions(video_start_timestamp);
CREATE INDEX idx_testsession_timing_status ON test_sessions(video_start_timestamp, status);
```

## Integration Points

### LabJack Service Integration

The service integrates with the LabJack detection system through:

1. **Synchronization Method**: `synchronize_with_labjack(session_id, labjack_service)`
2. **Timing Reference**: Provides video start timestamp to LabJack service
3. **Coordinated Monitoring**: Starts LabJack monitoring with video timing reference

```python
# Example integration
timing_service = get_video_timing_service()
labjack_service = get_labjack_service()

# Start video timing
video_start_time = timing_service.start_video_timing(session_id, video_id, db)

# Synchronize with LabJack
sync_success = timing_service.synchronize_with_labjack(session_id, labjack_service)

# When LabJack detects event
detection_timestamp = labjack_service.get_detection_timestamp()
measurement = timing_service.calculate_latency(session_id, detection_timestamp, db)
```

### Database Storage

- **Primary Storage**: In-memory cache for active sessions
- **Persistence**: Database storage in `TestSession.video_start_timestamp`
- **Metadata**: Additional timing info in `TestSession.video_timing_metadata` (JSON)
- **Performance**: Indexed fields for fast queries

## Performance Characteristics

### Timer Precision

The service automatically detects system timer precision:

- **Excellent**: < 1μs (1,000 ns) - High-precision systems
- **High**: < 10μs (10,000 ns) - Standard modern systems  
- **Standard**: < 100μs (100,000 ns) - Older systems
- **Low**: > 100μs - Not recommended for latency measurement

### Throughput

- **Concurrent Sessions**: Supports multiple simultaneous sessions
- **Thread Safety**: Full thread-safe operation with `RLock`
- **Memory Efficiency**: Lightweight in-memory cache
- **Database Performance**: Indexed queries for fast retrieval

## Error Handling

### Exception Types

- **VideoTimingError**: Custom exception for timing operations
- **HTTPException**: API endpoint error responses
- **SQLAlchemyError**: Database operation errors

### Error Scenarios

1. **Session Not Found**: Returns 404 for invalid session IDs
2. **No Timing Data**: Returns None for missing timing information
3. **LabJack Unavailable**: Returns False for synchronization failures
4. **Database Errors**: Logs errors and falls back to cache

### Logging

All operations are logged with appropriate levels:

- **INFO**: Successful operations and timing measurements
- **WARNING**: Non-critical issues (e.g., LabJack sync failures)
- **ERROR**: Critical errors that affect functionality
- **DEBUG**: Detailed timing and performance information

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
python -m pytest tests/test_video_timing_service.py -v
```

### Test Coverage

- ✅ Service initialization and singleton pattern
- ✅ Timer precision detection and validation
- ✅ Video timing start/stop operations
- ✅ Latency calculation accuracy
- ✅ LabJack synchronization
- ✅ Database integration
- ✅ API endpoint functionality
- ✅ Error handling and edge cases
- ✅ Thread safety and concurrent access
- ✅ Performance characteristics

### Example Test Results

```
Timer precision: 100ns (excellent class)
Video timing started: 1757411426.494162
Timing data retrieved: 1757411426.494162
Calculated latency: 50.000ms
Service Statistics:
- Active sessions: 1
- Total videos: 1
- Precision class: excellent
```

## Migration Guide

### Database Migration

Run the migration script to add required fields:

```bash
python migrations/add_video_timing_fields.py
```

This adds:
- `video_start_timestamp` field to test_sessions table
- `video_timing_metadata` field for additional timing info
- Performance indexes for timing queries

### API Integration

Update your application to use the new timing endpoints:

```python
# Before video playback
response = requests.post(f"/api/sessions/{session_id}/start-video", json={
    "video_id": video_id,
    "sync_labjack": True
})

# After LabJack detection
response = requests.post(f"/api/sessions/{session_id}/calculate-latency", json={
    "detection_timestamp": detection_timestamp
})

latency_ms = response.json()["data"]["latency_ms"]
```

## Monitoring and Debugging

### Health Check

```http
GET /api/sessions/timing-service/health
```

Returns service health status and timer precision information.

### Statistics Endpoint

```http
GET /api/sessions/{session_id}/timing-stats
```

Provides:
- Active session count
- Total video count  
- Timer precision metrics
- Cache size information
- Session-specific data

### Performance Monitoring

Monitor these metrics for optimal performance:

- **Timer Precision**: Should be < 10μs for accurate measurements
- **Active Sessions**: Monitor for memory usage
- **Cache Size**: Clear old sessions to prevent memory leaks
- **API Response Times**: Should be < 100ms for timing operations

## Best Practices

### Timing Accuracy

1. **Start Timing Immediately**: Call `start_video_timing()` right before video playback
2. **Minimize Delay**: Reduce time between timing start and actual video start
3. **Use High-Precision Timestamps**: The service automatically uses the best available precision
4. **Synchronize Clocks**: Ensure system clocks are synchronized for distributed systems

### Performance Optimization

1. **Clear Unused Sessions**: Use the clear endpoint to free memory
2. **Database Persistence**: Store timing data for long-term analysis
3. **Batch Operations**: Group multiple timing operations when possible
4. **Monitor Cache Size**: Track active sessions and memory usage

### Error Resilience

1. **Graceful Degradation**: Service continues with cache if database fails
2. **Retry Logic**: Implement retries for transient failures
3. **Fallback Options**: Use database storage if cache is cleared
4. **Comprehensive Logging**: Monitor logs for timing accuracy issues

## File Structure

```
backend/
├── services/
│   └── video_timing_service.py     # Main service implementation
├── routes/
│   └── video_timing.py             # API endpoints
├── migrations/
│   └── add_video_timing_fields.py  # Database migration
├── tests/
│   └── test_video_timing_service.py # Integration tests
└── docs/
    ├── video_timing_service_usage.py   # Usage examples
    └── VIDEO_TIMING_SERVICE_README.md  # This documentation
```

## Related Services

- **LabJackDetectionService**: Provides detection events for latency calculation
- **TestExecutionService**: Uses video timing for test workflow coordination  
- **SessionManagementService**: Manages test session lifecycle
- **WebSocketService**: Provides real-time timing updates

## Support

For issues or questions about the Video Timing Service:

1. Check the logs for error messages
2. Verify timer precision is adequate (< 10μs)
3. Ensure database migration has been run
4. Test with the provided usage examples
5. Review the integration test results

The service is designed to be robust and self-monitoring, with comprehensive error handling and performance optimization for production use in AI model validation testing.