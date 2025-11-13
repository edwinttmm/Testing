# Validation Error Handling Implementation

## Executive Summary

Implemented comprehensive validation failure handling to prevent sessions from remaining in limbo state when validation fails. Sessions now have explicit failure states with retry capability and automatic cleanup.

## Implementation Components

### 1. SessionStatus Enum (models.py)
Added explicit state machine for session lifecycle:
- CREATED -> RUNNING -> COMPLETED (success)
- CREATED -> RUNNING -> VALIDATION_FAILED (validation fails)
- CREATED -> RUNNING -> ERROR (unexpected errors)
- Any state -> CANCELLED (manual cancellation)

### 2. Failure Tracking Fields (models.py)
Added to TestSession model:
- `failure_reason`: Human-readable failure description
- `failure_details`: JSON structured error data for debugging
- `failed_at`: Timestamp when failure occurred
- `retry_count`: Number of retry attempts
- `last_retry_at`: Last retry timestamp

### 3. Enhanced Session Completion Service
**ValidationFailedException**: New controlled exception for validation failures (vs unexpected errors)

**Validation Failure Handling**:
```python
if not is_valid:
    session.status = "validation_failed"
    session.failure_reason = error_message
    session.failed_at = datetime.now(timezone.utc)
    session.failure_details = {
        'validation_type': 'video_sequence_completion',
        'error_message': error_message,
        'recoverable': True
    }
    db.commit()
    
    # Emit WebSocket event to frontend
    sio.emit('session_failed', {
        'session_id': session_id,
        'status': 'validation_failed',
        'reason': error_message,
        'recoverable': True
    })
    
    raise ValidationFailedException(error_message)
```

**Unexpected Error Handling**:
```python
except Exception as e:
    session.status = "error"
    session.failure_reason = f"Completion error: {str(e)}"
    session.failure_details = {
        'error_type': 'unexpected_error',
        'recoverable': False
    }
    db.commit()
```

### 4. Retry Endpoint (/api/test-sessions/{id}/retry-completion)
Allows recovery from validation failures:

**Features**:
- Only works for validation_failed or error status
- Checks if failure is recoverable
- Tracks retry count and timestamps
- Maintains audit trail in failure_details

**Usage**:
```bash
POST /api/test-sessions/{session_id}/retry-completion

Response:
{
  "status": "success",
  "message": "Session completed successfully on retry attempt 1",
  "session_id": "xxx",
  "retry_count": 1
}
```

### 5. Session Cleanup Jobs (session_cleanup.py)
Automatic background cleanup to prevent stale sessions:

**Stale Session Cleanup**:
- Marks sessions running > 2 hours as error
- Runs every 1 hour
- Non-recoverable (prevents infinite retries)

**Orphaned Session Cleanup**:
- Cancels sessions created > 1 hour ago but never started
- Handles cases where start endpoint never called

**Startup Integration**:
```python
from services.session_cleanup import start_cleanup_scheduler

# In main.py or app startup
start_cleanup_scheduler()
```

### 6. Enhanced Status Endpoint
Returns failure information for failed sessions:

```json
{
  "session_id": "xxx",
  "status": "validation_failed",
  "failure_info": {
    "has_failed": true,
    "failure_reason": "Video sequence validation failed",
    "failed_at": "2025-11-11T12:00:00Z",
    "failure_details": {
      "validation_type": "video_sequence_completion",
      "error_message": "...",
      "recoverable": true
    },
    "retry_count": 0,
    "last_retry_at": null,
    "recoverable": true
  }
}
```

### 7. WebSocket Error Events
Frontend receives real-time failure notifications:

```javascript
websocketService.on('session_failed', (data) => {
  // data.session_id
  // data.status: 'validation_failed' or 'error'
  // data.reason: error message
  // data.recoverable: boolean
});
```

## Database Migration

Run migration to add failure tracking fields:
```bash
cd backend
alembic upgrade head
```

Migration adds:
- failure_reason (Text, indexed)
- failure_details (JSON)
- failed_at (DateTime, indexed)
- retry_count (Integer)
- last_retry_at (DateTime)

## Testing

Comprehensive test suite in `tests/test_validation_error_handling.py`:
- Validation failure scenarios
- Retry mechanism
- Cleanup jobs
- Unexpected error handling

Run tests:
```bash
python3 -m pytest tests/test_validation_error_handling.py -v
```

## Error Recovery Flow

### User-Initiated Retry:
1. Session fails validation
2. Frontend receives session_failed WebSocket event
3. User sees error dialog with retry option
4. User clicks "Retry"
5. Frontend calls POST /api/test-sessions/{id}/retry-completion
6. Backend resets status to "running" and attempts completion again

### Automatic Cleanup:
1. Session stuck in "running" for > 2 hours
2. Cleanup job marks as "error" with timeout reason
3. Frontend receives session_failed event
4. User notified session timed out

## Production Standards

✅ All failure states explicitly recorded
✅ User-friendly error messages
✅ Retry capability for recoverable errors
✅ Automatic cleanup of stale sessions
✅ Comprehensive audit trail
✅ WebSocket real-time error notifications
✅ Database migration provided
✅ Comprehensive test coverage

## Integration Checklist

- [x] Add SessionStatus enum to models.py
- [x] Add failure tracking fields to TestSession
- [x] Update session_completion_service.py with error handling
- [x] Add retry endpoint to test_sessions router
- [x] Create session_cleanup.py background jobs
- [x] Add WebSocket error event emission
- [x] Create database migration
- [x] Write comprehensive tests
- [ ] Start cleanup scheduler in main.py
- [ ] Update frontend to handle session_failed events
- [ ] Add retry UI to frontend error dialogs

## Next Steps

1. **Start Cleanup Scheduler**: Add to main.py:
   ```python
   from services.session_cleanup import start_cleanup_scheduler
   start_cleanup_scheduler()
   ```

2. **Frontend Integration**: Implement error dialog with retry button

3. **Monitoring**: Add metrics for validation failure rates

4. **Alerting**: Configure alerts for high failure rates
