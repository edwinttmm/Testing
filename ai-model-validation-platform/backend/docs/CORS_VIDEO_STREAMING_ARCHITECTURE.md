# CORS Video Streaming Architecture - Root Cause Analysis & Solution

## Executive Summary

**Problem**: Video files fail to load from frontend with CORS error despite CORS headers being added to FileResponse.

**Root Cause**: FastAPI's middleware execution order causes CORSMiddleware to override manually-set CORS headers in FileResponse objects.

**Impact**: Video playback completely broken in frontend application.

## Root Cause Analysis

### 1. Middleware Execution Order Issue

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`

**Current Configuration (Lines 483-491)**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
    expose_headers=["*"],
    max_age=3600,
)
```

**Problem**: Middleware executes in REVERSE order of registration:
1. Request comes in → CORSMiddleware (first registered, last executed)
2. Custom security middleware (lines 4074-4087)
3. Process time middleware (lines 4089-4102)
4. Database error middleware (lines 4038-4072)
5. Route handler returns FileResponse with custom CORS headers (lines 577-589)
6. Response flows back through middleware stack
7. **CORSMiddleware overwrites FileResponse headers with its own logic**

### 2. CORSMiddleware Behavior with FileResponse

**Issue**: Starlette's CORSMiddleware has special handling that:
- Removes existing CORS headers from responses
- Applies its own CORS logic based on configuration
- Does NOT preserve manually-set headers on FileResponse objects

**Evidence from testing**:
```bash
$ curl -I http://localhost:8000/api/videos/test/file
HTTP/1.1 405 Method Not Allowed  # HEAD not handled
```

### 3. Missing OPTIONS Handler

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py:549`

**Current Endpoint**:
```python
@app.get("/api/videos/{video_id}/file")
async def get_video_file(video_id: str, db: Session = Depends(get_db)):
```

**Problem**:
- Only handles GET requests
- No OPTIONS handler for CORS preflight
- No HEAD support for byte-range requests
- Frontend browsers send OPTIONS before GET for cross-origin requests

### 4. CORS Configuration Limitations

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/config.py:46-55`

**Current CORS Settings**:
```python
cors_origins: List[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]
cors_credentials: bool = True
cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
cors_headers: List[str] = ["*"]
```

**Issues**:
- `expose_headers=["*"]` in middleware config (line 489) doesn't work properly with FileResponse
- Missing explicit exposure of critical headers: `Content-Range`, `Accept-Ranges`, `Content-Length`
- Browser needs these headers exposed to handle byte-range requests

## Architectural Design for Solution

### Architecture Decision Record (ADR)

**ADR-001: CORS Handling for Video Streaming**

**Context**:
- Video files require byte-range request support
- CORS headers must be properly exposed for browsers
- FastAPI middleware order affects header propagation

**Decision**: Implement a dual-layer CORS strategy:
1. **Layer 1**: CORSMiddleware for general API endpoints
2. **Layer 2**: Custom CORS handling for FileResponse endpoints (bypasses middleware)

**Consequences**:
- Video endpoints will have explicit CORS handling
- Maintenance requires updating both layers for CORS changes
- Better control over headers for streaming endpoints

### Solution Architecture

```
┌─────────────────────────────────────────────────────┐
│                Browser (Frontend)                    │
│            http://localhost:3000                     │
└─────────────┬───────────────────────────────────────┘
              │
              │ 1. OPTIONS /api/videos/{id}/file
              │    (CORS Preflight)
              ▼
┌─────────────────────────────────────────────────────┐
│           FastAPI Backend (main.py)                  │
│                                                      │
│  ┌───────────────────────────────────────────┐     │
│  │  CORSMiddleware (Line 483-491)            │     │
│  │  - Handles general API CORS               │     │
│  │  - Processes OPTIONS for /api/* routes    │     │
│  └───────────────────────────────────────────┘     │
│              │                                       │
│              │ Passes through to route handlers     │
│              ▼                                       │
│  ┌───────────────────────────────────────────┐     │
│  │  Video File Endpoint (NEW)                │     │
│  │  @app.options("/api/videos/{id}/file")    │     │
│  │  @app.head("/api/videos/{id}/file")       │     │
│  │  @app.get("/api/videos/{id}/file")        │     │
│  │                                            │     │
│  │  - Manual CORS header injection           │     │
│  │  - Bypasses CORSMiddleware override       │     │
│  │  - Exposes byte-range headers             │     │
│  └───────────────────────────────────────────┘     │
│              │                                       │
│              │ 2. Returns Response with headers     │
│              ▼                                       │
│  ┌───────────────────────────────────────────┐     │
│  │  Custom Middleware (AFTER FileResponse)   │     │
│  │  - add_security_headers (4074-4087)       │     │
│  │  - add_process_time_header (4089-4102)    │     │
│  │  - PRESERVES CORS headers                 │     │
│  └───────────────────────────────────────────┘     │
└─────────────┬───────────────────────────────────────┘
              │
              │ 3. Response with proper CORS headers
              ▼
┌─────────────────────────────────────────────────────┐
│            Browser receives video stream             │
│       - Access-Control-Allow-Origin: *              │
│       - Access-Control-Expose-Headers: ...          │
│       - Accept-Ranges: bytes                        │
└─────────────────────────────────────────────────────┘
```

