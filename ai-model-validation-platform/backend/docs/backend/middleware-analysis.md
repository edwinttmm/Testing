# Middleware Analysis - Security and Request Processing

## Overview

The FastAPI application implements a layered middleware architecture for cross-cutting concerns including CORS, security, logging, and static file serving. The middleware stack processes all requests and responses with proper error handling and security enforcement.

## Middleware Stack (Processing Order)

### 1. CORS Middleware (CORSMiddleware)

**Configuration**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Default: localhost:3000, 8001
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)
```

**Features**:
- **Dynamic Origins**: Configurable via environment variables
- **Credential Support**: Enables cookie-based authentication
- **Pre-flight Caching**: 1-hour cache for OPTIONS requests
- **Development Friendly**: Allows all headers for flexibility

**Security Considerations**:
- Production environments should restrict origins to specific domains
- Wildcard headers (`["*"]`) should be restricted in production
- Credential support requires careful origin configuration

### 2. Security Middleware (Planned)

**Status**: Currently disabled but architecture ready
```python
# setup_security_middleware(app, settings)  # Disabled for now
```

**Planned Features**:
- **Security Headers**: HSTS, CSP, X-Frame-Options
- **Request Validation**: Input sanitization
- **Rate Limiting**: Per-endpoint and global limits
- **Authentication Middleware**: JWT validation

**Configuration Ready**:
```python
# Security settings from config.py
security_headers_enabled: bool = True
hsts_enabled: bool = False  # Disabled by default
csp_enabled: bool = True
```

### 3. Static File Middleware

**Mount Configuration**:
```python
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/screenshots", StaticFiles(directory="screenshots"), name="screenshots")
```

**Features**:
- **Direct File Serving**: Efficient static file delivery
- **Directory Mapping**: `/uploads` → `uploads/`, `/screenshots` → `screenshots/`
- **Caching Headers**: Automatic browser caching
- **Range Request Support**: For large video files

**Security Features**:
- **Path Traversal Protection**: Built into StaticFiles
- **File Type Validation**: Handled at upload endpoints
- **Access Control**: Directory-level restrictions

## Custom Endpoint Middleware

### Dynamic Video File Serving

```python
@app.get("/api/videos/{video_id}/file")
async def get_video_file(video_id: str, db: Session = Depends(get_db)):
```

**Advanced Features**:
- **Database-driven Path Resolution**: Dynamic file path lookup
- **Fallback Path Handling**: Multiple path attempt strategies
- **HTTP Headers Optimization**:
  ```python
  return FileResponse(
      file_path, 
      media_type="video/mp4",
      headers={
          "Accept-Ranges": "bytes",        # Enable range requests
          "Cache-Control": "public, max-age=3600"  # 1-hour cache
      }
  )
  ```

**Error Handling**:
- **404 for Missing Videos**: Proper HTTP status codes
- **500 for Server Errors**: Comprehensive error logging
- **Path Validation**: Security against directory traversal

### Screenshot File Serving

```python
@app.get("/screenshots/{filename}")
async def get_screenshot(filename: str):
```

**Features**:
- **Direct File Access**: No database lookup required
- **Simple Error Handling**: 404 for missing files
- **Security**: Filename validation and sanitization

## WebSocket Middleware

### LabJack WebSocket Stream

```python
@app.websocket("/ws/labjack/stream")
async def labjack_websocket_stream(websocket: WebSocket):
```

**Advanced Features**:
- **Connection State Management**: 
  ```python
  if websocket.application_state.name == "CONNECTED":
      await websocket.send_text(json.dumps(message_data))
  ```
- **Safe Message Sending**: Error-tolerant communication
- **Connection ID Tracking**: Unique identifier per connection
- **30ms Timing Optimization**: High-frequency data streaming

**Error Handling**:
```python
except WebSocketDisconnect:
    logger.info(f"LabJack WebSocket disconnected: {connection_id}")
except Exception as e:
    logger.error(f"LabJack WebSocket error for {connection_id}: {e}")
