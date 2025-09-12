# CRITICAL BACKEND FIX - Missing Bleach Dependency

## Problem
Backend container failing to start with:
```
WARNING - Ground truth routes not available: No module named 'bleach'
WARNING - Enhanced routes not available: No module named 'bleach'
```

## Root Cause
The Docker container was using `requirements-minimal.txt` and `requirements-docker-minimal.txt` which were missing the `bleach` security library required by several critical modules:
- `src/middleware/validation_middleware.py`
- `src/form_validation_middleware.py` 
- `src/security/input_sanitizer.py`
- `src/unified_refinement_system.py`

## Fix Applied
Added missing security dependencies to both requirements files:
```
bleach==6.1.0
cryptography==41.0.7
validators==0.22.0
```

## IMMEDIATE RESTART COMMANDS

Run these commands in sequence to fix the backend:

### 1. Stop current containers
```bash
cd /home/rigade/Testing/ai-model-validation-platform
docker-compose down
```

### 2. Remove backend container and image to force rebuild
```bash
docker container rm ai_validation_backend 2>/dev/null || true
docker image rm ai-model-validation-platform-backend 2>/dev/null || true
```

### 3. Rebuild and start with fixed dependencies
```bash
docker-compose up --build -d backend
```

### 4. Monitor startup logs
```bash
docker-compose logs -f backend
```

### 5. Once backend is healthy, start frontend
```bash
docker-compose up -d frontend
```

### 6. Verify the fix worked
```bash
# Should show healthy status
docker-compose ps

# Should show ground truth and enhanced routes loaded
docker-compose logs backend | grep -E "Ground truth|Enhanced routes"

# Test API endpoint
curl -f http://localhost:8000/health
```

## Expected Success Output
After fix, you should see:
```
INFO - Ground truth routes loaded successfully ✅
INFO - Enhanced routes loaded successfully ✅
INFO - Uvicorn running on http://0.0.0.0:8000 ✅
```

## If Still Failing
1. Check Docker logs: `docker-compose logs backend`
2. Verify requirements files contain bleach dependency
3. Force clean rebuild: `docker system prune -f && docker-compose build --no-cache backend`