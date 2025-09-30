# CORS Video Streaming Fix - Implementation Guide

## Quick Summary

**Problem**: Video files fail with CORS error despite headers being added to FileResponse.

**Root Cause**: FastAPI's CORSMiddleware overwrites FileResponse headers during response processing.

**Solution**: Implement explicit OPTIONS and HEAD handlers with manual CORS header management.

## Critical Code Changes Required

### Change 1: Add OPTIONS Handler
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Location**: Insert before line 549 (before existing `@app.get("/api/videos/{video_id}/file")`)

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

### Change 2: Add HEAD Handler
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Location**: Insert before line 549 (after OPTIONS handler)

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

### Change 3: Update GET Handler with Byte-Range Support
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Location**: Replace lines 549-592

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

                # Return partial content
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

### Change 4: Update CORSMiddleware Configuration (Optional Enhancement)
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Location**: Lines 483-491

Replace:
```python
    expose_headers=["*"],
```

With:
```python
    expose_headers=[
        "Content-Length",
        "Content-Range",
        "Accept-Ranges",
        "Content-Type",
        "X-Process-Time"
    ],
```

## Quick Deployment Steps

1. **Backup current main.py**:
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
cp main.py main.py.backup
```

2. **Apply changes** from this guide to main.py

3. **Restart server**:
```bash
pkill -f "uvicorn main:socketio_app"
python -m uvicorn main:socketio_app --host 0.0.0.0 --port 8000 --reload
```

4. **Test OPTIONS request**:
```bash
curl -X OPTIONS http://localhost:8000/api/videos/test-id/file -v
```

Should return 200 with CORS headers.

5. **Test in frontend**: Load a page with video player and verify it works.

## Testing Checklist

- [ ] OPTIONS request returns 200 with CORS headers
- [ ] HEAD request returns 200 with Content-Length
- [ ] GET request without Range returns full video (200)
- [ ] GET request with Range returns partial content (206)
- [ ] Browser console shows no CORS errors
- [ ] Video plays and seeking works in frontend

## Rollback Procedure

If issues occur:
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
cp main.py.backup main.py
python -m uvicorn main:socketio_app --host 0.0.0.0 --port 8000 --reload
```

## Why This Fix Works

1. **Explicit OPTIONS Handler**: Handles CORS preflight before middleware can interfere
2. **HEAD Support**: Allows browsers to check file metadata without downloading
3. **Byte-Range Support**: Enables video seeking and progressive loading
4. **Direct CORS Headers**: Set at endpoint level, bypassing middleware override
5. **Proper Expose Headers**: Tells browser which headers it can access

## Key Technical Insights

- FastAPI middleware executes in reverse order of registration
- CORSMiddleware overwrites existing CORS headers on responses
- FileResponse doesn't preserve manually-set headers through middleware
- Explicit Response objects bypass middleware header manipulation
- Byte-range support requires manual chunk reading and 206 responses