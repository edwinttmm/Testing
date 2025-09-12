# Docker Deployment Troubleshooting Guide

## Issue: Frontend Container Unhealthy

### Root Cause Analysis
The frontend container was failing due to several issues:

1. **Health Check Too Aggressive**: Health checks were starting too early (90s) and retrying too frequently
2. **Missing System Dependencies**: The Node.js container needed `procps` package for proper process management
3. **Network Recreation Issues**: Docker Compose needed network recreation when configuration changed
4. **Dependency Chain Problems**: Frontend was depending on backend health, causing circular dependency issues

### Fixed Configuration

#### Updated docker-compose.immediate.yml
```yaml
frontend:
  image: node:20-slim
  container_name: ai_validation_frontend_immediate
  ports:
    - "0.0.0.0:3000:3000"
  environment:
    - REACT_APP_API_URL=http://localhost:8000
    - REACT_APP_WS_URL=ws://localhost:8000
    - NODE_ENV=development
    - HOST=0.0.0.0
    - PORT=3000
    - CHOKIDAR_USEPOLLING=true
    - WATCHPACK_POLLING=true
  volumes:
    - ./frontend:/app
  working_dir: /app
  command: bash -c "
    set -e &&
    echo 'Installing system dependencies...' &&
    apt-get update && apt-get install -y curl python3 make g++ procps &&
    echo 'Cleaning npm cache...' &&
    npm cache clean --force &&
    echo 'Checking package.json...' &&
    ls -la package.json &&
    cat package.json | head -20 &&
    echo 'Installing npm packages...' &&
    npm install --legacy-peer-deps --unsafe-perm --no-audit --no-fund &&
    echo 'Starting React development server...' &&
    npm start"
  depends_on:
    - redis
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000", "||", "exit", "1"]
    interval: 45s
    timeout: 15s
    retries: 5
    start_period: 180s
  restart: unless-stopped
```

### Key Fixes

1. **Extended Health Check Timeouts**:
   - `start_period`: 90s → 180s (3 minutes for npm install + React startup)
   - `interval`: 30s → 45s (less frequent checks)
   - `timeout`: 10s → 15s (longer timeout for slow responses)
   - `retries`: 3 → 5 (more retry attempts)

2. **Added System Dependencies**:
   - Added `procps` package for process management
   - Added verbose logging for debugging startup issues

3. **Improved Environment Variables**:
   - Added `CHOKIDAR_USEPOLLING=true` for file watching in containers
   - Added `WATCHPACK_POLLING=true` for webpack polling

4. **Fixed Dependencies**:
   - Changed from `backend` dependency to `redis` only
   - Removed circular dependency chain

5. **Enhanced Error Handling**:
   - Added `set -e` for script failure detection
   - Added echo statements for debugging startup process
   - Improved npm install flags (`--no-audit --no-fund`)

### Updated Deployment Script

The `scripts/immediate-deploy.sh` now includes:

1. **Cleanup Functions**:
   ```bash
   cleanup_unhealthy() {
       echo "🧹 Cleaning up unhealthy containers..."
       docker ps -aq --filter health=unhealthy | xargs -r docker stop
       docker ps -aq --filter health=unhealthy | xargs -r docker rm
       docker ps -aq --filter status=exited | xargs -r docker rm
       docker image prune -f
   }
   ```

2. **Service Monitoring**:
   - 30-iteration startup monitoring loop
   - Automatic log collection on container failures
   - Health check verification with retries

3. **Connectivity Testing**:
   - Backend health endpoint testing with 5 retry attempts
   - Frontend HTTP status code verification
   - Container resource usage reporting

### Troubleshooting Commands

```bash
# Check container status
docker-compose -f docker-compose.immediate.yml ps

# View logs
docker logs ai_validation_frontend_immediate -f
docker logs ai_validation_backend_immediate -f

# Test endpoints
curl http://localhost:3000  # Frontend
curl http://localhost:8000/health  # Backend

# Restart services
docker-compose -f docker-compose.immediate.yml restart

# Clean restart
docker-compose -f docker-compose.immediate.yml down --volumes
docker-compose -f docker-compose.immediate.yml up -d

# Container resource usage
docker stats --no-stream
```

### Common Issues and Solutions

1. **"Network needs to be recreated"**:
   - Solution: `docker-compose down` then `docker-compose up -d`

2. **Frontend container exits immediately**:
   - Check: `package.json` exists in frontend directory
   - Check: Node.js version compatibility
   - Solution: Ensure all system dependencies are installed

3. **Health check failing**:
   - Wait for `start_period` duration (3 minutes for frontend)
   - Check if service is actually running inside container
   - Verify health check command works manually

4. **Backend taking too long**:
   - Normal: PyTorch and CUDA libraries are large (3-5GB total)
   - Monitor: `docker logs ai_validation_backend_immediate -f`
   - Expected time: 5-10 minutes for full backend startup

### Success Indicators

- ✅ Redis: Shows "Up (healthy)"
- ✅ Frontend: Shows "Up (healthy)" and responds to HTTP requests on port 3000
- ✅ Backend: Shows "Up (healthy)" and `/health` endpoint returns 200

### Performance Expectations

- **Redis**: Ready in ~10 seconds
- **Frontend**: Ready in 2-4 minutes (npm install + React startup)
- **Backend**: Ready in 5-10 minutes (pip install large ML libraries)
- **Total deployment time**: 10-15 minutes for full stack