```

## Security Middleware (Architecture)

### Authentication Middleware (Planned)

**JWT Token Validation**:
```python
class JWTAuthenticationMiddleware:
    async def __call__(self, request: Request, call_next):
        token = request.headers.get("Authorization")
        if token and token.startswith("Bearer "):
            # Validate JWT token
            user = await validate_jwt_token(token[7:])
            request.state.user = user
        return await call_next(request)
```

### Security Headers Middleware (Planned)

**Header Configuration**:
```python
class SecurityHeadersMiddleware:
    def __init__(self, app, settings):
        self.app = app
        self.settings = settings
    
    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        
        if self.settings.hsts_enabled:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        if self.settings.csp_enabled:
            response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response
```

### Rate Limiting Middleware (Planned)

**Implementation Pattern**:
```python
class RateLimitMiddleware:
    def __init__(self, app, redis_client, limits):
        self.app = app
        self.redis = redis_client
        self.limits = limits
    
    async def __call__(self, request: Request, call_next):
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"
        
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, 60)  # 1-minute window
        
        if current > self.limits.get(request.url.path, 100):
            raise HTTPException(429, "Rate limit exceeded")
        
        return await call_next(request)
```

## Request/Response Processing

### Request Logging Pattern

```python
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Log request details
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Log response details
    process_time = time.time() - start_time
    logger.info(
        f"Response: {response.status_code} "
        f"Duration: {process_time:.3f}s"
    )
    
    return response
```

### Error Handling Middleware

```python
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
```

## Performance Middleware

### Response Compression

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### Response Time Headers

```python
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

## Configuration-Driven Middleware

### Environment-Based Configuration

```python
# From config.py
class Settings(BaseSettings):
    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    cors_credentials: bool = True
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]
    
    # Security settings
    security_headers_enabled: bool = True
    hsts_enabled: bool = False
    csp_enabled: bool = True
```

### Dynamic CORS Configuration

```python
@field_validator('cors_origins', mode='before')
def parse_cors_origins(cls, v):
    if isinstance(v, str):
        if not v.strip():
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    return v
```

## Monitoring Middleware

### Request Metrics Collection

```python
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # Collect metrics
    metrics_collector.record_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=duration
    )
    
    return response
```

### Health Check Integration

```python
@app.middleware("http")
async def health_check_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return JSONResponse({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    return await call_next(request)
```

## File Upload Middleware

### Upload Size Validation

```python
@app.middleware("http")
async def upload_size_middleware(request: Request, call_next):
    if request.method == "POST" and "multipart/form-data" in request.headers.get("content-type", ""):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_file_size:
            raise HTTPException(413, "File too large")
    
    return await call_next(request)
```

## Development vs Production Middleware

### Development Middleware

```python
if settings.app_environment == "development":
    # Add development-specific middleware
    app.add_middleware(DebugMiddleware)
    app.add_middleware(DetailedErrorMiddleware)
```

### Production Middleware

```python
if settings.app_environment == "production":
    # Add production security middleware
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(RateLimitMiddleware, limits=production_limits)
    app.add_middleware(AuditLoggingMiddleware)
```

## WebSocket Middleware Patterns

### Connection Management

```python
class WebSocketConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                self.disconnect(connection)
```

## Error Recovery Middleware

### Circuit Breaker Pattern

```python
class CircuitBreakerMiddleware:
    def __init__(self, app, failure_threshold=5, timeout=60):
        self.app = app
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.last_failure_time = None
        self.timeout = timeout
    
    async def __call__(self, request: Request, call_next):
        if self.is_circuit_open():
            raise HTTPException(503, "Service temporarily unavailable")
        
        try:
            response = await call_next(request)
            self.on_success()
            return response
        except Exception as e:
            self.on_failure()
            raise e
    
    def is_circuit_open(self):
        if self.failure_count >= self.failure_threshold:
            if time.time() - self.last_failure_time > self.timeout:
                self.reset()
                return False
            return True
        return False
```

## Middleware Testing

### Testing CORS Configuration

```python
def test_cors_headers(client):
    response = client.options("/api/projects")
    assert "Access-Control-Allow-Origin" in response.headers
    assert response.headers["Access-Control-Allow-Methods"]
```

### Testing Security Headers

```python
def test_security_headers(client):
    response = client.get("/api/health")
    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
```