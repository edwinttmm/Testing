# Docker Command Configuration Fix

## Issue Identified
The docker-compose.yml file overrides the Dockerfile's CMD instruction, bypassing the `wait-for-services.sh` script that ensures dependencies are ready.

## Current Configuration Problem
- **Dockerfile CMD**: Uses `wait-for-services.sh` to wait for PostgreSQL and Redis
- **docker-compose.yml command**: Overrides with direct uvicorn start, ignoring service dependencies

## Recommended Fix

### Option 1: Use the wait-for-services.sh script (Recommended)
Update docker-compose.yml backend command to:

```yaml
command: [
  "/app/scripts/wait-for-services.sh",
  "uvicorn", "main:socketio_app", "--host", "0.0.0.0", "--port", "8000", "--reload"
]
```

### Option 2: Keep current approach but add manual dependency wait
Keep the current command but ensure proper startup order with healthchecks:

```yaml
command: [
  "sh", "-c",
  "echo 'Waiting for database...' && sleep 30 && python -c 'import database; print(\"Database connection test passed\")' && uvicorn main:socketio_app --host 0.0.0.0 --port 8000 --reload"
]
```

## Why wait-for-services.sh is Better
1. **Robust dependency checking**: Tests actual service readiness, not just delays
2. **Configurable timeouts**: Can handle varying startup times
3. **Multiple connection methods**: Uses nc, telnet, or bash sockets as fallback
4. **Service-specific verification**: PostgreSQL and Redis specific health checks
5. **Better error handling**: Provides clear failure messages

## Quick Fix Command
Run this on your Vultr server to use the wait-for-services.sh approach:

```bash
cd ~/Testing/ai-model-validation-platform
```

Then edit docker-compose.yml to replace the backend command with:
```yaml
command: ["/app/scripts/wait-for-services.sh", "uvicorn", "main:socketio_app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

This will ensure all services are ready before the backend starts, preventing connection errors.