## Implementation Plan

### Change 1: Add OPTIONS Handler (High Priority)

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Location**: Before line 549

**Add**:
```python
@app.options("/api/videos/{video_id}/file")
async def video_file_options(video_id: str):
    """Handle CORS preflight for video file endpoint"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Accept, Content-Type, Authorization",
            "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges, Content-Type",
            "Access-Control-Max-Age": "3600"
        }
    )
```

### Change 2: Add HEAD Handler (High Priority)

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Location**: Before line 549

**Add**:
```python
@app.head("/api/videos/{video_id}/file")
async def video_file_head(video_id: str, db: Session = Depends(get_db)):
    """Handle HEAD requests for video file metadata"""
    from models import Video

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    file_path = video.file_path
    if not file_path or not os.path.exists(file_path):
        # Try alternate paths
        possible_paths = [
            os.path.join("uploads", video.filename),
            os.path.join("uploads", f"{video.id}.mp4"),
            video.filename if os.path.exists(video.filename) else None
        ]
        for path in possible_paths:
            if path and os.path.exists(path):
                file_path = path
                break
        else:
            raise HTTPException(status_code=404, detail="Video file not found")

    file_size = os.path.getsize(file_path)

    return Response(
        status_code=200,
        headers={
            "Content-Type": "video/mp4",
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Accept, Content-Type",
            "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges, Content-Type",
            "Cache-Control": "public, max-age=3600"
        }
    )
```

### Change 3: Modify GET Handler (Critical Priority)

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Location**: Lines 549-592

**Replace with**:
```python
@app.get("/api/videos/{video_id}/file")
async def get_video_file(
    video_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Serve video files with proper CORS and byte-range support"""
    try:
        from models import Video

        # Get video from database
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Resolve the actual file path
        file_path = video.file_path
        if not file_path or not os.path.exists(file_path):
            # Try alternate paths if original doesn't exist
            possible_paths = [
                os.path.join("uploads", video.filename),
                os.path.join("uploads", f"{video.id}.mp4"),
                video.filename if os.path.exists(video.filename) else None
            ]

            for path in possible_paths:
                if path and os.path.exists(path):
                    file_path = path
                    break
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Video file not found at {file_path}"
                )

        # Get file stats
        file_size = os.path.getsize(file_path)

        # Handle byte-range requests
        range_header = request.headers.get("Range")
        if range_header:
            # Parse Range header (e.g., "bytes=0-1023")
            import re
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else file_size - 1

                # Validate range
                if start >= file_size or end >= file_size or start > end:
                    raise HTTPException(
                        status_code=416,
                        detail="Requested range not satisfiable",
                        headers={
                            "Content-Range": f"bytes */{file_size}",
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Expose-Headers": "Content-Range, Content-Length"
                        }
                    )

                # Read the requested range
                with open(file_path, "rb") as f:
                    f.seek(start)
                    chunk = f.read(end - start + 1)

                # Return partial content with proper headers
                return Response(
                    content=chunk,
                    status_code=206,
                    media_type="video/mp4",
                    headers={
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Content-Length": str(len(chunk)),
                        "Accept-Ranges": "bytes",
                        "Cache-Control": "public, max-age=3600",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                        "Access-Control-Allow-Headers": "Range, Accept, Content-Type",
                        "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges, Content-Type"
                    }
                )

        # Return full file if no range requested
        return FileResponse(
            file_path,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "Range, Accept, Content-Type",
                "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges, Content-Type"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error serving video: {str(e)}"
        )
```

### Change 4: Update CORSMiddleware Configuration (Medium Priority)

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Location**: Lines 483-491

**Replace with**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
    expose_headers=[
        "Content-Length",
        "Content-Range",
        "Accept-Ranges",
        "Content-Type",
        "X-Process-Time"
    ],
    max_age=3600,
)
```

### Change 5: Update Security Middleware (Low Priority)

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Location**: Lines 4074-4087

**Modify to preserve CORS headers**:
```python
@app.middleware("http")
async def add_security_headers(request, call_next):
    """
    Security headers middleware - FOCUSED SCOPE

    This middleware ONLY adds security headers to responses.
    PRESERVES existing CORS headers set by endpoints.
    """
    response = await call_next(request)

    # Only add security headers if they don't already exist
    if "X-Content-Type-Options" not in response.headers:
        response.headers["X-Content-Type-Options"] = "nosniff"
    if "X-Frame-Options" not in response.headers:
        response.headers["X-Frame-Options"] = "DENY"
    if "X-XSS-Protection" not in response.headers:
        response.headers["X-XSS-Protection"] = "1; mode=block"
    if "Strict-Transport-Security" not in response.headers:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response
