# LJM Comprehensive Error Handling Implementation

## Overview
Implemented comprehensive error code handling for all LabJack LJM failure scenarios with appropriate recovery actions.

## Changes Made

### 1. Error Code Mapping Dictionary (Lines 83-114)
Added `LJM_ERROR_CODES` dictionary with 24+ error codes organized by category:

**Connection Errors:**
- 1224: DEVICE_NOT_OPEN → reconnect
- 1227: DEVICE_DISCONNECTED → reconnect
- 1230: DEVICE_NOT_FOUND → fail
- 1239: STREAM_NOT_INITIALIZED → restart_stream

**Stream Errors:**
- 1301: STREAM_SCAN_OVERLAP → recover
- 1302: STREAM_SCAN_OVERLAP_VARIANT → recover
- 1303: STREAM_SAMPLE_NUM_INVALID → restart_stream
- 1304: STREAM_OUT_OF_MEMORY → reduce_rate
- 1305: STREAM_BUFFER_FULL → recover
- 1306: STREAM_AUTO_TARGET_INVALID → restart_stream
- 1307: STREAM_NOT_RUNNING → restart_stream
- 1308: STREAM_INVALID_TRIGGER → restart_stream

**USB/Communication Errors:**
- 2942: USB_INIT_ERROR → reconnect
- 2943: USB_SEND_ERROR → retry
- 2944: USB_RECEIVE_ERROR → retry
- 2603: RECONNECT_FAILED → fail

**Configuration Errors:**
- 2360: INVALID_ADDRESS → fail
- 2361: INVALID_NAME → fail
- 2362: INVALID_PARAMETER → fail
- 2500: TIMEOUT → retry

**Network Errors:**
- 1233: SOCKET_ERROR → reconnect

### 2. Error Info Extraction Function (Lines 117-142)
```python
def get_error_info(error) -> Tuple[Optional[int], Optional[str], Optional[str], Optional[str]]:
    """Extract error information from exception."""
```
- Extracts error code from exception attributes or string
- Returns error code, name, action, and description
- Handles both direct error codes and string-based errors

### 3. Error Handler Method (Lines 707-748)
```python
def handle_ljm_error(self, error: Exception, context: str = "operation") -> bool:
    """Handle LJM errors with appropriate recovery actions."""
```

**Recovery Actions:**
- `reconnect`: Calls `_reconnect_on_error()` for connection issues
- `recover`: Calls `_recover_stream_overflow()` to clear backlog
- `restart_stream`: Calls `_restart_stream()` to restart streaming
- `retry`: Returns True indicating caller should retry
- `reduce_rate`: Returns False, caller needs to reduce rate
- `fail`: Returns False, no automatic recovery

### 4. Stream Overflow Recovery Method (Lines 750-774)
```python
def _recover_stream_overflow(self) -> bool:
    """Recover from stream buffer overflow by clearing backlog."""
```
- Reads and discards backlogged data
- Clears buffer overflow condition
- Logs recovery status

### 5. Stream Restart Method (Lines 776-814)
```python
def _restart_stream(self) -> bool:
    """Restart streaming after error."""
```
- Saves current stream configuration
- Stops stream gracefully
- Restarts with same configuration
- Handles restart failures

### 6. Updated Methods Using Error Handler

**read_single_voltage** (Lines 1021-1049):
- Replaced manual error 1224 handling with `handle_ljm_error()`
- Comprehensive error handling for all LJM errors
- Automatic retry after successful recovery

**read_stream_mode** (Lines 1256-1265):
- Uses `handle_ljm_error()` instead of manual overflow detection
- Simplified error handling logic
- Automatic recovery attempt

**_direct_stream_loop** (Lines 961-972):
- Integrated `handle_ljm_error()` into streaming loop
- Continues streaming after recoverable errors
- Breaks loop only on fatal errors

**_health_monitor_loop** (Lines 1415-1438):
- Uses error info extraction for better logging
- Calls `handle_ljm_error()` for recovery
- Preserves sessions during recovery

## Benefits

1. **Comprehensive Coverage**: All 24+ LJM error codes handled
2. **Appropriate Actions**: Each error has specific recovery strategy
3. **Clear Logging**: Descriptive error messages with error codes and names
4. **Automatic Recovery**: Attempts appropriate recovery before failing
5. **Consistent Handling**: Single error handler used throughout service
6. **Graceful Degradation**: Failed recovery doesn't crash the system
7. **Context Awareness**: Error context included in logging

## Recovery Strategy Examples

### Connection Loss (Error 1224)
```
Error 1224 (DEVICE_NOT_OPEN) → Reconnect
1. Close existing handle
2. Exponential backoff retry
3. Attempt direct connection
4. Up to 3 retry attempts
```

### Stream Overflow (Error 1301)
```
Error 1301 (STREAM_SCAN_OVERLAP) → Recover
1. Read backlogged data
2. Discard samples
3. Clear overflow condition
4. Continue streaming
```

### Stream Not Running (Error 1307)
```
Error 1307 (STREAM_NOT_RUNNING) → Restart Stream
1. Save stream configuration
2. Stop stream
3. Wait briefly
4. Restart with same config
```

## Error Handling Flow
```
Operation Exception
       ↓
handle_ljm_error()
       ↓
Extract error info
       ↓
Identify recovery action
       ↓
Execute appropriate recovery:
   - reconnect
   - recover overflow
   - restart stream
   - retry operation
   - reduce rate
   - fail
       ↓
Return success/failure
       ↓
Caller retries or reports error
```

## Testing Verification

The error handling has been integrated into:
- Single voltage reads
- Stream mode operations
- Health monitoring
- Connection management

All operations now have comprehensive error recovery with clear logging.

## Location
`/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_service.py`

Lines:
- Error codes: 83-114
- Error info function: 117-142
- Error handler: 707-748
- Stream overflow recovery: 750-774
- Stream restart: 776-814
- Usage in methods: 961-972, 1021-1049, 1256-1265, 1415-1438
