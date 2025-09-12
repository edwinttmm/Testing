# Simple Mode Setup Guide - AI Model Validation Platform

## Overview
This guide provides step-by-step instructions to start the application in simple development mode with Docker-matching database credentials.

## Problem Solved
- **Before**: Backend tried to connect with production credentials, causing startup failures
- **After**: All services use consistent, simple development credentials

## Quick Start Commands

### Method 1: Automated Setup (Recommended)
```bash
cd /home/rigade/Testing/ai-model-validation-platform

# Use the automated startup script
chmod +x scripts/start-simple.sh
./scripts/start-simple.sh
```

### Method 2: Manual Setup
```bash
cd /home/rigade/Testing/ai-model-validation-platform

# Copy simple mode environment
cp .env.development.simple .env

# Stop any existing containers
docker-compose -f docker-compose.simple.yml down --remove-orphans

# Start all services
docker-compose -f docker-compose.simple.yml up --build -d

# Check status
docker-compose -f docker-compose.simple.yml ps
```

## Service Configuration

### Database (PostgreSQL)
- **Container Name**: `vru-simple-dev_postgres_1`
- **Internal Port**: 5432
- **External Port**: 5433 (to avoid conflicts)
- **Database**: `vru_validation`
- **Username**: `postgres`
- **Password**: `password`
- **Connection URL**: `postgresql://postgres:password@postgres:5432/vru_validation` (internal)
- **External Connection**: `postgresql://postgres:password@localhost:5433/vru_validation`

### Redis Cache
- **Container Name**: `vru-simple-dev_redis_1`
- **Internal Port**: 6379
- **External Port**: 6380 (to avoid conflicts)
- **Connection URL**: `redis://redis:6379` (internal)
- **External Connection**: `redis://localhost:6380`

### Backend API
- **Container Name**: `vru-simple-dev_backend_1`
- **Internal Port**: 8000
- **External Port**: 8001 (to avoid conflicts)
- **API Base URL**: `http://localhost:8001`
- **Health Check**: `http://localhost:8001/health`
- **API Documentation**: `http://localhost:8001/docs`

### Frontend
- **Container Name**: `vru-simple-dev_frontend_1`
- **Port**: 3000
- **URL**: `http://localhost:3000`

## Environment Variables Summary

### Key Database Variables
```bash
DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation
AIVALIDATION_DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation
VRU_DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation
```

### Key Redis Variables
```bash
REDIS_URL=redis://redis:6379
AIVALIDATION_REDIS_URL=redis://redis:6379
```

### Key Security Variables (Development Only)
```bash
SECRET_KEY=development-secret-key-change-for-production
AIVALIDATION_SECRET_KEY=development-secret-key-change-for-production
ENVIRONMENT=development
DEBUG=true
```

## Testing Connections

### Test Database Connection
```bash
# From host machine (using external port)
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d vru_validation -c "SELECT version();"
```

### Test Redis Connection
```bash
# Test Redis connectivity
redis-cli -h localhost -p 6380 ping
```

### Test Backend API
```bash
# Test API health
curl http://localhost:8001/health

# Test API documentation
curl http://localhost:8001/docs

# Test API endpoints
curl http://localhost:8001/api/v1/status
```

### Test Frontend
```bash
# Check if frontend is running
curl -I http://localhost:3000
```

## Troubleshooting

### Port Conflicts
If you encounter port conflicts:

1. **Check what's using the ports**:
```bash
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis  
lsof -i :8000  # Backend API
```

2. **Stop conflicting services**:
```bash
# Stop other Docker projects
docker stop $(docker ps -q)

# Or modify ports in docker-compose.simple.yml
```

### Database Connection Issues
1. **Check PostgreSQL container health**:
```bash
docker-compose -f docker-compose.simple.yml exec postgres pg_isready -U postgres
```

2. **Check container logs**:
```bash
docker-compose -f docker-compose.simple.yml logs postgres
docker-compose -f docker-compose.simple.yml logs backend
```

### Backend Startup Issues
1. **Check backend logs**:
```bash
docker-compose -f docker-compose.simple.yml logs backend
```

2. **Common issues**:
   - CORS configuration parsing errors
   - Missing environment variables
   - Database connection failures

### Clean Restart
If services are in a bad state:
```bash
# Complete cleanup and restart
docker-compose -f docker-compose.simple.yml down --remove-orphans
docker volume prune -f
docker network prune -f
docker-compose -f docker-compose.simple.yml up --build -d
```

## Development Workflow

### Making Code Changes
```bash
# Backend changes are automatically reloaded (--reload flag)
# Frontend changes trigger rebuild

# To restart specific service:
docker-compose -f docker-compose.simple.yml restart backend
docker-compose -f docker-compose.simple.yml restart frontend
```

### Database Operations
```bash
# Access database container
docker-compose -f docker-compose.simple.yml exec postgres psql -U postgres -d vru_validation

# Run database migrations (if available)
docker-compose -f docker-compose.simple.yml exec backend alembic upgrade head
```

### Log Monitoring
```bash
# Follow all logs
docker-compose -f docker-compose.simple.yml logs -f

# Follow specific service logs
docker-compose -f docker-compose.simple.yml logs -f backend
docker-compose -f docker-compose.simple.yml logs -f postgres
```

## Files Created/Modified

### New Configuration Files
- `.env.development.simple` - Simple mode environment variables
- `config/simple-mode-config.py` - Configuration handler
- `scripts/start-simple.sh` - Automated startup script
- `DATABASE_CONFIGURATION_SUMMARY.md` - Technical details
- `SIMPLE_MODE_SETUP_GUIDE.md` - This guide

### Modified Files
- `docker-compose.simple.yml` - Updated ports and environment variables
- `backend/.env` - Simple mode credentials
- `backend/config.py` - Enhanced database URL fallbacks

## Success Indicators

When everything is working correctly, you should see:

1. **All containers running**:
```bash
$ docker-compose -f docker-compose.simple.yml ps
          Name                         Command                  State                        Ports                  
--------------------------------------------------------------------------------------------------------------------
vru-simple-dev_backend_1    uvicorn main:app --host 0. ...   Up             0.0.0.0:8001->8000/tcp
vru-simple-dev_frontend_1   docker-entrypoint.sh npm start   Up             0.0.0.0:3000->3000/tcp
vru-simple-dev_postgres_1   docker-entrypoint.sh postgres    Up (healthy)   0.0.0.0:5433->5432/tcp
vru-simple-dev_redis_1      docker-entrypoint.sh redis ...   Up             0.0.0.0:6380->6379/tcp
```

2. **API responding**:
```bash
$ curl http://localhost:8001/health
{"status": "healthy", "timestamp": "2024-..."}
```

3. **Database accessible**:
```bash
$ PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d vru_validation -c "SELECT 1;"
 ?column? 
----------
        1
(1 row)
```

## Next Steps

After successful startup:
1. Visit frontend: http://localhost:3000
2. Check API docs: http://localhost:8001/docs  
3. Test API endpoints
4. Start development with consistent database credentials

The configuration ensures all services use matching credentials and avoids port conflicts with existing services.