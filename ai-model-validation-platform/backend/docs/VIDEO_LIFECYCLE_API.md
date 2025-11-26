# Video Lifecycle API - Integration Guide

**Version:** 1.0.0
**Date:** 2025-11-20
**Status:** Production-Ready

## Overview

The Video Lifecycle API provides per-video start/stop monitoring control for HIL testing platforms. It coordinates timing between Browser → Backend → LabJack with software-only drift compensation.

**Key Features:**
- ✅ Per-video monitoring control (start/stop)
- ✅ Clock synchronization and drift compensation
- ✅ Production-grade error handling
- ✅ Rate limiting (30-120 req/min per endpoint)
- ✅ Comprehensive logging
- ✅ Health checks
- ✅ Transaction management

## Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Browser   │         │   Backend   │         │   LabJack   │
│   (React)   │         │   (Python)  │         │   Device    │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                        │
       │ POST /video-started   │                        │
       ├──────────────────────>│                        │
       │                       │ start_monitoring()     │
       │                       ├───────────────────────>│
       │                       │                        │
       │                       │<───────────────────────┤
       │<──────────────────────┤                        │
       │   {drift_ms: 25.3}    │                        │
       │                       │                        │
       │   ... video plays ... │   ... monitoring ...   │
       │                       │                        │
       │ POST /video-ended     │                        │
       ├──────────────────────>│                        │
       │                       │ stop_monitoring()      │
       │                       ├───────────────────────>│
       │                       │                        │
       │<──────────────────────┤                        │
       │  {detections: 15}     │                        │
```

## API Endpoints

### 1. Start Video Monitoring

**Endpoint:** `POST /api/video-lifecycle/{session_id}/video-started`

**Description:** Notifies backend that video playback has started. Initiates LabJack monitoring and records timing for drift compensation.

**Rate Limit:** 30 requests/minute

**Request Body:**
```json
{
  "video_id": "video_001",
  "frontend_timestamp": 12345.678,
  "video_url": "/videos/test_video.mp4",
  "video_duration_ms": 30000,
  "video_fps": 30.0,
  "browser_timezone": "America/New_York",
  "metadata": {
    "test_type": "HIL",
    "camera_view": "front"
  }
}
```

**Success Response (200):**
```json
{
  "success": true,
  "video_id": "video_001",
  "session_id": "session_abc123",
  "monitoring_status": "active",
  "timing": {
    "frontend_timestamp_ms": 12345.678,
    "backend_timestamp_s": 1700000000.123,
    "labjack_timestamp_s": 1700000000.150,
    "clock_offset_ms": 50.5,
    "drift_ms": 27.0,
    "latency_ms": 10.5
  },
  "message": "Video monitoring started successfully",
  "warnings": ["Drift of 27ms detected, within acceptable range"]
}
```

**Error Responses:**
- **400 Bad Request:** Invalid request payload
- **409 Conflict:** Session already has active video
- **503 Service Unavailable:** LabJack not responding (retry after 30s)

---

### 2. Stop Video Monitoring

**Endpoint:** `POST /api/video-lifecycle/{session_id}/video-ended`

**Description:** Notifies backend that video has ended. Stops LabJack monitoring and returns final statistics.

**Rate Limit:** 30 requests/minute

**Request Body:**
```json
{
  "video_id": "video_001",
  "frontend_timestamp": 42345.678,
  "detection_count": 15,
  "playback_duration_ms": 29850,
  "ended_naturally": true,
  "metadata": {
    "user_stopped": false
  }
}
```

**Success Response (200):**
```json
{
  "success": true,
  "video_id": "video_001",
  "session_id": "session_abc123",
  "monitoring_status": "stopped",
  "detections_recorded": 15,
  "timing": {
    "frontend_timestamp_ms": 42345.678,
    "backend_timestamp_s": 1700000030.123,
    "clock_offset_ms": 50.5
  },
  "message": "Video monitoring stopped successfully, 15 detections recorded"
}
```

**Error Responses:**
- **404 Not Found:** No active video for session
- **503 Service Unavailable:** LabJack not responding

---

### 3. Report Video Error

**Endpoint:** `POST /api/video-lifecycle/{session_id}/video-error`

**Description:** Reports video playback error. Performs cleanup and stops monitoring if active.

**Rate Limit:** 30 requests/minute

**Request Body:**
```json
{
  "video_id": "video_001",
  "frontend_timestamp": 15000.123,
  "error_code": "MEDIA_ERR_NETWORK",
  "error_message": "Failed to load video due to network error",
  "stack_trace": "Error: ...",
  "metadata": {
    "network_status": "offline"
  }
}
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Video error recorded and monitoring cleaned up",
  "session_id": "session_abc123",
  "video_id": "video_001"
}
```

---

### 4. Get Session Status

**Endpoint:** `GET /api/video-lifecycle/{session_id}/status`

**Description:** Get current video lifecycle and monitoring status for a session.

**Rate Limit:** 60 requests/minute

**Success Response (200):**
```json
{
  "session_id": "session_abc123",
  "current_video_id": "video_001",
  "monitoring_active": true,
  "monitoring_status": "active",
  "video_start_time": "2025-11-20T10:30:45.123Z",
  "elapsed_time_ms": 15234.5,
  "detections_count": 8,
  "drift_ms": 25.3,
  "health": "healthy",
  "last_error": null
}
```

---

### 5. Get Drift Statistics

**Endpoint:** `GET /api/video-lifecycle/{session_id}/drift-stats`

**Description:** Get drift measurement statistics for a session.

**Rate Limit:** 60 requests/minute

**Success Response (200):**
```json
{
  "session_id": "session_abc123",
  "total_videos": 5,
  "mean_drift_ms": 25.5,
  "median_drift_ms": 24.0,
  "std_dev_ms": 8.3,
  "min_drift_ms": 15.2,
  "max_drift_ms": 42.1,
  "drift_trend": "stable",
  "quality_assessment": "excellent",
  "warnings": [],
  "calculated_at": "2025-11-20T10:35:00.000Z"
}
```

---

### 6. Health Check

**Endpoint:** `GET /api/video-lifecycle/health`

**Description:** Check health status of video lifecycle system.

**Rate Limit:** 120 requests/minute

**Success Response (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "database": "healthy",
    "labjack": "healthy",
    "clock_sync": "healthy",
    "drift_measurement": "healthy"
  },
  "active_sessions": 2,
  "monitoring_active": true,
  "last_error": null,
  "uptime_seconds": 3600.5,
  "timestamp": "2025-11-20T10:30:00.000Z"
}
```

