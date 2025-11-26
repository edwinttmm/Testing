# Video Lifecycle API - Quick Integration Guide

## Overview

This guide provides step-by-step instructions for integrating the Video Lifecycle API into your HIL testing platform.

## Files Created

### 1. Data Models
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/src/models/video_lifecycle_models.py`

Pydantic models for request/response validation:
- `VideoStartedRequest` - Video start event
- `VideoEndedRequest` - Video end event
- `VideoErrorRequest` - Video error event
- `VideoStartedResponse` - Start response with timing
- `VideoEndedResponse` - End response with stats
- `VideoLifecycleStatus` - Current session status
- `DriftStatisticsResponse` - Drift analytics
- `ErrorResponse` - Standard error format
- `HealthCheckResponse` - System health

### 2. Orchestrator Service
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/src/services/video_lifecycle_orchestrator.py`

Main coordination service:
- Coordinates Browser → Backend → LabJack timing
- Integrates with `ClockSyncService` for clock offset
- Uses `DriftMeasurementService` for tracking
- Calls `DedicatedLabJackMonitor` for hardware control
- Manages session state and error handling

### 3. API Routes
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/src/routes/video_lifecycle_routes.py`

FastAPI endpoints:
- `POST /api/video-lifecycle/{session_id}/video-started`
- `POST /api/video-lifecycle/{session_id}/video-ended`
- `POST /api/video-lifecycle/{session_id}/video-error`
- `GET /api/video-lifecycle/{session_id}/status`
- `GET /api/video-lifecycle/{session_id}/drift-stats`
- `GET /api/video-lifecycle/health`

### 4. Rate Limiting Middleware
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/src/middleware/rate_limiting.py`

Production-grade rate limiting:
- Sliding window algorithm
- Per-client IP tracking
- Per-endpoint limits
- 429 responses with Retry-After headers

### 5. Configuration
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/src/config/video_lifecycle_config.py`

Centralized configuration:
- Environment-based settings
- Rate limit configuration
- Drift thresholds
- LabJack settings
- Logging configuration

### 6. Documentation
**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/docs/VIDEO_LIFECYCLE_API.md`

Complete API documentation with:
- Endpoint specifications
- Request/response examples
- Frontend integration code
- Error handling strategies
- Testing guidelines

## Integration Steps

### Step 1: Install Dependencies

Add to `requirements.txt`:
```
slowapi>=0.1.9  # For rate limiting
```

Install:
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Create `.env` file or set environment variables:

```bash
# Environment
ENVIRONMENT=development  # or production

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/hildb

# LabJack
LABJACK_DEVICE_ID=T7_001
LABJACK_CONNECTION_TYPE=USB
LABJACK_SAMPLE_RATE_HZ=1000

# Rate Limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_VIDEO_STARTED=30
RATE_LIMIT_VIDEO_ENDED=30
RATE_LIMIT_STATUS=60

# Drift Configuration
ACCEPTABLE_DRIFT_MS=50.0
WARNING_DRIFT_MS=100.0
CRITICAL_DRIFT_MS=500.0

# Logging
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_FILE_PATH=/var/log/video_lifecycle/api.log
```

### Step 3: Integrate Routes with Main App

In your `main.py` or `app.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import video lifecycle components
from src.routes.video_lifecycle_routes import (
    router as video_lifecycle_router,
    setup_video_lifecycle_routes
)
from src.middleware.rate_limiting import rate_limit_middleware
from src.config.video_lifecycle_config import initialize_config

# Create FastAPI app
app = FastAPI(
    title="HIL Testing Platform API",
    version="1.0.0",
    description="Hardware-in-the-Loop Testing Platform"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Include video lifecycle routes
app.include_router(video_lifecycle_router)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    # Initialize configuration
    config = initialize_config()
    print(f"✅ Configuration loaded for {config.environment.value}")

    # Initialize video lifecycle services
    await setup_video_lifecycle_routes(app)
    print("✅ Video lifecycle API initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Shutting down video lifecycle API...")

# Health check for main app
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "HIL Testing Platform",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Step 4: Run Database Migrations (if needed)

If you need to add database tables for video lifecycle state:

```bash
# Create migration
alembic revision -m "Add video lifecycle tables"

# Edit migration file to add tables
# Then run migration
alembic upgrade head
```

### Step 5: Start the Server

```bash
# Development
uvicorn main:app --reload --port 8000

# Production
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Step 6: Test the API

Using curl:

```bash
# Health check
curl http://localhost:8000/api/video-lifecycle/health

# Start video monitoring
curl -X POST http://localhost:8000/api/video-lifecycle/session_abc123/video-started \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "video_001",
    "frontend_timestamp": 12345.678,
    "video_url": "/videos/test.mp4"
  }'

# Get session status
curl http://localhost:8000/api/video-lifecycle/session_abc123/status

# End video monitoring
curl -X POST http://localhost:8000/api/video-lifecycle/session_abc123/video-ended \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "video_001",
    "frontend_timestamp": 42345.678,
    "detection_count": 15
  }'
```

Using Python requests:

```python
import requests

BASE_URL = "http://localhost:8000/api/video-lifecycle"
SESSION_ID = "session_abc123"

# Start video
response = requests.post(
    f"{BASE_URL}/{SESSION_ID}/video-started",
    json={
        "video_id": "video_001",
        "frontend_timestamp": 12345.678,
        "video_url": "/videos/test.mp4"
    }
)

print(f"Status: {response.status_code}")
print(f"Drift: {response.json()['timing']['drift_ms']:.2f}ms")

# End video
response = requests.post(
    f"{BASE_URL}/{SESSION_ID}/video-ended",
    json={
        "video_id": "video_001",
        "frontend_timestamp": 42345.678,
        "detection_count": 15
    }
)

print(f"Detections recorded: {response.json()['detections_recorded']}")
```

