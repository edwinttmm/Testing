# Quick Start - Simple Development Mode

## FIXED: Database Configuration Mismatch

The database configuration mismatch has been resolved. The application now uses consistent credentials across all services.

## Quick Commands

```bash
# Navigate to project
cd /home/rigade/Testing/ai-model-validation-platform

# Start with simple mode (recommended)
cp .env.development.simple .env
docker-compose -f docker-compose.simple.yml up --build -d

# Check status
docker-compose -f docker-compose.simple.yml ps

# Test connections
curl http://localhost:8001/health                              # Backend API
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d vru_validation -c "SELECT 1;"  # Database
```

## Service URLs (Port-Conflict-Free)

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001 
- **API Docs**: http://localhost:8001/docs
- **PostgreSQL**: localhost:5433 (user: postgres, pass: password, db: vru_validation)
- **Redis**: localhost:6380

## Database Credentials (All Services)

```
Host: postgres (internal) / localhost (external)
Port: 5432 (internal) / 5433 (external)
Database: vru_validation
Username: postgres
Password: password
```

## What Was Fixed

1. **Environment Variables**: All services now use consistent PostgreSQL credentials
2. **Port Conflicts**: Services use alternative ports (5433, 6380, 8001) 
3. **CORS Configuration**: Fixed parsing issues in backend
4. **Docker Compose**: Updated with proper environment variables
5. **Configuration Files**: Created simple mode configuration files

## Files Changed

- `.env.development.simple` - New simple mode environment
- `docker-compose.simple.yml` - Updated ports and environment variables
- `backend/.env` - Simple mode credentials
- `backend/config.py` - Enhanced CORS validation
- `scripts/start-simple.sh` - Automated startup script

## Success Indicators

✅ All containers running (Up status)
✅ Database responds to health checks  
✅ Backend API returns health status
✅ No port conflicts
✅ Consistent credentials across all services

The application should now start successfully in development mode with Docker-matching credentials.