## Frontend Integration

### React/TypeScript Example

```typescript
import axios from 'axios';

class VideoLifecycleClient {
  private baseUrl: string = '/api/video-lifecycle';
  private sessionId: string;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  /**
   * Notify backend that video has started playing
   */
  async videoStarted(videoId: string, videoUrl: string): Promise<void> {
    const frontendTimestamp = performance.now();

    try {
      const response = await axios.post(
        `${this.baseUrl}/${this.sessionId}/video-started`,
        {
          video_id: videoId,
          frontend_timestamp: frontendTimestamp,
          video_url: videoUrl,
          browser_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          performance_origin: performance.timeOrigin
        }
      );

      const { timing, warnings } = response.data;

      console.log(`✅ Monitoring started. Drift: ${timing.drift_ms.toFixed(1)}ms`);

      if (warnings.length > 0) {
        console.warn('⚠️ Warnings:', warnings);
      }

      // Store timing for detection correlation
      this.saveTiming(timing);

    } catch (error) {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;

        if (status === 409) {
          // Session already has active video
          console.error('❌ Video already active. Stop current video first.');
        } else if (status === 503) {
          // LabJack not responding
          const retryAfter = error.response?.data?.retry_after_seconds || 30;
          console.error(`❌ LabJack unavailable. Retry after ${retryAfter}s`);
        }
      }

      throw error;
    }
  }

  /**
   * Notify backend that video has ended
   */
  async videoEnded(videoId: string, detectionCount: number): Promise<void> {
    const frontendTimestamp = performance.now();

    try {
      const response = await axios.post(
        `${this.baseUrl}/${this.sessionId}/video-ended`,
        {
          video_id: videoId,
          frontend_timestamp: frontendTimestamp,
          detection_count: detectionCount,
          ended_naturally: true
        }
      );

      const { detections_recorded } = response.data;

      console.log(`✅ Monitoring stopped. Detections: ${detections_recorded}`);

    } catch (error) {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;

        if (status === 404) {
          // No active video
          console.error('❌ No active video to stop.');
        }
      }

      throw error;
    }
  }

  /**
   * Report video error
   */
  async videoError(videoId: string, error: Error): Promise<void> {
    const frontendTimestamp = performance.now();

    try {
      await axios.post(
        `${this.baseUrl}/${this.sessionId}/video-error`,
        {
          video_id: videoId,
          frontend_timestamp: frontendTimestamp,
          error_code: error.name,
          error_message: error.message,
          stack_trace: error.stack
        }
      );

      console.log('✅ Video error reported and cleaned up');

    } catch (err) {
      console.error('Failed to report video error:', err);
    }
  }

  /**
   * Get current session status
   */
  async getStatus(): Promise<VideoLifecycleStatus> {
    const response = await axios.get(
      `${this.baseUrl}/${this.sessionId}/status`
    );

    return response.data;
  }

  private saveTiming(timing: any): void {
    // Store timing information for detection correlation
    sessionStorage.setItem('video_lifecycle_timing', JSON.stringify(timing));
  }
}

// Usage in React component
const VideoPlayer: React.FC = () => {
  const sessionId = 'session_abc123';
  const lifecycleClient = new VideoLifecycleClient(sessionId);

  const handleVideoPlay = async () => {
    const videoElement = document.getElementById('test-video') as HTMLVideoElement;

    try {
      await lifecycleClient.videoStarted('video_001', videoElement.src);
    } catch (error) {
      console.error('Failed to start monitoring:', error);
    }
  };

  const handleVideoEnded = async () => {
    try {
      await lifecycleClient.videoEnded('video_001', detectionCount);
    } catch (error) {
      console.error('Failed to stop monitoring:', error);
    }
  };

  const handleVideoError = async (error: Error) => {
    try {
      await lifecycleClient.videoError('video_001', error);
    } catch (err) {
      console.error('Failed to report error:', err);
    }
  };

  return (
    <video
      id="test-video"
      onPlaying={handleVideoPlay}
      onEnded={handleVideoEnded}
      onError={(e) => handleVideoError(new Error(e.currentTarget.error?.message || 'Unknown error'))}
    >
      <source src="/videos/test_video.mp4" type="video/mp4" />
    </video>
  );
};
```

