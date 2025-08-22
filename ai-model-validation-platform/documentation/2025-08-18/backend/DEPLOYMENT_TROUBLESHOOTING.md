# 🚨 Deployment Issues & Solutions

## Current Status: ✅ Partially Successful
Your services are running but there are network connectivity issues.

## 🔍 Issues Identified:

### 1. Network Connectivity Issues
**Problem**: Frontend showing "Network error - please check your connection"
**Root Cause**: Frontend trying to reach backend API but connection failing

### 2. Missing GPU Detection File
**Problem**: `Cannot find module './src/utils/gpu-detection.js'` 
**Root Cause**: File missing in frontend container during build

## 📊 Current Service Status:
```
✅ Backend: Running on 155.138.239.131:8000
✅ Frontend: Running on 155.138.239.131:3000
✅ PostgreSQL: Running on 155.138.239.131:5432
✅ Redis: Running on 155.138.239.131:6379
✅ CVAT: Running on 155.138.239.131:8080
❌ Frontend-Backend Communication: FAILING
```

## 🛠️ Immediate Fixes Needed:

### Fix 1: Test Backend Health
```bash
# From your server, test backend directly
curl http://localhost:8000/health
curl http://155.138.239.131:8000/health

# Check backend logs
docker logs ai-model-validation-platform-backend-1
```

### Fix 2: Check Frontend Network Configuration
```bash
# Check frontend logs
docker logs ai-model-validation-platform-frontend-1

# Test frontend container network access
docker exec -it ai-model-validation-platform-frontend-1 sh
# Inside container, test backend connectivity:
curl http://backend:8000/health
curl http://155.138.239.131:8000/health
```

### Fix 3: Create Missing GPU Detection File
```bash
# Create the missing GPU detection file
mkdir -p ai-model-validation-platform/frontend/src/utils
cat > ai-model-validation-platform/frontend/src/utils/gpu-detection.js << 'EOF'
function detectGPU() {
    try {
        // Basic GPU detection for browser environment
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        
        if (gl) {
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (debugInfo) {
                return {
                    vendor: gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL),
                    renderer: gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL),
                    supported: true
                };
            }
        }
        
        return {
            vendor: 'Unknown',
            renderer: 'Software Rendering',
            supported: false
        };
    } catch (error) {
        return {
            vendor: 'Detection Failed',
            renderer: 'CPU-only mode',
            supported: false,
            error: error.message
        };
    }
}

module.exports = { detectGPU };
EOF

# Rebuild frontend with the fix
docker compose build frontend
docker compose up -d frontend
```

## 🔧 Network Troubleshooting Steps:

### Step 1: Verify Internal Container Communication
```bash
# Test backend from inside frontend container
docker exec -it ai-model-validation-platform-frontend-1 sh
wget -O- http://backend:8000/health 2>/dev/null || echo "Internal network failed"
```

### Step 2: Check External Network Access
```bash
# Test external backend access
curl -v http://155.138.239.131:8000/health
curl -v http://155.138.239.131:8000/api/dashboard/stats
```

### Step 3: Verify CORS Configuration
```bash
# Test CORS with explicit headers
curl -H "Origin: http://155.138.239.131:3000" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     http://155.138.239.131:8000/api/projects
```

### Step 4: Check Container Network
```bash
# Inspect Docker network
docker network ls
docker network inspect vru_validation_network

# Check container IPs
docker inspect ai-model-validation-platform-backend-1 | grep IPAddress
docker inspect ai-model-validation-platform-frontend-1 | grep IPAddress
```

## 🚀 Quick Resolution Commands:

### Option A: Restart with Network Reset
```bash
# Stop all services
docker compose down

# Remove network and volumes if needed
docker network prune -f

# Rebuild and restart
docker compose up -d --build
```

### Option B: Fix Frontend API Configuration
```bash
# Check current frontend API URL
docker exec -it ai-model-validation-platform-frontend-1 env | grep REACT_APP_API_URL

# If needed, update and restart
docker compose restart frontend
```

## 📱 Testing Frontend-Backend Connection:

### Browser Developer Tools Check:
1. Open http://155.138.239.131:3000
2. Press F12 (Dev Tools)
3. Go to Network tab
4. Refresh page
5. Look for failed requests to 155.138.239.131:8000

### Expected Working State:
- ✅ GET http://155.138.239.131:8000/api/dashboard/stats → 200 OK
- ✅ GET http://155.138.239.131:8000/api/projects → 200 OK
- ✅ No CORS errors in console

## 🔍 Root Cause Analysis:

The errors suggest:
1. **Frontend is deployed** ✅
2. **Backend is deployed** ✅  
3. **Network requests are failing** ❌
4. **Missing GPU detection file** ❌

Most likely causes:
- Firewall blocking inter-service communication
- Docker network configuration issue
- Backend not responding on external IP
- CORS configuration mismatch

## 🎯 Priority Fixes:

1. **HIGH**: Fix GPU detection file (build error)
2. **HIGH**: Test backend health endpoint directly
3. **HIGH**: Verify frontend can reach backend
4. **MEDIUM**: Check container network configuration
5. **LOW**: Optimize error handling

Run these diagnostics and let me know the results!