```

## Testing Strategy

### Manual Testing

1. **Test OPTIONS Request**:
```bash
curl -X OPTIONS http://localhost:8000/api/videos/{video_id}/file \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

Expected response:
```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, HEAD, OPTIONS
Access-Control-Allow-Headers: Range, Accept, Content-Type, Authorization
Access-Control-Expose-Headers: Content-Length, Content-Range, Accept-Ranges, Content-Type
```

2. **Test HEAD Request**:
```bash
curl -I http://localhost:8000/api/videos/{video_id}/file \
  -H "Origin: http://localhost:3000"
```

Expected response:
```
HTTP/1.1 200 OK
Content-Type: video/mp4
Content-Length: 12345678
Accept-Ranges: bytes
Access-Control-Allow-Origin: *
```

3. **Test GET Request (Full)**:
```bash
curl http://localhost:8000/api/videos/{video_id}/file \
  -H "Origin: http://localhost:3000" \
  -o test_video.mp4
```

Expected: Video downloads successfully with proper CORS headers

4. **Test GET Request (Byte-Range)**:
```bash
curl http://localhost:8000/api/videos/{video_id}/file \
  -H "Origin: http://localhost:3000" \
  -H "Range: bytes=0-1023" \
  -v
```

Expected response:
```
HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1023/12345678
Content-Length: 1024
Accept-Ranges: bytes
Access-Control-Allow-Origin: *
```

### Frontend Testing

**Test in Browser Console**:
```javascript
// Test video element
const video = document.querySelector('video');
video.src = 'http://localhost:8000/api/videos/{video_id}/file';
video.load();
video.play();

// Check for CORS errors in console
// Should see: No errors, video plays successfully
```

## Deployment Instructions

### Step 1: Backup Current Configuration
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
cp main.py main.py.backup
```

### Step 2: Apply Changes
Apply all changes from Implementation Plan in order:
1. Add OPTIONS handler
2. Add HEAD handler
3. Modify GET handler
4. Update CORSMiddleware config
5. Update security middleware

### Step 3: Restart Backend Server
```bash
# Kill existing process
pkill -f "uvicorn main:socketio_app"

# Start fresh
python -m uvicorn main:socketio_app --host 0.0.0.0 --port 8000 --reload
```

### Step 4: Verify Server Startup
Check logs for:
```
INFO:     Application startup complete.
CORS configured for 4 origins
```

### Step 5: Run Tests
Execute all manual tests from Testing Strategy section

### Step 6: Frontend Verification
1. Open frontend at http://localhost:3000
2. Navigate to page with video player
3. Verify video loads and plays without CORS errors
4. Check browser Network tab for proper CORS headers

## Monitoring & Validation

### Success Criteria

1. **OPTIONS Request**: Returns 200 with proper CORS headers
2. **HEAD Request**: Returns 200 with Content-Length and CORS headers
3. **GET Request**: Returns 200 (or 206 for ranges) with video data
4. **Browser Console**: No CORS errors when loading video
5. **Video Playback**: Smooth playback with seek support

### Performance Metrics

- **Response Time**: < 100ms for OPTIONS/HEAD
- **First Byte Time**: < 200ms for GET requests
- **Byte-Range Support**: Seek operations work instantly
- **Cache Hit Rate**: > 80% for repeated requests

## Rollback Plan

If issues occur after deployment:

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
cp main.py.backup main.py
python -m uvicorn main:socketio_app --host 0.0.0.0 --port 8000 --reload
```

## Future Improvements

1. **Add Compression Support**: Gzip for video metadata responses
2. **Implement CDN Integration**: CloudFront or similar for production
3. **Add Rate Limiting**: Prevent abuse of video endpoints
4. **Enhanced Caching**: ETag support for conditional requests
5. **Metrics Collection**: Track video streaming performance

## References

- FastAPI CORS Documentation: https://fastapi.tiangolo.com/tutorial/cors/
- Starlette CORSMiddleware: https://www.starlette.io/middleware/#corsmiddleware
- HTTP Range Requests: https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests
- CORS Specification: https://fetch.spec.whatwg.org/#http-cors-protocol

## Conclusion

The CORS issue stems from FastAPI's middleware execution order causing CORSMiddleware to override manually-set headers. The solution implements explicit CORS handling at the endpoint level with proper OPTIONS, HEAD, and GET handlers that bypass middleware interference. This ensures video files stream correctly with full byte-range and CORS support.