## Error Handling

### HTTP Status Codes

| Code | Description | Action |
|------|-------------|--------|
| 200 | Success | Process response |
| 400 | Bad Request | Fix request payload |
| 404 | Not Found | Check session has active video |
| 409 | Conflict | Stop current video first |
| 429 | Too Many Requests | Wait for retry-after seconds |
| 500 | Internal Server Error | Report to backend team |
| 503 | Service Unavailable | Retry with exponential backoff |

### Retry Strategy

```typescript
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  initialDelay: number = 1000
): Promise<T> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;

        // Don't retry client errors (400, 409, 404)
        if (status && status >= 400 && status < 500 && status !== 429) {
          throw error;
        }

        // Respect Retry-After header
        const retryAfter = error.response?.headers['retry-after'];
        if (retryAfter) {
          const delay = parseInt(retryAfter) * 1000;
          await sleep(delay);
          continue;
        }
      }

      // Exponential backoff for server errors
      if (i < maxRetries - 1) {
        const delay = initialDelay * Math.pow(2, i);
        console.log(`Retrying in ${delay}ms...`);
        await sleep(delay);
      } else {
        throw error;
      }
    }
  }

  throw new Error('Max retries exceeded');
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
```

## Rate Limiting

### Rate Limit Headers

All responses include rate limit information:

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1700000060
```

### Handling 429 Too Many Requests

```typescript
if (error.response?.status === 429) {
  const retryAfter = error.response.headers['retry-after'];
  console.warn(`Rate limited. Retry after ${retryAfter}s`);

  // Wait and retry
  await sleep(parseInt(retryAfter) * 1000);
  return await retryRequest();
}
```

## Monitoring and Logging

### Backend Logs

All requests are logged with structured JSON:

```json
{
  "timestamp": "2025-11-20T10:30:45.123Z",
  "level": "INFO",
  "message": "Video started successfully",
  "session_id": "session_abc123",
  "video_id": "video_001",
  "drift_ms": 25.3,
  "request_id": "req_1700000045123"
}
```

### Metrics to Monitor

- **Drift Statistics:** Track mean, median, and max drift
- **Error Rate:** Monitor 5xx responses
- **Latency:** P50, P95, P99 response times
- **Rate Limit Hits:** Track 429 responses
- **Active Sessions:** Number of concurrent monitoring sessions

## Production Deployment

### Prerequisites

1. **Services Running:**
   - PostgreSQL database
   - LabJack device connected
   - Clock sync service initialized

2. **Environment Variables:**
   ```bash
   DATABASE_URL=postgresql://user:pass@localhost:5432/hildb
   LABJACK_DEVICE_ID=T7_001
   LOG_LEVEL=INFO
   ENABLE_RATE_LIMITING=true
   ```

3. **Database Migrations:**
   ```bash
   alembic upgrade head
   ```

### Integration with Main App

```python
# In main.py or app.py

from fastapi import FastAPI
from src.routes.video_lifecycle_routes import router as video_lifecycle_router
from src.routes.video_lifecycle_routes import setup_video_lifecycle_routes
from src.middleware.rate_limiting import rate_limit_middleware

app = FastAPI()

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Include video lifecycle routes
app.include_router(video_lifecycle_router)

@app.on_event("startup")
async def startup():
    # Initialize video lifecycle services
    await setup_video_lifecycle_routes(app)
```

## Testing

### Unit Tests

```python
import pytest
from src.services.video_lifecycle_orchestrator import VideoLifecycleOrchestrator

@pytest.mark.asyncio
async def test_video_started_success():
    """Test successful video start"""
    orchestrator = VideoLifecycleOrchestrator(...)

    response = await orchestrator.handle_video_started(
        session_id="test_session",
        request=VideoStartedRequest(
            video_id="test_video",
            frontend_timestamp=12345.678,
            video_url="/test.mp4"
        ),
        db=mock_db
    )

    assert response.success is True
    assert response.monitoring_status == "active"
    assert response.timing.drift_ms < 100  # Drift within spec
```

### Integration Tests

```bash
# Start test environment
docker-compose up -d

# Run integration tests
pytest tests/integration/test_video_lifecycle_api.py -v
```

## Support

For issues or questions:
- **Documentation:** `/docs` (Swagger UI)
- **GitHub Issues:** [Report Bug](https://github.com/...)
- **Email:** support@...

---

**Version:** 1.0.0
**Last Updated:** 2025-11-20
**Maintained By:** Backend API Developer Team
