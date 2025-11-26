# API Documentation - Quality Endpoints

**Version**: 1.0.0
**Last Updated**: 2025-11-19
**Base URL**: `http://localhost:8000` (development)

---

## Table of Contents

1. [Authentication](#authentication)
2. [Rate Limiting](#rate-limiting)
3. [Monitoring Endpoints](#monitoring-endpoints)
4. [Quality-Enhanced Endpoints](#quality-enhanced-endpoints)
5. [Error Codes](#error-codes)
6. [Request/Response Examples](#requestresponse-examples)
7. [WebSocket Events](#websocket-events)

---

## Authentication

**Current Status**: No authentication required (development)

**Production Recommendations**:
- Add JWT-based authentication
- Require API keys for monitoring endpoints
- Implement role-based access control (RBAC)

**Future Enhancement**:
```http
Authorization: Bearer <jwt_token>
X-API-Key: <api_key>
```

---

## Rate Limiting

**Default Limits**:
- 100 requests per 60 seconds per IP address
- Configurable via environment variables

**Configuration**:
```bash
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

**Headers**:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1637000000
```

**Rate Limit Exceeded Response**:
```json
{
  "error": "RateLimitExceeded",
  "message": "Too many requests. Please try again in 45 seconds.",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 45
}
```

---

## Monitoring Endpoints

### 1. Global Metrics

Get system-wide quality and performance metrics.

**Endpoint**: `GET /api/monitoring/metrics/global`

**Parameters**: None

**Response** (200 OK):
```json
{
  "total_sessions": 267,
  "total_detections": 29113,
  "quality_metrics": {
    "sessions_with_degraded_timing": 12,
    "sessions_with_verified_timing": 255,
    "degradation_rate": 4.5,
    "verification_rate": 95.5
  },
  "detection_metrics": {
    "usable_detections": 28950,
    "degraded_detections": 163,
    "usable_percentage": 99.4,
    "degraded_percentage": 0.6
  },
  "performance": {
    "average_response_time_ms": 127.5,
    "requests_last_hour": 1450,
    "errors_last_hour": 3
  },
  "timestamp": "2025-11-19T23:45:00Z"
}
```

**cURL Example**:
```bash
curl http://localhost:8000/api/monitoring/metrics/global
```

---

### 2. Session-Specific Metrics

Get quality metrics for a specific test session.

**Endpoint**: `GET /api/monitoring/metrics/session/{session_id}`

**Parameters**:
- `session_id` (path, required): UUID of the test session

**Response** (200 OK):
```json
{
  "session_id": "abc123-def456-ghi789",
  "session_name": "Vehicle Detection Test 001",
  "quality_level": "high",
  "timing_degraded": false,
  "timing_verified": true,
  "statistics": {
    "total_detections": 100,
    "usable_detections": 98,
    "degraded_detections": 2,
    "usable_percentage": 98.0,
    "degraded_percentage": 2.0
  },
  "warnings": [],
  "recommendations": [
    "Quality metrics are excellent - data is suitable for validation"
  ],
  "last_updated": "2025-11-19T23:30:00Z"
}
```

**cURL Example**:
```bash
curl http://localhost:8000/api/monitoring/metrics/session/abc123-def456-ghi789
```

**Error Responses**:

**404 Not Found** - Session doesn't exist:
```json
{
  "error": "NotFound",
  "message": "Test session not found",
  "code": "SESSION_NOT_FOUND"
}
```

**400 Bad Request** - Invalid UUID:
```json
{
  "error": "ValidationError",
  "message": "Invalid session ID format",
  "code": "INVALID_UUID"
}
```

---

### 3. Recent Sessions Metrics

Get metrics for recent test sessions.

**Endpoint**: `GET /api/monitoring/metrics/sessions/recent`

**Parameters**:
- `limit` (query, optional): Number of sessions to return (default: 10, max: 100)
- `quality_filter` (query, optional): Filter by quality level (`high`, `medium`, `low`, `all`)

**Response** (200 OK):
```json
{
  "sessions": [
    {
      "session_id": "abc123",
      "session_name": "Test 001",
      "quality_level": "high",
      "usable_percentage": 98.0,
      "degraded_percentage": 2.0,
      "warning_count": 0,
      "completed_at": "2025-11-19T23:30:00Z"
    },
    {
      "session_id": "def456",
      "session_name": "Test 002",
      "quality_level": "medium",
      "usable_percentage": 85.0,
      "degraded_percentage": 15.0,
      "warning_count": 1,
      "completed_at": "2025-11-19T23:15:00Z"
    }
  ],
  "total": 2,
  "limit": 10,
  "quality_filter": "all"
}
```

**cURL Example**:
```bash
# Get 5 most recent high-quality sessions
curl "http://localhost:8000/api/monitoring/metrics/sessions/recent?limit=5&quality_filter=high"
```

---

### 4. Database Health

Get database connection pool health status.

**Endpoint**: `GET /api/monitoring/health/database`

**Parameters**: None

**Response** (200 OK):
```json
{
  "status": "healthy",
  "pool": {
    "pool_size": 10,
    "active_connections": 3,
    "idle_connections": 7,
    "overflow_connections": 0,
    "utilization_percentage": 30.0
  },
  "performance": {
    "average_query_time_ms": 45.2,
    "slow_queries_count": 0,
    "connection_errors_count": 0
  },
  "warnings": [],
  "timestamp": "2025-11-19T23:45:00Z"
}
```

**Status Values**:
- `healthy`: All metrics within normal range
- `warning`: Some metrics approaching limits
- `critical`: Immediate attention required

**cURL Example**:
```bash
curl http://localhost:8000/api/monitoring/health/database
```

---

### 5. Alert History

Get recent quality alerts.

**Endpoint**: `GET /api/monitoring/alerts`

**Parameters**:
- `limit` (query, optional): Number of alerts to return (default: 50, max: 200)
- `severity` (query, optional): Filter by severity (`info`, `warning`, `error`, `critical`)
- `since` (query, optional): ISO timestamp to get alerts since

**Response** (200 OK):
```json
{
  "alerts": [
    {
      "id": "alert_001",
      "severity": "warning",
      "message": "Session abc123 has 15% degraded detections",
      "alert_type": "quality_degradation",
      "session_id": "abc123",
      "created_at": "2025-11-19T23:40:00Z",
      "acknowledged": false
    },
    {
      "id": "alert_002",
      "severity": "info",
      "message": "System health check completed successfully",
      "alert_type": "health_check",
      "created_at": "2025-11-19T23:35:00Z",
      "acknowledged": true
    }
  ],
  "total": 2,
  "limit": 50,
  "has_more": false
}
```

**cURL Example**:
```bash
# Get warning and error alerts from last hour
curl "http://localhost:8000/api/monitoring/alerts?severity=warning&since=2025-11-19T22:45:00Z"
```

---

### 6. Alert Thresholds

Get current alert threshold configuration.

**Endpoint**: `GET /api/monitoring/alerts/thresholds`

**Parameters**: None

**Response** (200 OK):
```json
{
  "degradation_threshold": 25.0,
  "validation_threshold": 75.0,
  "timing_threshold": 50.0,
  "pool_utilization_threshold": 80.0,
  "response_time_threshold_ms": 1000,
  "error_rate_threshold": 5.0
}
```

**cURL Example**:
```bash
curl http://localhost:8000/api/monitoring/alerts/thresholds
```

---

### 7. Test Alert System

Send a test alert through the alert system.

**Endpoint**: `POST /api/monitoring/alerts/test`

**Parameters**:
- `severity` (query, optional): Alert severity (`info`, `warning`, `error`, `critical`) - default: `info`
- `message` (query, optional): Custom alert message - default: "Test alert"

**Response** (200 OK):
```json
{
  "status": "success",
  "alert_sent": true,
  "handlers_notified": 2,
  "severity": "info",
  "message": "Test alert",
  "timestamp": "2025-11-19T23:45:00Z"
}
```

**cURL Example**:
```bash
curl -X POST "http://localhost:8000/api/monitoring/alerts/test?severity=warning&message=Testing%20alert%20system"
```

---

### 8. Check Alert Thresholds

Manually trigger threshold checks and generate alerts if needed.

**Endpoint**: `POST /api/monitoring/alerts/check-thresholds`

**Parameters**: None

**Response** (200 OK):
```json
{
  "checks_performed": 4,
  "alerts_generated": 1,
  "results": {
    "degradation_check": {
      "passed": false,
      "current_value": 28.5,
      "threshold": 25.0,
      "alert_generated": true
    },
    "validation_check": {
      "passed": true,
      "current_value": 89.2,
      "threshold": 75.0,
      "alert_generated": false
    },
    "timing_check": {
      "passed": true,
      "current_value": 12.3,
      "threshold": 50.0,
      "alert_generated": false
    },
    "pool_check": {
      "passed": true,
      "current_value": 35.0,
      "threshold": 80.0,
      "alert_generated": false
    }
  },
  "timestamp": "2025-11-19T23:45:00Z"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8000/api/monitoring/alerts/check-thresholds
```

---

### 9. System Status

Get overall monitoring system status.

**Endpoint**: `GET /api/monitoring/status`

**Parameters**: None

**Response** (200 OK):
```json
{
  "monitoring": {
    "active": true,
    "alert_handlers": 2,
    "alert_history_size": 15,
    "background_monitoring": true
  },
  "metrics": {
    "total_sessions": 267,
    "total_detections": 29113,
    "degradation_rate": 4.5,
    "validation_rate": 95.5
  },
  "database": {
    "status": "healthy",
    "pool_size": 10,
    "active_connections": 3,
    "utilization": 30.0
  },
  "performance": {
    "average_response_time_ms": 127.5,
    "requests_last_hour": 1450,
    "errors_last_hour": 3
  },
  "alerts": {
    "total_alerts": 15,
    "unacknowledged": 2,
    "last_alert": "2025-11-19T23:40:00Z"
  },
  "timestamp": "2025-11-19T23:45:00Z"
}
```

**cURL Example**:
```bash
curl http://localhost:8000/api/monitoring/status
```

---

## Quality-Enhanced Endpoints

These are existing endpoints that have been enhanced with automatic quality information.

### 1. Get Test Session (Enhanced)

**Endpoint**: `GET /api/test-sessions/{session_id}`

**New Fields Added**:
```json
{
  "id": "abc123-def456-ghi789",
  "name": "Test Session 001",
  "status": "completed",

  // ... existing fields ...

  "quality": {
    "timing_degraded": false,
    "timing_verified": true,
    "validation_statistics": {
      "total_detections": 100,
      "usable_detections": 98,
      "degraded_detections": 2,
      "usable_percentage": 98.0,
      "degraded_percentage": 2.0
    },
    "warnings": [],
    "recommendations": [
      "Quality metrics are excellent - data is suitable for validation"
    ],
    "quality_level": "high"
  }
}
```

**Usage**:
```bash
curl http://localhost:8000/api/test-sessions/abc123-def456-ghi789
```

---

### 2. List Test Sessions (Enhanced)

**Endpoint**: `GET /api/test-sessions`

**Parameters**:
- Standard parameters (limit, skip, project_id, etc.)
- **New**: `quality_filter` (optional): Filter by quality level

**Response**: Array of sessions with quality field included

**Usage**:
```bash
# Get high-quality sessions only
curl "http://localhost:8000/api/test-sessions?quality_filter=high"

# Get sessions with warnings
curl "http://localhost:8000/api/test-sessions?quality_filter=has_warnings"
```

---

## Error Codes

### Standard Error Format

All errors follow this format:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error description",
  "code": "MACHINE_READABLE_CODE",
  "details": {
    "additional": "context"
  }
}
```

### Error Code Reference

| HTTP Status | Code | Error Type | Description |
|-------------|------|------------|-------------|
| 400 | `INVALID_UUID` | ValidationError | Invalid UUID format |
| 400 | `INVALID_PARAMETER` | ValidationError | Invalid query parameter |
| 400 | `MISSING_REQUIRED_FIELD` | ValidationError | Required field missing |
| 401 | `UNAUTHORIZED` | AuthenticationError | Authentication required |
| 403 | `FORBIDDEN` | AuthorizationError | Insufficient permissions |
| 404 | `SESSION_NOT_FOUND` | NotFound | Test session not found |
| 404 | `ENDPOINT_NOT_FOUND` | NotFound | Endpoint does not exist |
| 429 | `RATE_LIMIT_EXCEEDED` | RateLimitError | Too many requests |
| 500 | `INTERNAL_ERROR` | ServerError | Internal server error |
| 503 | `SERVICE_UNAVAILABLE` | ServerError | Service temporarily unavailable |

### Error Examples

**Invalid UUID**:
```json
{
  "error": "ValidationError",
  "message": "Invalid session ID format. Expected UUID.",
  "code": "INVALID_UUID",
  "details": {
    "provided": "invalid-id",
    "expected_format": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  }
}
```

**Rate Limit Exceeded**:
```json
{
  "error": "RateLimitExceeded",
  "message": "Too many requests. Please try again in 45 seconds.",
  "code": "RATE_LIMIT_EXCEEDED",
  "details": {
    "limit": 100,
    "window_seconds": 60,
    "retry_after": 45
  }
}
```

**Server Error**:
```json
{
  "error": "ServerError",
  "message": "An internal error occurred. Please try again later.",
  "code": "INTERNAL_ERROR",
  "details": {
    "request_id": "req_abc123",
    "timestamp": "2025-11-19T23:45:00Z"
  }
}
```

---

## Request/Response Examples

### Example 1: Get Quality Metrics for Session

**Request**:
```bash
curl -X GET "http://localhost:8000/api/monitoring/metrics/session/abc123-def456-ghi789" \
  -H "Accept: application/json"
```

**Response** (200 OK):
```json
{
  "session_id": "abc123-def456-ghi789",
  "session_name": "Highway Vehicle Detection",
  "quality_level": "high",
  "timing_degraded": false,
  "timing_verified": true,
  "statistics": {
    "total_detections": 150,
    "usable_detections": 148,
    "degraded_detections": 2,
    "usable_percentage": 98.7,
    "degraded_percentage": 1.3
  },
  "warnings": [],
  "recommendations": [
    "Quality metrics are excellent - data is suitable for validation"
  ],
  "last_updated": "2025-11-19T23:30:00Z"
}
```

---

### Example 2: Check Database Health

**Request**:
```bash
curl -X GET "http://localhost:8000/api/monitoring/health/database" \
  -H "Accept: application/json"
```

**Response** (200 OK):
```json
{
  "status": "healthy",
  "pool": {
    "pool_size": 10,
    "active_connections": 3,
    "idle_connections": 7,
    "overflow_connections": 0,
    "utilization_percentage": 30.0
  },
  "performance": {
    "average_query_time_ms": 45.2,
    "slow_queries_count": 0,
    "connection_errors_count": 0
  },
  "warnings": [],
  "timestamp": "2025-11-19T23:45:00Z"
}
```

---

### Example 3: Test Alert System

**Request**:
```bash
curl -X POST "http://localhost:8000/api/monitoring/alerts/test?severity=warning&message=System%20test" \
  -H "Accept: application/json"
```

**Response** (200 OK):
```json
{
  "status": "success",
  "alert_sent": true,
  "handlers_notified": 2,
  "severity": "warning",
  "message": "System test",
  "timestamp": "2025-11-19T23:45:00Z"
}
```

---

### Example 4: Get Global Metrics with Filters

**Request**:
```bash
curl -X GET "http://localhost:8000/api/monitoring/metrics/global" \
  -H "Accept: application/json"
```

**Response** (200 OK):
```json
{
  "total_sessions": 267,
  "total_detections": 29113,
  "quality_metrics": {
    "sessions_with_degraded_timing": 12,
    "sessions_with_verified_timing": 255,
    "degradation_rate": 4.5,
    "verification_rate": 95.5
  },
  "detection_metrics": {
    "usable_detections": 28950,
    "degraded_detections": 163,
    "usable_percentage": 99.4,
    "degraded_percentage": 0.6
  },
  "performance": {
    "average_response_time_ms": 127.5,
    "requests_last_hour": 1450,
    "errors_last_hour": 3
  },
  "timestamp": "2025-11-19T23:45:00Z"
}
```

---

## WebSocket Events

Quality data is also available via WebSocket for real-time updates.

### Connection

**URL**: `ws://localhost:8000/socket.io/`

**Library**: Socket.IO client

**Example**:
```javascript
import io from 'socket.io-client';

const socket = io('http://localhost:8000', {
  transports: ['websocket']
});
```

### Events

#### 1. quality_update

Emitted when session quality changes.

**Payload**:
```json
{
  "event": "quality_update",
  "session_id": "abc123-def456-ghi789",
  "quality_level": "medium",
  "quality_changed": true,
  "previous_quality": "high",
  "warnings": [
    {
      "type": "timing_degraded",
      "severity": "warning",
      "message": "15% of detections have degraded timing",
      "affected_items": 15
    }
  ],
  "timestamp": "2025-11-19T23:45:00Z"
}
```

**Client Example**:
```javascript
socket.on('quality_update', (data) => {
  console.log(`Quality changed for session ${data.session_id}`);
  console.log(`New quality level: ${data.quality_level}`);
  console.log(`Warnings: ${data.warnings.length}`);
});
```

---

#### 2. quality_alert

Emitted when quality threshold is breached.

**Payload**:
```json
{
  "event": "quality_alert",
  "alert_type": "degradation_threshold",
  "severity": "warning",
  "message": "System degradation rate exceeded threshold",
  "details": {
    "current_value": 28.5,
    "threshold": 25.0,
    "sessions_affected": 12
  },
  "timestamp": "2025-11-19T23:45:00Z"
}
```

**Client Example**:
```javascript
socket.on('quality_alert', (data) => {
  if (data.severity === 'critical') {
    showCriticalAlert(data.message);
  } else {
    showWarning(data.message);
  }
});
```

---

#### 3. detection_quality

Emitted for each detection with quality information.

**Payload**:
```json
{
  "event": "detection_quality",
  "detection_id": "det_12345",
  "session_id": "abc123-def456-ghi789",
  "usable_for_validation": true,
  "timing_degraded": false,
  "confidence": 0.95,
  "quality_score": 98.5,
  "warnings": [],
  "timestamp": "2025-11-19T23:45:00.123Z"
}
```

**Client Example**:
```javascript
socket.on('detection_quality', (data) => {
  updateDetectionStatus(data.detection_id, {
    usable: data.usable_for_validation,
    quality: data.quality_score,
    warnings: data.warnings
  });
});
```

---

## Best Practices

### 1. Caching

**Recommendations**:
- Cache global metrics for 30-60 seconds
- Cache session metrics for 5 minutes (if session is completed)
- Don't cache real-time endpoints (health, status)

**Example**:
```javascript
const cache = new Map();
const CACHE_TTL = 60000; // 60 seconds

async function getGlobalMetrics() {
  const cached = cache.get('global_metrics');
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  const data = await fetch('/api/monitoring/metrics/global').then(r => r.json());
  cache.set('global_metrics', { data, timestamp: Date.now() });
  return data;
}
```

---

### 2. Error Handling

**Always handle errors gracefully**:

```javascript
async function getSessionQuality(sessionId) {
  try {
    const response = await fetch(`/api/monitoring/metrics/session/${sessionId}`);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || 'Failed to fetch quality metrics');
    }

    return await response.json();
  } catch (error) {
    console.error('Quality metrics error:', error);
    // Return fallback or show user-friendly message
    return null;
  }
}
```

---

### 3. Pagination

**For endpoints returning lists**:

```javascript
async function getAllRecentSessions() {
  const allSessions = [];
  let offset = 0;
  const limit = 50;
  let hasMore = true;

  while (hasMore) {
    const response = await fetch(
      `/api/monitoring/metrics/sessions/recent?limit=${limit}&offset=${offset}`
    );
    const data = await response.json();

    allSessions.push(...data.sessions);
    hasMore = data.has_more;
    offset += limit;
  }

  return allSessions;
}
```

---

### 4. Polling vs WebSocket

**Use WebSocket for**:
- Real-time quality updates
- Alert notifications
- Detection events
- Active monitoring dashboards

**Use REST API for**:
- Historical data
- Reports
- Batch operations
- One-time queries

---

### 5. Rate Limit Handling

**Respect rate limits**:

```javascript
async function fetchWithRateLimit(url) {
  const response = await fetch(url);

  if (response.status === 429) {
    const retryAfter = response.headers.get('X-RateLimit-Reset');
    const waitTime = retryAfter ? parseInt(retryAfter) * 1000 : 60000;

    console.log(`Rate limited. Waiting ${waitTime}ms...`);
    await sleep(waitTime);

    return fetchWithRateLimit(url); // Retry
  }

  return response;
}
```

---

## API Versioning

**Current Version**: v1 (implicit)

**Future Versions**: Will use `/api/v2/` prefix

**Deprecation Policy**: 6 months notice before removing endpoints

---

## OpenAPI Specification

**Interactive Documentation**: `http://localhost:8000/docs` (when server is running)

**OpenAPI Schema**: `http://localhost:8000/openapi.json`

**ReDoc**: `http://localhost:8000/redoc`

---

**API Documentation Version**: 1.0.0
**Last Updated**: 2025-11-19
**Maintained By**: API Team
