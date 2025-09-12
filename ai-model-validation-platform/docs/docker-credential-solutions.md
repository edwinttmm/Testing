# Docker Credential Error Solutions

## Problem Diagnosis

The error `ERROR: failed to solve: error getting credentials - err: exit status 1, out: ''` is caused by Docker trying to use Windows Docker Desktop's credential helper (`desktop.exe`) from within WSL2, which fails due to access restrictions.

**Root Cause**: `~/.docker/config.json` contains `"credsStore": "desktop.exe"` which is not accessible from WSL2.

## 3 Complete Solutions

### Solution 1: Fix Docker Credentials (Recommended)

**Immediate Fix:**
```bash
# Backup existing config
cp ~/.docker/config.json ~/.docker/config.json.backup

# Remove problematic credential store
echo '{}' > ~/.docker/config.json

# Deploy stack
cd /path/to/project
./scripts/immediate-deploy.sh
```

**What it does**: Removes the Windows credential helper dependency, allowing Docker to work natively in WSL2.

### Solution 2: Alternative Base Image (If Node:20-alpine fails)

Update `frontend/Dockerfile` to use `node:20-slim` instead of `node:20-alpine`:

```dockerfile
FROM node:20-slim  # Instead of node:20-alpine

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 make g++ curl \
    && rm -rf /var/lib/apt/lists/*

# Rest of Dockerfile...
```

**Why it works**: `node:20-slim` uses Debian base which has better compatibility and doesn't trigger credential issues.

### Solution 3: Local Build Fix (Manual approach)

If automated deployment fails, build manually:

```bash
# 1. Fix credentials
echo '{}' > ~/.docker/config.json

# 2. Clean Docker
docker system prune -af
docker volume prune -f

# 3. Disable BuildKit (if needed)
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0

# 4. Build individually
docker build -t backend-image ./backend
docker build -t frontend-image ./frontend

# 5. Use docker-compose with built images
docker-compose up -d
```

## Complete Working Commands

### Immediate Deployment (Use This Now)
```bash
cd /home/rigade/Testing/ai-model-validation-platform
./scripts/immediate-deploy.sh
```

### Full Stack Deployment
```bash
cd /home/rigade/Testing/ai-model-validation-platform
./scripts/docker-deploy.sh
```

### Quick Deploy (Fastest)
```bash
cd /home/rigade/Testing/ai-model-validation-platform
./scripts/quick-deploy.sh
```

## Service URLs After Deployment

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000  
- **API Documentation**: http://localhost:8000/docs
- **Redis**: localhost:6379

## Troubleshooting Commands

```bash
# Check service status
docker-compose -f docker-compose.immediate.yml ps

# View logs
docker-compose -f docker-compose.immediate.yml logs -f

# Restart specific service
docker-compose -f docker-compose.immediate.yml restart frontend

# Full cleanup
docker-compose -f docker-compose.immediate.yml down --volumes
docker system prune -af

# Check Docker config
cat ~/.docker/config.json
```

## Prevention

To prevent this issue in the future:

1. **Always check Docker config**: `cat ~/.docker/config.json`
2. **Use WSL2-compatible base images**: Prefer `node:20-slim` over `node:20-alpine`
3. **Set environment variables**:
   ```bash
   export DOCKER_BUILDKIT=0
   export COMPOSE_DOCKER_CLI_BUILD=0
   ```

## Validation

After deployment, verify services are running:

```bash
curl http://localhost:8000/health    # Backend health
curl http://localhost:3000           # Frontend
docker ps                           # All containers
```

Expected response from backend: `{"status":"healthy","timestamp":"..."}`
Expected response from frontend: HTTP 200 with React app HTML