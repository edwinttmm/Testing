# CORS Configuration Guide

## Current Configuration

**Location:** `backend/main.py` (lines 525-531)

### Settings
```python
CORS Origins: ['http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:8000', 'http://127.0.0.1:8000']
CORS Methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH']
CORS Headers: ['*']
CORS Credentials: True
```

### Configuration Source
- **Settings File:** `backend/config/__init__.py` (`settings.py`)
- **Environment Variable:** `CORS_ORIGINS` (comma-separated list)
- **Default Behavior:** Allows localhost origins on ports 3000 and 8000

## How CORS Works

### Preflight Requests
For complex requests (POST, PUT, DELETE, custom headers), browsers send an OPTIONS request first:

```bash
OPTIONS /api/test-sessions HTTP/1.1
Host: localhost:8000
Origin: http://localhost:3000
Access-Control-Request-Method: POST
Access-Control-Request-Headers: content-type
```

### Backend Response
```http
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS, PATCH
Access-Control-Allow-Headers: *
Access-Control-Allow-Credentials: true
```

## Testing CORS

### 1. Test Simple GET Request
```bash
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: GET" \
     http://localhost:8000/api/monitoring/status
```

**Expected Response Headers:**
```
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Credentials: true
```

### 2. Test Preflight (OPTIONS) Request
```bash
curl -X OPTIONS \
     -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: content-type" \
     http://localhost:8000/api/test-sessions \
     -v
```

**Expected Response:**
- Status: 200 OK
- `Access-Control-Allow-Origin: http://localhost:3000`
- `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS, PATCH`
- `Access-Control-Allow-Headers: *`

### 3. Test with Credentials
```bash
curl -H "Origin: http://localhost:3000" \
     -H "Cookie: session=abc123" \
     http://localhost:8000/api/monitoring/status
```

**Expected:**
- `Access-Control-Allow-Credentials: true`

## Configuration for Different Environments

### Development (.env)
```bash
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_CREDENTIALS=true
```

### Production (.env.production)
```bash
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_CREDENTIALS=true
CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_MAX_AGE=3600
```

### Docker (.env.docker)
```bash
# Allow frontend container by service name
CORS_ORIGINS=http://frontend:3000,http://localhost:3000
CORS_CREDENTIALS=true
```

## Common CORS Issues and Solutions

### Issue 1: No 'Access-Control-Allow-Origin' Header
**Symptom:**
```
Access to fetch at 'http://localhost:8000/api/...' from origin 'http://localhost:3000'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
```

**Solution:**
1. Check that backend is running
2. Verify origin is in `CORS_ORIGINS` list
3. Check backend logs for CORS middleware errors

### Issue 2: Credentials Not Allowed
**Symptom:**
```
The value of the 'Access-Control-Allow-Origin' header in the response must not be
the wildcard '*' when the request's credentials mode is 'include'
```

**Solution:**
```python
# Don't use wildcard with credentials
allow_origins=["http://localhost:3000"]  # ✅ Specific origins
allow_credentials=True
```

### Issue 3: Preflight Failure
**Symptom:**
```
Response to preflight request doesn't pass access control check
```

**Solution:**
1. Ensure OPTIONS method is allowed
2. Check `Access-Control-Allow-Headers` includes requested headers
3. Verify frontend is sending correct headers

## Frontend Configuration

### Axios Configuration
```typescript
// frontend/src/services/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  withCredentials: true,  // Important for cookies
  headers: {
    'Content-Type': 'application/json'
  }
});
```

### Fetch API Configuration
```typescript
fetch('http://localhost:8000/api/test-sessions', {
  method: 'POST',
  credentials: 'include',  // Important for cookies
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(data)
});
```

## Verification Checklist

- [ ] Backend running on correct port (8000)
- [ ] Frontend running on correct port (3000)
- [ ] CORS origins configured correctly
- [ ] Preflight requests return 200 OK
- [ ] Simple GET requests work
- [ ] POST requests with body work
- [ ] Credentials (cookies) are sent/received
- [ ] Error responses include CORS headers
- [ ] No console errors about CORS in browser

## Security Considerations

### 1. Production Origins
```python
# ❌ NEVER use wildcard in production
allow_origins=["*"]  # DANGEROUS

# ✅ Use specific domains
allow_origins=[
    "https://yourdomain.com",
    "https://www.yourdomain.com"
]
```

### 2. Sensitive Headers
```python
# ❌ Don't expose all headers
allow_headers=["*"]

# ✅ Be specific
allow_headers=[
    "Content-Type",
    "Authorization",
    "X-Requested-With"
]
```

### 3. Credentials
```python
# Only enable if needed
allow_credentials=True  # Use only if cookies/auth headers required
```

## Debugging CORS Issues

### 1. Browser DevTools
```
1. Open DevTools (F12)
2. Go to Network tab
3. Look for failed request
4. Check Response Headers
5. Check Console for error messages
```

### 2. Backend Logs
```bash
# Enable CORS debug logging
import logging
logging.getLogger("fastapi.middleware.cors").setLevel(logging.DEBUG)
```

### 3. Test with cURL
```bash
# Test from command line (bypasses browser CORS)
curl -v http://localhost:8000/api/monitoring/status
```

## Advanced Configuration

### Vary Header
```python
# Tell caches that response varies by Origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    vary=["Origin"]
)
```

### Max Age (Preflight Caching)
```python
app.add_middleware(
    CORSMiddleware,
    max_age=3600  # Cache preflight for 1 hour
)
```

### Expose Headers
```python
# Allow frontend to read custom headers
app.add_middleware(
    CORSMiddleware,
    expose_headers=["X-Total-Count", "X-Page-Count"]
)
```

## Status

✅ **CORS Configuration:** VERIFIED
- Origins configured for localhost:3000 (frontend) and localhost:8000 (backend)
- Methods: All standard HTTP methods allowed
- Headers: All headers allowed
- Credentials: Enabled

⚠️ **CORS Testing:** PENDING
- Need backend running to test preflight requests
- Need frontend running to test actual browser requests
- End-to-end CORS verification recommended

## Next Steps

1. Start backend: `cd backend && python main.py`
2. Start frontend: `cd frontend && npm start`
3. Test with browser DevTools
4. Verify no CORS errors in console
5. Test all API endpoints from frontend
6. Check preflight requests in Network tab