## Frontend Integration

### React TypeScript Example

```typescript
// src/services/VideoLifecycleService.ts
import axios from 'axios';

export class VideoLifecycleService {
  private baseUrl = '/api/video-lifecycle';
  private sessionId: string;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  async startVideo(videoId: string, videoUrl: string) {
    const response = await axios.post(
      `${this.baseUrl}/${this.sessionId}/video-started`,
      {
        video_id: videoId,
        frontend_timestamp: performance.now(),
        video_url: videoUrl
      }
    );
    return response.data;
  }

  async endVideo(videoId: string, detectionCount: number) {
    const response = await axios.post(
      `${this.baseUrl}/${this.sessionId}/video-ended`,
      {
        video_id: videoId,
        frontend_timestamp: performance.now(),
        detection_count: detectionCount
      }
    );
    return response.data;
  }

  async getStatus() {
    const response = await axios.get(
      `${this.baseUrl}/${this.sessionId}/status`
    );
    return response.data;
  }
}
```

### Usage in React Component

```typescript
// src/components/VideoPlayer.tsx
import React, { useEffect, useRef } from 'react';
import { VideoLifecycleService } from '../services/VideoLifecycleService';

export const VideoPlayer: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const lifecycleService = new VideoLifecycleService('session_abc123');

  const handlePlaying = async () => {
    try {
      const result = await lifecycleService.startVideo(
        'video_001',
        videoRef.current?.src || ''
      );
      console.log('Monitoring started, drift:', result.timing.drift_ms);
    } catch (error) {
      console.error('Failed to start monitoring:', error);
    }
  };

  const handleEnded = async () => {
    try {
      const result = await lifecycleService.endVideo('video_001', 15);
      console.log('Monitoring stopped, detections:', result.detections_recorded);
    } catch (error) {
      console.error('Failed to stop monitoring:', error);
    }
  };

  return (
    <video
      ref={videoRef}
      onPlaying={handlePlaying}
      onEnded={handleEnded}
      controls
    >
      <source src="/videos/test.mp4" type="video/mp4" />
    </video>
  );
};
```

## Monitoring and Logging

### View Logs

```bash
# Tail logs
tail -f /var/log/video_lifecycle/api.log

# Search for errors
grep "ERROR" /var/log/video_lifecycle/api.log

# Check drift measurements
grep "drift_ms" /var/log/video_lifecycle/api.log
```

### Metrics to Monitor

1. **Drift Statistics**
   - Mean drift (should be < 50ms)
   - Max drift (should be < 100ms)
   - Drift trend (should be "stable")

2. **API Performance**
   - Response times (P50, P95, P99)
   - Error rate (should be < 1%)
   - Rate limit hits (429 responses)

3. **System Health**
   - Active sessions
   - LabJack connection status
   - Database connection pool

## Troubleshooting

### Issue: "Video lifecycle orchestrator not initialized"

**Solution:** Ensure `setup_video_lifecycle_routes()` is called in startup event:

```python
@app.on_event("startup")
async def startup_event():
    await setup_video_lifecycle_routes(app)
```

### Issue: "LabJack not responding" (503)

**Solution:**
1. Check LabJack device connection
2. Verify `LABJACK_DEVICE_ID` in environment
3. Test with fallback mode: `LABJACK_ENABLE_FALLBACK=true`

### Issue: "Rate limit exceeded" (429)

**Solution:**
1. Wait for `retry_after_seconds` from response
2. Increase rate limits in `.env` if legitimate traffic
3. Check for infinite loops in frontend code

### Issue: High drift (> 100ms)

**Solution:**
1. Check network latency (use wired connection)
2. Verify clock synchronization is working
3. Review system load and CPU usage
4. Consider hardware timestamping for sub-ms accuracy

## Production Deployment Checklist

- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Configure proper `DATABASE_URL`
- [ ] Set restrictive CORS origins
- [ ] Enable rate limiting with appropriate limits
- [ ] Configure log rotation
- [ ] Set up monitoring and alerting
- [ ] Test LabJack connection
- [ ] Run database migrations
- [ ] Configure reverse proxy (nginx/traefik)
- [ ] Set up SSL/TLS certificates
- [ ] Test error handling scenarios
- [ ] Verify drift compensation is working
- [ ] Load test with expected traffic

## Support

- **Full API Documentation:** `/docs/VIDEO_LIFECYCLE_API.md`
- **Swagger UI:** `http://localhost:8000/docs` (when running)
- **Configuration Reference:** `/src/config/video_lifecycle_config.py`
- **Examples:** See `/docs/VIDEO_LIFECYCLE_API.md`

## Summary

You now have a production-ready video lifecycle API with:

✅ **6 REST endpoints** for video monitoring control
✅ **Type-safe Pydantic models** for validation
✅ **Production error handling** with retries
✅ **Rate limiting** to prevent abuse
✅ **Comprehensive logging** for debugging
✅ **Health checks** for monitoring
✅ **Configuration management** via environment variables
✅ **Frontend integration examples** for React/TypeScript

The API is ready to integrate with your existing HIL testing platform!
